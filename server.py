"""Agent orchestration dashboard server."""
import asyncio
import os
from pathlib import Path
import subprocess

from aiohttp import web

import cleanup as cleanup_tasks
from middleware import (
    DASH_API_KEY_KEY,
    MAX_JSON_BODY_BYTES,
    api_error_middleware,
    auth_middleware,
    parse_json,
)
from routes.agents import register_routes as register_agent_routes
from routes.chat import register_routes as register_chat_routes
from routes.system import register_routes as register_system_routes
from state import AgentState, NetworkStatsTracker


NETWORK_TRACKER_KEY = web.AppKey("network_tracker", NetworkStatsTracker)


# Global state
state = AgentState()
sse_clients: set[web.StreamResponse] = set()
chat_messages: list[dict[str, object]] = []  # Store chat messages in memory
cleanup_task = None  # Background cleanup task
_send_sse_update_impl = None
_broadcast_event_impl = None


async def send_sse_update():
    """Broadcast agent/system SSE updates via the registered route callback."""
    if _send_sse_update_impl is not None:
        await _send_sse_update_impl()


async def broadcast_event(event_name: str, payload):
    """Broadcast a typed SSE event via the registered route callback."""
    if _broadcast_event_impl is not None:
        await _broadcast_event_impl(event_name, payload)


def check_tmux_session(session_name: str) -> tuple[bool, int | None]:
    """Check if tmux session exists and get its exit code if dead.

    Returns:
        (is_alive, exit_code) where exit_code is None if session is alive,
        0 if exited successfully, or non-zero if failed/killed.
    """
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, None

        list_result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name} #{pane_dead} #{pane_dead_status}"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if list_result.returncode == 0:
            for line in list_result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[0] == session_name and parts[1] == "1":
                    try:
                        exit_code = int(parts[2])
                        return False, exit_code
                    except ValueError:
                        pass

        return False, 1

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, 1


async def cleanup_stale_agents():
    """Compatibility wrapper used by tests for one cleanup sweep."""
    await cleanup_tasks.cleanup_stale_agents(state, send_sse_update, check_tmux_session)


async def agent_cleanup_loop():
    """Compatibility wrapper used by tests for the background cleanup loop."""
    await cleanup_tasks.agent_cleanup_loop(state, send_sse_update, check_tmux_session)


async def handle_startup(app):
    """Load state from disk and start background tasks."""
    global cleanup_task
    await state._load()
    await app[NETWORK_TRACKER_KEY].start()
    cleanup_task = asyncio.create_task(agent_cleanup_loop())
    print("Started agent cleanup background task")


async def handle_cleanup(app):
    """Stop background tasks."""
    global cleanup_task
    await app[NETWORK_TRACKER_KEY].stop()

    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
        print("Stopped agent cleanup background task")


def create_app():
    """Create aiohttp application."""
    global _broadcast_event_impl, _send_sse_update_impl

    app = web.Application(
        middlewares=[api_error_middleware, auth_middleware],
        client_max_size=MAX_JSON_BODY_BYTES,
    )
    app[DASH_API_KEY_KEY] = os.getenv("DASHBOARD_API_KEY", "")
    app[NETWORK_TRACKER_KEY] = NetworkStatsTracker()

    register_system_routes(app, state=state, network_tracker_key=NETWORK_TRACKER_KEY)
    _send_sse_update_impl, _broadcast_event_impl = register_agent_routes(
        app,
        state=state,
        sse_clients=sse_clients,
        parse_json=parse_json,
    )
    register_chat_routes(
        app,
        chat_messages=chat_messages,
        parse_json=parse_json,
        broadcast_event=broadcast_event,
    )

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
