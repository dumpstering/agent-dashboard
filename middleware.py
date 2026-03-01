"""Shared middleware and API helpers."""
import os
from urllib.parse import urlparse

from aiohttp import web


DASH_API_KEY_KEY = web.AppKey("dash_api_key", str)
MUTATING_METHODS = {"POST", "PUT", "DELETE"}
MAX_JSON_BODY_BYTES = 1 * 1024 * 1024
FIELD_MAX_LENGTHS = {
    "id": 64,
    "project": 256,
    "task": 1024,
    "message": 10000,
}


def error_response(message: str, status: int = 400) -> web.Response:
    """Create normalized API error payload."""
    return web.json_response({"success": False, "error": message}, status=status)


def get_api_key(request: web.Request) -> str:
    """Extract API key from common headers."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return ""


def is_dev_mode_enabled() -> bool:
    """Check whether dashboard dev mode is active."""
    return os.getenv("DASHBOARD_DEV_MODE") == "1"


def requires_api_auth(request: web.Request) -> bool:
    """Return True when this request must satisfy API auth policy."""
    if not request.path.startswith("/api/"):
        return False
    if request.method in MUTATING_METHODS:
        return True
    return request.method == "GET" and request.path == "/api/chat/history"


def is_ws_api_key_valid(request: web.Request) -> bool:
    """Validate websocket API key query parameter when auth is configured."""
    configured_key = request.app[DASH_API_KEY_KEY]
    if not configured_key:
        return True
    return request.query.get("key", "") == configured_key


def is_origin_allowed(request: web.Request) -> bool:
    """Validate websocket Origin header with fail-closed defaults."""
    if is_dev_mode_enabled():
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

    for field, max_len in FIELD_MAX_LENGTHS.items():
        if field not in data:
            continue
        if len(str(data[field])) > max_len:
            return None, error_response(
                f"Field '{field}' exceeds maximum length ({max_len})",
                status=400,
            )

    return data, None


@web.middleware
async def auth_middleware(request, handler):
    """API auth policy for protected dashboard routes."""
    if requires_api_auth(request):
        configured_key = request.app[DASH_API_KEY_KEY]
        if configured_key:
            provided_key = get_api_key(request)
            if provided_key != configured_key:
                return error_response("Unauthorized", status=401)
        elif not is_dev_mode_enabled():
            return error_response("Forbidden", status=403)

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
