"""Chat REST and websocket route registration."""
import time

from aiohttp import web

from middleware import error_response

from .connection import MAX_CHAT_MESSAGE_BYTES, create_chat_ws_handler


__all__ = ["MAX_CHAT_MESSAGE_BYTES", "register_routes"]


def register_routes(app: web.Application, chat_messages: list, parse_json, broadcast_event):
    """Register chat routes."""

    async def handle_post_chat(request):
        """Legacy REST chat endpoint: add a chat message and broadcast via SSE."""
        data, error = await parse_json(request, required_fields=["message"])
        if error:
            return error

        message_text = str(data.get("message", "")).strip()
        if not message_text:
            return error_response("Message cannot be empty", status=400)

        msg = {
            "text": message_text,
            "timestamp": int(time.time()),
            "is_system": False,
        }
        chat_messages.append(msg)
        if len(chat_messages) > 50:
            chat_messages.pop(0)

        await broadcast_event("chat", msg)

        return web.json_response({"success": True})

    async def handle_get_chat_history(request):
        """Legacy REST chat history endpoint."""
        return web.json_response({"messages": chat_messages})

    app.router.add_get("/api/chat/history", handle_get_chat_history)
    app.router.add_post("/api/chat", handle_post_chat)
    app.router.add_get("/ws/chat", create_chat_ws_handler(chat_messages))
