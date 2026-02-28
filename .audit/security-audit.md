# Security Audit

Score: **2/5 (Poor)**

Scope focus: WebSocket auth, injection/input safety, CORS/origin controls, gateway token handling.

## Findings

### CRITICAL - Hardcoded default gateway token in startup script
- **File:Line:** `start.sh:34`
- **What is wrong:** `OPENCLAW_GATEWAY_TOKEN` is given a hardcoded fallback secret in source. This is credential exposure and can lead to unauthorized gateway access if reused.
- **Suggested fix:** Remove hardcoded token fallback. Require explicit env injection (`export OPENCLAW_GATEWAY_TOKEN=...`) and fail fast with clear startup error when missing.

### HIGH - WebSocket endpoint bypasses API key enforcement
- **File:Line:** `server.py:115`, `server.py:664`
- **What is wrong:** Auth middleware protects only `POST /api/*`. `GET /ws/chat` is unauthenticated even when `DASH_API_KEY` is configured, creating a protected-surface bypass for chat operations.
- **Suggested fix:** Enforce auth on `/ws/chat` during handshake using `X-API-Key`/Bearer token validation (or move to global auth gate for all sensitive routes).

### HIGH - No Origin validation on browser WebSocket handshake (CSWSH risk)
- **File:Line:** `server.py:466`, `server.py:469`
- **What is wrong:** Server accepts any incoming WebSocket upgrade without checking `Origin`. A malicious site can attempt cross-site WS use from a victim browser in some deployment models.
- **Suggested fix:** Validate `Origin` against an allowlist before `prepare()`. Reject mismatched origins with 403.

### HIGH - No message length/rate limits and unbounded outbound queue
- **File:Line:** `server.py:479`, `server.py:607`, `server.py:620`
- **What is wrong:** Browser can send unlimited-sized messages and unlimited count; `outgoing_messages = asyncio.Queue()` has no max size. Under gateway outages or slowdowns this can exhaust memory.
- **Suggested fix:** Add max payload length and queue `maxsize`, reject/close on abuse, and add per-connection rate limiting.

### MEDIUM - Default gateway URL may downgrade to plaintext WS
- **File:Line:** `server.py:15`, `server.py:358`, `server.py:359`
- **What is wrong:** Default URL is `http://...` and conversion logic maps to `ws://` (plaintext). Gateway auth token and chat content can traverse unencrypted links in non-local deployments.
- **Suggested fix:** Prefer `https://`/`wss://` by default outside localhost, or enforce secure transport in production mode.

### LOW - Broad exception swallowing reduces security observability
- **File:Line:** `server.py:546`, `server.py:178`
- **What is wrong:** Exceptions in key loops are swallowed with generic behavior; incidents are hard to detect and triage.
- **Suggested fix:** Log sanitized exception class/context with connection identifiers.
