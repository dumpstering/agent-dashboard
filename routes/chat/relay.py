"""Browser relay helpers for chat websocket proxying."""

from .gateway import extract_history_messages, extract_history_text


def extract_chat_event_text(payload):
    """Extract text from a gateway chat event payload."""
    msg = payload.get("message")
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    parts.append(text)
        return "".join(parts)
    text = msg.get("text")
    return text if isinstance(text, str) else ""


def normalize_history(payload):
    """Normalize gateway history payload into browser-facing message objects."""
    history = extract_history_messages(payload)
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
    return normalized


async def relay_chat_event(browser_ws, payload, stream_buffers):
    """Translate gateway chat events into browser websocket messages."""
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
