"""Agent orchestration dashboard server."""
import asyncio
from collections import deque
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import aiohttp
import psutil
from aiohttp import web

from state import AgentState, NetworkStatsTracker, VALID_STATUSES


DASH_API_KEY_KEY = web.AppKey("dash_api_key", str)
NETWORK_TRACKER_KEY = web.AppKey("network_tracker", NetworkStatsTracker)

MAX_CHAT_MESSAGE_BYTES = 16 * 1024
MAX_JSON_BODY_BYTES = 1 * 1024 * 1024
MAX_CHAT_MESSAGES_PER_WINDOW = 30
CHAT_RATE_WINDOW_SECONDS = 10


# Global state
state = AgentState()
sse_clients = set()
chat_messages = []  # Store chat messages in memory
cleanup_task = None  # Background cleanup task


def error_response(message: str, status: int = 400) -> web.Response:
    """Create normalized API error payload."""
    return web.json_response({"success": False, "error": message}, status=status)


def check_tmux_session(session_name: str) -> tuple[bool, int | None]:
    """Check if tmux session exists and get its exit code if dead.

    Returns:
        (is_alive, exit_code) where exit_code is None if session is alive,
        0 if exited successfully, or non-zero if failed/killed.
    """
    try:
        # Check if session exists and is alive
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Session exists and is alive
            return True, None

        # Session doesn't exist - try to get exit code from session history
        # First check if there's a pane with that session name that exited
        list_result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name} #{pane_dead} #{pane_dead_status}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if list_result.returncode == 0:
            for line in list_result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[0] == session_name and parts[1] == "1":
                    # Found dead pane for this session
                    try:
                        exit_code = int(parts[2])
                        return False, exit_code
                    except ValueError:
                        pass

        # Session doesn't exist and no history found - assume it was killed
        return False, 1

    except (subprocess.TimeoutExpired, FileNotFoundError):
        # tmux command failed or timed out - assume session is dead
        return False, 1


async def cleanup_stale_agents():
    """Check registered agents against running tmux sessions and update status."""
    agents = await state.get_all()

    for agent in agents:
        # Only check agents that are supposed to be running
        if agent.status not in {"working", "queued"}:
            continue

        # Check if tmux session exists (assuming agent.id is the session name)
        is_alive, exit_code = await asyncio.to_thread(check_tmux_session, agent.id)

        if not is_alive:
            # Tmux session is dead - update agent status based on exit code
            if exit_code == 0:
                await state.update_status(agent.id, "done")
                print(f"Agent {agent.id} tmux session exited cleanly, marked as done")
            else:
                await state.update_status(agent.id, "error")
                print(f"Agent {agent.id} tmux session failed (exit {exit_code}), marked as error")

            # Broadcast update to connected clients
            await send_sse_update()


async def agent_cleanup_loop():
    """Background task that periodically checks for stale agents."""
    while True:
        try:
            await asyncio.sleep(60)  # Run every 60 seconds
            await cleanup_stale_agents()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in agent cleanup loop: {e}")


