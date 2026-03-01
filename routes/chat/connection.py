"""Connection lifecycle for browser<->gateway chat websocket proxying."""
import asyncio
from collections import deque
import json
import time
import uuid

import aiohttp

from middleware import error_response, is_origin_allowed, is_ws_api_key_valid

from .gateway import (
    GATEWAY_SESSION_KEY,
    get_gateway_token,
    get_gateway_ws_url,
    perform_gateway_handshake,
)
from .relay import normalize_history, relay_chat_event


MAX_CHAT_MESSAGE_BYTES = 16 * 1024
MAX_CHAT_MESSAGES_PER_WINDOW = 30
CHAT_RATE_WINDOW_SECONDS = 10


def _append_chat_message(chat_messages: list, message_text: str):
    """Add a message to in-memory history while enforcing max length."""
    chat_messages.append(
        {
            "text": message_text,
            "timestamp": int(time.time()),
            "is_system": False,
        }
    )
    if len(chat_messages) > 50:
        chat_messages.pop(0)


async def _send_browser_error(browser_ws, text: str):
    if not browser_ws.closed:
        await browser_ws.send_json({"type": "error", "text": text})


async def _gateway_manager(
    browser_ws,
    gateway_url: str,
    gateway_token: str,
    gateway_ready: asyncio.Event,
    gateway_ref: dict,
    gateway_lock: asyncio.Lock,
    pending_send_ids: set,
    pending_lock: asyncio.Lock,
    stop_event: asyncio.Event,
    stream_buffers: dict,
):
    backoff = 1
    timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_connect=10, sock_read=None)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while not stop_event.is_set() and not browser_ws.closed:
            history_req_id = None
            gateway_ws = None
            try:
                gateway_ws = await session.ws_connect(gateway_url, heartbeat=30, max_msg_size=1024 * 1024)
                await perform_gateway_handshake(gateway_ws, gateway_token)

                history_req_id = f"history-{uuid.uuid4().hex[:8]}"
                await gateway_ws.send_json(
                    {
                        "type": "req",
                        "id": history_req_id,
                        "method": "chat.history",
                        "params": {"sessionKey": GATEWAY_SESSION_KEY, "limit": 50},
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
                        if msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
                        continue

                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue

                    if data.get("type") == "event" and data.get("event") == "chat":
                        await relay_chat_event(browser_ws, data.get("payload", {}), stream_buffers)
                        continue

                    if data.get("type") == "res" and data.get("id") == history_req_id:
                        if data.get("ok"):
                            await browser_ws.send_json(
                                {"type": "history", "messages": normalize_history(data.get("payload"))}
                            )
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
                                            "error": data.get("error")
                                            or data.get("payload")
                                            or "Send failed",
                                        }
                                    )
                        continue
            except Exception:
                if not stop_event.is_set() and not browser_ws.closed:
                    await _send_browser_error(browser_ws, "Gateway disconnected, retrying...")
            finally:
                gateway_ready.clear()
                try:
                    if gateway_ws is not None and not gateway_ws.closed:
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


async def _sender_loop(
    browser_ws,
    outgoing_messages: asyncio.Queue,
    gateway_ready: asyncio.Event,
    gateway_ref: dict,
    gateway_lock: asyncio.Lock,
    pending_send_ids: set,
    pending_lock: asyncio.Lock,
    stop_event: asyncio.Event,
):
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
                            "sessionKey": GATEWAY_SESSION_KEY,
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


def create_chat_ws_handler(chat_messages: list):
    """Build websocket handler bound to a shared in-memory chat store."""

    async def handle_chat_ws(request):
        """WebSocket proxy between dashboard browser and OpenClaw gateway."""
        if not is_ws_api_key_valid(request):
            return error_response("Unauthorized", status=401)

        if not is_origin_allowed(request):
            return error_response("Forbidden origin", status=403)

        browser_ws = aiohttp.web.WebSocketResponse(heartbeat=30)
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
        stream_buffers = {}

        gateway_task = asyncio.create_task(
            _gateway_manager(
                browser_ws=browser_ws,
                gateway_url=gateway_url,
                gateway_token=gateway_token,
                gateway_ready=gateway_ready,
                gateway_ref=gateway_ref,
                gateway_lock=gateway_lock,
                pending_send_ids=pending_send_ids,
                pending_lock=pending_lock,
                stop_event=stop_event,
                stream_buffers=stream_buffers,
            )
        )
        sender_task = asyncio.create_task(
            _sender_loop(
                browser_ws=browser_ws,
                outgoing_messages=outgoing_messages,
                gateway_ready=gateway_ready,
                gateway_ref=gateway_ref,
                gateway_lock=gateway_lock,
                pending_send_ids=pending_send_ids,
                pending_lock=pending_lock,
                stop_event=stop_event,
            )
        )

        try:
            async for msg in browser_ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        break
                    continue

                if len(msg.data.encode("utf-8")) > MAX_CHAT_MESSAGE_BYTES:
                    await _send_browser_error(browser_ws, "Message too large")
                    await browser_ws.close(code=aiohttp.WSCloseCode.MESSAGE_TOO_BIG)
                    break

                now = time.monotonic()
                cutoff = now - CHAT_RATE_WINDOW_SECONDS
                while message_timestamps and message_timestamps[0] < cutoff:
                    message_timestamps.popleft()
                if len(message_timestamps) >= MAX_CHAT_MESSAGES_PER_WINDOW:
                    await _send_browser_error(browser_ws, "Rate limit exceeded")
                    await browser_ws.close(code=aiohttp.WSCloseCode.POLICY_VIOLATION)
                    break
                message_timestamps.append(now)

                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    await _send_browser_error(browser_ws, "Invalid JSON message")
                    continue

                message_text = str(data.get("message", "")).strip()
                if not message_text:
                    continue

                _append_chat_message(chat_messages, message_text)
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

    return handle_chat_ws
