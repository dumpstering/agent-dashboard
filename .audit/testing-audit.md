# Testing Audit

Score: **2/5 (Poor)**

Scope focus: WS endpoint coverage, contract tests for new chat integration, security tests.

## Findings

### HIGH - No automated tests for `/ws/chat`
- **File:Line:** `tests/test_api.py:1`
- **What is wrong:** Test suite covers REST endpoints only; there are no WebSocket tests for connect, history bootstrap, stream deltas, reply frames, or reconnect behavior.
- **Suggested fix:** Add async WS tests using `aiohttp` test server + mock gateway to validate handshake, relay mapping, and reconnect flow.

### HIGH - No tests for WS auth/origin protections
- **File:Line:** `tests/test_api.py:159`
- **What is wrong:** Auth tests validate only POST `/api/*`; no equivalent checks exist for `/ws/chat` under `DASH_API_KEY`.
- **Suggested fix:** Add tests asserting unauthorized WS upgrade rejection and origin allowlist behavior.

### MEDIUM - No negative protocol tests for malformed gateway frames
- **File:Line:** `server.py:396`, `server.py:432`
- **What is wrong:** Handshake and runtime frame parsing rely on JSON frames but tests do not cover malformed/nonconforming gateway payloads.
- **Suggested fix:** Add contract tests for invalid gateway messages and verify graceful client-facing errors.

### MEDIUM - SSE contract not covered despite active endpoint
- **File:Line:** `server.py:655`
- **What is wrong:** `/api/sse` behavior (event shapes, initial snapshot) is not validated in current suite.
- **Suggested fix:** Add event-stream tests for `agents` and `system` event contracts.

## What currently passes
- `tests/test_api.py` validates REST CRUD, status transitions, normalized errors, and POST auth behavior.
- Local run: `source venv/bin/activate && PYTHONPATH=. pytest -q tests/test_api.py` -> **10 passed**.