def get_api_key(request: web.Request) -> str:
    """Extract API key from common headers."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return ""


async def parse_json(request: web.Request, required_fields=None):
    """Parse JSON body and verify required fields."""
    content_length = request.content_length
    if content_length is not None and content_length > MAX_JSON_BODY_BYTES:
        return None, error_response("Request body too large", status=413)

    try:
        data = await request.json()
    except Exception:
        return None, error_response("Invalid JSON", status=400)

    if not isinstance(data, dict):
        return None, error_response("Invalid JSON", status=400)

    required_fields = required_fields or []
    missing = [field for field in required_fields if field not in data]
    if missing:
        return None, error_response(f"Missing required field: {missing[0]}", status=400)

    return data, None


async def broadcast_message(message: str):
    """Broadcast one SSE message to all clients with queue backpressure handling."""
    dead_clients = set()
    for queue in list(sse_clients):
        try:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)
        except Exception:
            dead_clients.add(queue)

    sse_clients.difference_update(dead_clients)


async def broadcast_event(event_name: str, payload):
    """Broadcast one typed SSE event."""
    message = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
    await broadcast_message(message)


async def send_sse_update():
    """Broadcast agents and system stats updates."""
    agents = await state.get_all()
    stats = await state.get_stats()

    agents_payload = [
        {
            "id": a.id,
            "project": a.project,
            "task": a.task,
            "status": a.status,
            "started_at": a.started_at,
            "completed_at": a.completed_at,
            "duration": a.duration_seconds(),
        }
        for a in agents
    ]

    await broadcast_event("agents", agents_payload)
    await broadcast_event("system", stats)


@web.middleware
async def auth_middleware(request, handler):
    """Optional API key auth for POST routes."""
    configured_key = request.app[DASH_API_KEY_KEY]
    if configured_key and request.method == "POST" and request.path.startswith("/api/"):
        provided_key = get_api_key(request)
        if provided_key != configured_key:
            return error_response("Unauthorized", status=401)

    return await handler(request)


@web.middleware
async def api_error_middleware(request, handler):
    """Normalize API errors so clients always receive JSON."""
    try:
        return await handler(request)
    except web.HTTPException as exc:
        if not request.path.startswith("/api/"):
            raise
        if exc.status == 400:
            return error_response("Invalid JSON", status=400)
        message = exc.reason or "Request failed"
        return error_response(message, status=exc.status)
    except Exception:
        if not request.path.startswith("/api/"):
            raise
        return error_response("Internal server error", status=500)


async def handle_sse(request):
    """SSE endpoint for live updates."""
    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    queue = asyncio.Queue(maxsize=100)
    sse_clients.add(queue)

    try:
        # Send initial snapshot for this client.
        agents = await state.get_all()
        stats = await state.get_stats()
        initial_agents = [
            {
                "id": a.id,
                "project": a.project,
                "task": a.task,
                "status": a.status,
                "started_at": a.started_at,
                "completed_at": a.completed_at,
                "duration": a.duration_seconds(),
            }
            for a in agents
        ]
        await queue.put(f"event: agents\ndata: {json.dumps(initial_agents)}\n\n")
        await queue.put(f"event: system\ndata: {json.dumps(stats)}\n\n")

        # Stream updates; evict idle clients after 30 seconds of no activity.
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                break
            await response.write(message.encode())
    except Exception:
        pass
    finally:
        sse_clients.discard(queue)

    return response


async def handle_get_agents(request):
    """Get all agents."""
    agents = await state.get_all()
    return web.json_response(
        [
            {
                "id": a.id,
                "project": a.project,
                "task": a.task,
                "status": a.status,
                "started_at": a.started_at,
                "completed_at": a.completed_at,
                "duration": a.duration_seconds(),
            }
            for a in agents
        ]
    )


async def handle_get_stats(request):
    """Get dashboard stats."""
    stats = await state.get_stats()
    return web.json_response(stats)


async def handle_add_agent(request):
    """Add a new agent."""
    data, error = await parse_json(request, required_fields=["id", "project", "task"])
    if error:
        return error

    status = data.get("status", "queued")
    if status not in VALID_STATUSES:
        return error_response("Invalid status", status=400)

    agent = await state.add_agent(
        id=data["id"],
        project=data["project"],
        task=data["task"],
        status=status,
    )
    await send_sse_update()
    return web.json_response({"success": True, "agent": agent.id})


async def handle_update_status(request):
    """Update agent status."""
    data, error = await parse_json(request, required_fields=["id", "status"])
    if error:
        return error

    if data["status"] not in VALID_STATUSES:
        return error_response("Invalid status", status=400)

    agent = await state.update_status(data["id"], data["status"])

    if agent:
        await send_sse_update()
        return web.json_response({"success": True})

    return error_response("Agent not found", status=404)


async def handle_remove_agent(request):
    """Remove an agent."""
    data, error = await parse_json(request, required_fields=["id"])
    if error:
        return error

    success = await state.remove_agent(data["id"])

    if success:
        await send_sse_update()
        return web.json_response({"success": True})

    return error_response("Agent not found", status=404)


async def handle_index(request):
    """Serve index.html for root path."""
    return web.FileResponse(Path(__file__).parent / "static" / "index.html")


async def handle_system_stats(request):
    """Get system statistics."""
    # Uptime
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    uptime_days = uptime_seconds // 86400
    uptime_hours = (uptime_seconds % 86400) // 3600
    uptime_mins = (uptime_seconds % 3600) // 60
    uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_mins}m"

    # Memory
    mem = psutil.virtual_memory()
    mem_used_gb = mem.used / (1024**3)
    mem_total_gb = mem.total / (1024**3)
    mem_percent = mem.percent

    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    load_avg = psutil.getloadavg()

    network_tracker = request.app[NETWORK_TRACKER_KEY]

    return web.json_response(
        {
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
            "memory": {
                "used_gb": round(mem_used_gb, 2),
                "total_gb": round(mem_total_gb, 2),
                "percent": mem_percent,
            },
            "cpu": {
                "percent": cpu_percent,
                "load_1m": round(load_avg[0], 2),
                "load_5m": round(load_avg[1], 2),
                "load_15m": round(load_avg[2], 2),
            },
            "network": {
                "all_time": network_tracker.format_window(*network_tracker.get_all_time_totals()),
                "last_24h": await network_tracker.get_window_delta(24 * 60 * 60),
                "last_1h": await network_tracker.get_window_delta(60 * 60),
            },
        }
    )


async def handle_post_chat(request):
    """Legacy REST chat endpoint: add a chat message and broadcast via SSE."""
    data, error = await parse_json(request, required_fields=["message"])
    if error:
        return error

    message_text = str(data.get("message", "")).strip()

    if not message_text:
        return error_response("Message cannot be empty", status=400)

    # Create message object
    msg = {
        "text": message_text,
        "timestamp": int(time.time()),
        "is_system": False,
    }

    # Store message (keep last 50)
    chat_messages.append(msg)
    if len(chat_messages) > 50:
        chat_messages.pop(0)

    await broadcast_event("chat", msg)

    return web.json_response({"success": True})


def get_gateway_ws_url() -> str:
    """Normalize OPENCLAW_GATEWAY_URL to a ws:// or wss:// endpoint URL."""
    gateway_url = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:18789")
    parsed = urlparse(gateway_url)
    host = (parsed.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme in ("ws", "wss"):
        ws_url = gateway_url
    else:
        if parsed.scheme == "https":
            scheme = "wss"
        elif parsed.scheme == "http":
            scheme = "ws" if is_local else "wss"
        else:
            scheme = "ws" if is_local else "wss"
        ws_url = urlunparse((scheme, parsed.netloc, parsed.path or "", "", "", ""))

    ws_parsed = urlparse(ws_url)
    ws_host = (ws_parsed.hostname or "").lower()
    ws_is_local = ws_host in {"localhost", "127.0.0.1", "::1"}
    if ws_parsed.scheme == "ws" and not ws_is_local:
        raise ValueError("Non-local gateway URL must use TLS (wss://)")

    return ws_url


def get_gateway_token() -> str:
    """Read gateway token from environment at request time."""
    return os.getenv("OPENCLAW_GATEWAY_TOKEN", "")


def is_ws_api_key_valid(request: web.Request) -> bool:
    """Validate websocket API key query parameter when auth is configured."""
    configured_key = request.app[DASH_API_KEY_KEY]
    if not configured_key:
        return True
    return request.query.get("key", "") == configured_key


def is_origin_allowed(request: web.Request) -> bool:
    """Validate websocket Origin header with fail-closed defaults."""
    if os.getenv("DASHBOARD_DEV_MODE") == "1":
        return True

    raw_allowed_origins = os.getenv("DASH_ALLOWED_ORIGINS", "")
    if not raw_allowed_origins.strip():
        return False

    origin = request.headers.get("Origin", "").strip()
    if not origin:
        return False

    parsed_origin = urlparse(origin)
    origin_host = (parsed_origin.hostname or "").lower()
    origin_host_port = (parsed_origin.netloc or "").lower()
    allowed_origins = {
        entry.strip().lower() for entry in raw_allowed_origins.split(",") if entry.strip()
    }

    if origin_host in allowed_origins or origin_host_port in allowed_origins:
        return True
    return origin.lower() in allowed_origins


def extract_history_messages(payload):
    """Normalize chat.history response payload to a list of messages."""
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        return payload["messages"]
    if isinstance(payload, list):
        return payload
    return []


def extract_history_text(message):
    """Extract text from a history message object."""
    if not isinstance(message, dict):
        return str(message)
    for key in ("text", "message", "content", "delta"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    content = message.get("content")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        if parts:
            return "".join(parts)
    return ""


async def perform_gateway_handshake(gateway_ws, gateway_token: str):
    """Wait for challenge and complete connect handshake with the gateway."""
    challenge = await gateway_ws.receive(timeout=10)
    if challenge.type != aiohttp.WSMsgType.TEXT:
        raise RuntimeError("Gateway did not send connect challenge")

    challenge_data = json.loads(challenge.data)
    if challenge_data.get("type") != "event" or challenge_data.get("event") != "connect.challenge":
        raise RuntimeError("Unexpected handshake frame from gateway")

    connect_id = f"connect-{uuid.uuid4().hex[:8]}"
    await gateway_ws.send_json(
        {
            "type": "req",
            "id": connect_id,
            "method": "connect",
            "params": {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "gateway-client",
                    "version": "1.0.0",
                    "platform": "web",
                    "mode": "backend",
                },
                "role": "operator",
                "scopes": ["operator.admin"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "auth": {"token": gateway_token},
                "locale": "en-US",
                "userAgent": "dashboard-chat/1.0.0",
            },
        }
    )

    while True:
        frame = await gateway_ws.receive(timeout=10)
        if frame.type != aiohttp.WSMsgType.TEXT:
            raise RuntimeError("Gateway closed during handshake")

        data = json.loads(frame.data)
        if data.get("type") == "res" and data.get("id") == connect_id:
            if not data.get("ok"):
                raise RuntimeError("Gateway connect request rejected")
            return


def extract_chat_event_text(payload):
    """Extract text from a gateway chat event payload."""
    msg = payload.get("message")
    if not isinstance(msg, dict):
        return ""
    # Try content array first (standard format)
    content = msg.get("content")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text", "")
                if t:
                    parts.append(t)
        return "".join(parts)
    # Fallback to plain text field
    text = msg.get("text")
    return text if isinstance(text, str) else ""


async def relay_chat_event(browser_ws, payload, stream_buffers):
    """Translate gateway chat events into browser websocket messages.

    Gateway deltas contain the FULL accumulated text, not incremental chunks.
    We track per-runId what we've already sent and forward only new content.
    """
    if not isinstance(payload, dict):
        return

    state = payload.get("state")
    run_id = payload.get("runId", "")
    text = extract_chat_event_text(payload)

    if state == "delta" and text:
        prev_len = stream_buffers.get(run_id, 0)
        if len(text) > prev_len:
            new_content = text[prev_len:]
            stream_buffers[run_id] = len(text)
            await browser_ws.send_json({"type": "stream", "delta": new_content})
    elif state == "final":
        stream_buffers.pop(run_id, None)
        if text:
            await browser_ws.send_json({"type": "reply", "text": text})
        await browser_ws.send_json({"type": "stream_end"})
    elif state == "aborted":
        stream_buffers.pop(run_id, None)
        await browser_ws.send_json({"type": "stream_end"})
    elif state == "error":
        stream_buffers.pop(run_id, None)
        error_msg = payload.get("errorMessage", "Agent error")
        await browser_ws.send_json({"type": "error", "text": error_msg})
        await browser_ws.send_json({"type": "stream_end"})


async def handle_chat_ws(request):
    """WebSocket proxy between dashboard browser and OpenClaw gateway."""
    if not is_ws_api_key_valid(request):
        return error_response("Unauthorized", status=401)

    if not is_origin_allowed(request):
        return error_response("Forbidden origin", status=403)

    browser_ws = web.WebSocketResponse(heartbeat=30)
    await browser_ws.prepare(request)

    gateway_token = get_gateway_token()
    if not gateway_token:
        await browser_ws.send_json(
            {"type": "error", "text": "OPENCLAW_GATEWAY_TOKEN is not configured on the server"}
        )
        await browser_ws.close()
        return browser_ws

    try:
        gateway_url = get_gateway_ws_url()
    except ValueError as exc:
        await browser_ws.send_json({"type": "error", "text": str(exc)})
        await browser_ws.close()
        return browser_ws
    outgoing_messages = asyncio.Queue(maxsize=200)
    gateway_ready = asyncio.Event()
    gateway_ref = {"ws": None, "history_req_id": None}
    pending_send_ids = set()
    gateway_lock = asyncio.Lock()
    pending_lock = asyncio.Lock()
    stop_event = asyncio.Event()
    message_timestamps = deque()
    stream_buffers = {}  # runId -> chars already sent (for incremental delta forwarding)

    async def send_browser_error(text):
        if not browser_ws.closed:
            await browser_ws.send_json({"type": "error", "text": text})

    async def gateway_manager():
        backoff = 1
        timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_connect=10, sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while not stop_event.is_set() and not browser_ws.closed:
                try:
                    gateway_ws = await session.ws_connect(
                        gateway_url, heartbeat=30, max_msg_size=1024 * 1024
                    )
                    await perform_gateway_handshake(gateway_ws, gateway_token)
                    history_req_id = f"history-{uuid.uuid4().hex[:8]}"
                    await gateway_ws.send_json(
                        {
                            "type": "req",
                            "id": history_req_id,
                            "method": "chat.history",
                            "params": {"sessionKey": "agent:main:main", "limit": 50},
                        }
                    )
                    async with gateway_lock:
                        gateway_ref["ws"] = gateway_ws
                        gateway_ref["history_req_id"] = history_req_id
                    gateway_ready.set()
                    await browser_ws.send_json({"type": "connected"})
                    backoff = 1

                    async for msg in gateway_ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                            continue
                        try:
                            data = json.loads(msg.data)
                        except json.JSONDecodeError:
                            continue

                        if data.get("type") == "event" and data.get("event") == "chat":
                            await relay_chat_event(browser_ws, data.get("payload", {}), stream_buffers)
                            continue

                        if data.get("type") == "res" and data.get("id") == gateway_ref.get("history_req_id"):
                            if data.get("ok"):
                                history = extract_history_messages(data.get("payload"))
                                normalized = []
                                for item in history:
                                    if not isinstance(item, dict):
                                        continue
                                    text = extract_history_text(item).strip()
                                    if not text:
                                        continue
                                    normalized.append(
                                        {
                                            "text": text,
                                            "timestamp": item.get("timestamp"),
                                            "role": item.get("role"),
                                        }
                                    )
                                await browser_ws.send_json({"type": "history", "messages": normalized})
                            continue

                        if data.get("type") == "res":
                            req_id = data.get("id")
                            async with pending_lock:
                                if req_id in pending_send_ids:
                                    pending_send_ids.discard(req_id)
                                    if data.get("ok"):
                                        await browser_ws.send_json({"type": "send_ok", "id": req_id})
                                    else:
                                        await browser_ws.send_json(
                                            {
                                                "type": "send_error",
                                                "id": req_id,
                                                "error": data.get("error") or data.get("payload") or "Send failed",
                                            }
                                        )
                            continue
                except Exception:
                    if not stop_event.is_set() and not browser_ws.closed:
                        await send_browser_error("Gateway disconnected, retrying...")
                finally:
                    gateway_ready.clear()
                    try:
                        if "gateway_ws" in locals() and gateway_ws is not None and not gateway_ws.closed:
                            await gateway_ws.close()
                    except Exception:
                        pass
                    async with gateway_lock:
                        gateway_ref["ws"] = None
                        gateway_ref["history_req_id"] = None

                if stop_event.is_set() or browser_ws.closed:
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5)

    async def sender_loop():
        while not stop_event.is_set() and not browser_ws.closed:
            message_text = await outgoing_messages.get()
            while not stop_event.is_set() and not browser_ws.closed:
                if not gateway_ready.is_set():
                    try:
                        await asyncio.wait_for(gateway_ready.wait(), timeout=1)
                    except asyncio.TimeoutError:
                        continue
                async with gateway_lock:
                    gateway_ws = gateway_ref["ws"]
                if gateway_ws is None:
                    await asyncio.sleep(0.1)
                    continue
                req_id = f"msg-{uuid.uuid4().hex[:8]}"
                try:
                    await gateway_ws.send_json(
                        {
                            "type": "req",
                            "id": req_id,
                            "method": "chat.send",
                            "params": {
                                "sessionKey": "agent:main:main",
                                "message": message_text,
                                "idempotencyKey": f"idem-{uuid.uuid4().hex[:8]}",
                            },
                        }
                    )
                    async with pending_lock:
                        pending_send_ids.add(req_id)
                    break
                except Exception:
                    gateway_ready.clear()
                    await asyncio.sleep(0.2)

    gateway_task = asyncio.create_task(gateway_manager())
    sender_task = asyncio.create_task(sender_loop())

    try:
        async for msg in browser_ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
                continue
            if len(msg.data.encode("utf-8")) > MAX_CHAT_MESSAGE_BYTES:
                await send_browser_error("Message too large")
                await browser_ws.close(code=aiohttp.WSCloseCode.MESSAGE_TOO_BIG)
                break

            now = time.monotonic()
            cutoff = now - CHAT_RATE_WINDOW_SECONDS
            while message_timestamps and message_timestamps[0] < cutoff:
                message_timestamps.popleft()
            if len(message_timestamps) >= MAX_CHAT_MESSAGES_PER_WINDOW:
                await send_browser_error("Rate limit exceeded")
                await browser_ws.close(code=aiohttp.WSCloseCode.POLICY_VIOLATION)
                break
            message_timestamps.append(now)
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                await send_browser_error("Invalid JSON message")
                continue

            message_text = str(data.get("message", "")).strip()
            if not message_text:
                continue

            chat_messages.append(
                {
                    "text": message_text,
                    "timestamp": int(time.time()),
                    "is_system": False,
                }
            )
            if len(chat_messages) > 50:
                chat_messages.pop(0)
            if outgoing_messages.full():
                try:
                    outgoing_messages.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            outgoing_messages.put_nowait(message_text)
    finally:
        stop_event.set()
        gateway_task.cancel()
        sender_task.cancel()
        await asyncio.gather(gateway_task, sender_task, return_exceptions=True)
        async with gateway_lock:
            gateway_ws = gateway_ref["ws"]
        if gateway_ws is not None and not gateway_ws.closed:
            await gateway_ws.close()
        if not browser_ws.closed:
            await browser_ws.close()

    return browser_ws


async def handle_get_chat_history(request):
    """Legacy REST chat history endpoint."""
    return web.json_response({"messages": chat_messages})


async def handle_startup(app):
    """Load state from disk on startup."""
    global cleanup_task
    await state._load()
    await app[NETWORK_TRACKER_KEY].start()

    # Start agent cleanup background task
    cleanup_task = asyncio.create_task(agent_cleanup_loop())
    print("Started agent cleanup background task")


async def handle_cleanup(app):
    """Stop background tasks."""
    global cleanup_task
    await app[NETWORK_TRACKER_KEY].stop()

    # Stop agent cleanup background task
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
        print("Stopped agent cleanup background task")


def create_app():
    """Create aiohttp application."""
    app = web.Application(middlewares=[api_error_middleware, auth_middleware])
    app[DASH_API_KEY_KEY] = os.getenv("DASHBOARD_API_KEY", "")
    app[NETWORK_TRACKER_KEY] = NetworkStatsTracker()

    # Root route
    app.router.add_get("/", handle_index)

    # API routes
    app.router.add_get("/api/sse", handle_sse)
    app.router.add_get("/api/agents", handle_get_agents)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/system", handle_system_stats)
    app.router.add_get("/api/chat/history", handle_get_chat_history)
    app.router.add_post("/api/agents", handle_add_agent)
    app.router.add_post("/api/agents/status", handle_update_status)
    app.router.add_post("/api/agents/remove", handle_remove_agent)
    app.router.add_post("/api/chat", handle_post_chat)
    app.router.add_get("/ws/chat", handle_chat_ws)

    # Static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.router.add_static("/static", static_dir, name="static")

    app.on_startup.append(handle_startup)
    app.on_cleanup.append(handle_cleanup)
    return app


if __name__ == "__main__":
    app = create_app()
    print("🚀 Agent Orchestration Dashboard")
    print("📡 Server running on http://localhost:8223")
    web.run_app(app, host="0.0.0.0", port=8223)
