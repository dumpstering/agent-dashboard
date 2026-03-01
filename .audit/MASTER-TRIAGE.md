# MASTER TRIAGE (H/M/L)

Date: 2026-03-01
Scope: full codebase audit

## High Priority (Fix First)

1. **[H] Insecure-by-default WebSocket origin policy**
- Evidence: `server.py:472-474`, `server.py:626-630`
- Risk: CSWSH/unauthorized WS use if env not set
- Owner: Backend
- Target: 24-48h

2. **[H] Mutating API unauthenticated by default**
- Evidence: `server.py:199-208`, `server.py:899-902`
- Risk: Unauthorized state mutation when perimeter controls fail
- Owner: Backend
- Target: 24-48h

3. **[H] Test suite currently red (release gate broken)**
- Evidence: `pytest -q` => 1 failed, 15 passed; failing test at `tests/test_api.py:293`
- Risk: Undetected regressions
- Owner: QA/Backend
- Target: same day

4. **[H] Monolithic architecture (server + UI) driving fragility**
- Evidence: `server.py` (~919 lines), `static/index.html` (~1344 lines)
- Risk: High regression likelihood and low change velocity
- Owner: Platform
- Target: short-term refactor plan this sprint

5. **[H] Documentation trust-model contradictions**
- Evidence: `PROJECT.md:13-15` vs `README.md` + `server.py`
- Risk: Incorrect security decisions by contributors
- Owner: Docs + Backend
- Target: same day

## Medium Priority

1. **[M] Non-atomic state persistence can corrupt `agents.json`** (`state.py:64`)
2. **[M] Missing tests for cleanup/tmux lifecycle paths** (`server.py:39-121`)
3. **[M] No request body/field size caps on JSON APIs** (`server.py:136-151`)
4. **[M] Chat history endpoint leaks operator messages by default** (`server.py:856-858`)
5. **[M] Startup script lacks port/process preflight** (`start.sh:21-37`)
6. **[M] No standardized lint/type/security command pipeline**
7. **[M] Missing threat model + deployment runbook docs**

## Low Priority

1. **[L] Cleanup loop logging is print-based, not structured**
2. **[L] Tests use private aiohttp internals (`_server`)** (`tests/test_api.py:278`)
3. **[L] Legacy REST chat endpoints add maintenance overhead** (`server.py:403-429`, `856-858`)

## Recommended Sequencing

1. Security defaults + startup validation (H1/H2/H5)
2. Fix failing WS protocol test and add cleanup tests (H3 + M2)
3. Persistence hardening + input limits (M1 + M3)
4. Refactor plan for module decomposition (H4)
5. Command/tooling standardization + docs runbooks (M5-M7)
