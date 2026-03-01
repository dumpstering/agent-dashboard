"""Gateway protocol helpers for chat websocket proxying."""
import json
import os
import uuid
from urllib.parse import urlparse, urlunparse

import aiohttp


GATEWAY_SESSION_KEY = "agent:main:main"


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
