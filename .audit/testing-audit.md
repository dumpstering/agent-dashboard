# Testing Audit - Agent Orchestration Dashboard

Date: 2026-03-01
Command run: `pytest -q`
Result: **1 failed, 15 passed**

Score: **45/100**

## High Findings

### H1 - CI-breaking failing test in current suite
Evidence:
- Failure in `tests/test_api.py::TestChatWebSocket::test_ws_connect_send_and_response_tracking`.
- Test gateway emits `{"payload":{"delta":"pong","done":true}}` (`tests/test_api.py:266`) but server expects `state/message.content` (`server.py:590-621`).

Impact:
- Test suite is currently unreliable as a release gate.

Recommendation:
- Align fixtures to current gateway protocol and add compatibility test matrix.

### H2 - No tests for stale-agent cleanup behavior
Evidence:
- No coverage for `cleanup_stale_agents`, `check_tmux_session`, `agent_cleanup_loop` (`server.py:39-121`).

Impact:
- Regression risk in core orchestration correctness.

Recommendation:
- Add unit tests with mocked subprocess outcomes and time-based loop control.

## Medium Findings

### M1 - Security configuration paths under-tested
Evidence:
- Partial tests for origin/key rejection exist, but no startup/config invariants for production hardening.

Recommendation:
- Add tests for fail-closed startup when required env vars are missing in production mode.

### M2 - No browser-level integration tests
Evidence:
- Only aiohttp test client coverage; no frontend E2E for SSE+WS interaction.

Recommendation:
- Add Playwright smoke tests for connect/reconnect/chat render/agent updates.

### M3 - Deterministic test script is outside automated suite
Evidence:
- `test_agents.py` is useful but not integrated into CI pipeline.

Recommendation:
- Convert into pytest integration cases or invoke from CI target.

### M4 - Tests rely on private aiohttp server internals
Evidence:
- `tests/test_api.py:278` uses `self.gateway_site._server.sockets[0]`.

Recommendation:
- Wrap gateway startup in helper returning bound URL via supported API.

## Positive Coverage
- CRUD/status/error contracts are well exercised.
- Auth rejection/acceptance basics are covered.
