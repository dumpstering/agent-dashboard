# Master Triage

Project: Agent Orchestration Dashboard (WebSocket chat integration)

## CRITICAL

### C1 - Hardcoded gateway token in repository startup path - FIXED
- **Location:** `start.sh:34`
- **Impact:** Credential exposure and potential unauthorized gateway access.
- **Fix:** Remove fallback secret; require explicit secure env provisioning.
- **Verification:** `OPENCLAW_GATEWAY_TOKEN` now uses strict required env expansion with no fallback secret.

## HIGH

### H1 - `/ws/chat` bypasses configured API auth - FIXED
- **Location:** `server.py:115`, `server.py:664`
- **Impact:** Authenticated deployment can still be used via unauthenticated chat WS endpoint.
- **Fix:** Enforce token/API-key validation on WS upgrade.
- **Verification:** WS endpoint enforces key validation when `DASH_API_KEY` is configured; production can rely on Cloudflare Access only when unset.

### H2 - Missing WebSocket Origin validation - FIXED
- **Location:** `server.py:466`
- **Impact:** Cross-site WebSocket hijacking risk in browser-based deployments.
- **Fix:** Validate `Origin` against allowlist before `prepare()`.
- **Verification:** Origin validation now rejects forbidden origins prior to WS upgrade.

### H3 - No WS contract tests for new integration - FIXED
- **Location:** `tests/test_api.py:1`
- **Impact:** Regressions in handshake/relay/reconnect path will not be caught pre-deploy.
- **Fix:** Add WS integration tests with mocked gateway protocol frames.
- **Verification:** WS handshake, send tracking, auth rejection, and origin rejection tests are present and passing.

### H4 - Unbounded WS message buffering enables memory DoS - FIXED
- **Location:** `server.py:479`, `server.py:620`
- **Impact:** Flooded/disconnected gateway path can accumulate unbounded queued messages.
- **Fix:** Bound queue size, enforce message size limit, throttle per connection.
- **Verification:** Outgoing queue is bounded, max message size is enforced, and per-connection inbound rate limiting is enforced.

## MEDIUM

### M1 - Potential plaintext gateway transport (`ws://`) - FIXED
- **Location:** `server.py:15`, `server.py:358`
- **Impact:** Token/chat data may traverse unencrypted channels outside localhost.
- **Fix:** Use `wss://` by default in non-local deployments; enforce TLS mode.
- **Verification:** Non-local `ws://` gateway URLs are rejected; non-local `http://` inputs normalize to `wss://`.

### M2 - `chat.send` responses are not tracked - FIXED
- **Location:** `server.py:576`
- **Impact:** Silent message delivery failures and weak reliability semantics.
- **Fix:** Correlate request IDs with gateway `res` frames and notify client.
- **Verification:** `send_ok` / `send_error` frames are emitted for tracked `chat.send` request IDs.

### M3 - WS chat prerequisites missing from README - FIXED
- **Location:** `README.md:40`
- **Impact:** Setup confusion; operators think no env vars are required.
- **Fix:** Document `OPENCLAW_GATEWAY_URL` + `OPENCLAW_GATEWAY_TOKEN`.
- **Verification:** README documents both required gateway env vars and clarifies optional local `DASH_API_KEY`.

### M4 - REST and WS chat paths have divergent semantics - FIXED
- **Location:** `server.py:325`, `server.py:466`, `static/index.html:1217`
- **Impact:** Confusing behavior when mixed clients use REST and WS chat.
- **Fix:** Pick one authoritative chat path or fully align and document both.
- **Verification:** WS is documented as canonical; REST endpoints are explicitly marked legacy compatibility.

### M5 - Missing SSE endpoint tests - FIXED
- **Location:** `server.py:655`, `tests/test_api.py:1`
- **Impact:** Event schema regressions can ship undetected.
- **Fix:** Add stream tests for `agents` and `system` events.
- **Verification:** New SSE test validates initial `agents` and `system` event frames.

## LOW

### L1 - Generic error reporting limits troubleshooting
- **Location:** `server.py:548`, `server.py:178`, `static/index.html:1032`
- **Impact:** Harder incident diagnosis.
- **Fix:** Structured error codes and minimal server-side sanitized logging.

## Immediate Priority Order
1. L1 follow-up (optional)
