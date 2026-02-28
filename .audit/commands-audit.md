# Commands and Endpoints Audit

Score: **3/5 (Adequate)**

Scope focus: correctness of API routes and WS endpoint behavior.

## Route Inventory (observed)
- `GET /`
- `GET /api/sse`
- `GET /api/agents`
- `GET /api/stats`
- `GET /api/system`
- `GET /api/chat/history`
- `POST /api/agents`
- `POST /api/agents/status`
- `POST /api/agents/remove`
- `POST /api/chat`
- `GET /ws/chat`

## Findings

### HIGH - Endpoint protection inconsistency
- **File:Line:** `server.py:115`, `server.py:664`
- **What is wrong:** REST POST endpoints can be protected by API key, but WS chat endpoint remains open under the same deployment, creating inconsistent command surface protection.
- **Suggested fix:** Apply equivalent auth to `/ws/chat`.

### MEDIUM - WS endpoint is operationally dependent on undocumented env var
- **File:Line:** `server.py:471`, `README.md:42`
- **What is wrong:** `/ws/chat` immediately errors/closes without `OPENCLAW_GATEWAY_TOKEN`, but README states server can run with no env vars and does not document WS dependency.
- **Suggested fix:** Document required vars and startup behavior; optionally hide/disable chat UI when not configured.

### MEDIUM - Legacy `/api/chat` and WS chat can diverge state semantics
- **File:Line:** `server.py:325`, `server.py:466`, `static/index.html:1217`
- **What is wrong:** UI says chat is WS-only, but legacy REST chat remains active and writes local history independently from gateway-backed flow. Mixed clients can observe inconsistent histories.
- **Suggested fix:** Define one authoritative chat path. If REST is retained, synchronize semantics and document precedence.

## Verification notes
- REST contract tests pass (10/10) via `tests/test_api.py`.
- Runtime WS check confirms missing token behavior: server sends error then closes connection.
