# QA Review (Post-Audit)

Date: 2026-03-01
Baseline: `692dc29`
Reviewed commits: `a618e7c`..`8f3df5e`
Test run: `python3 -m pytest tests/ -q` -> **21 passed**

## Findings Status

1. **H1 Insecure-by-default WebSocket origin policy**: **FIXED**
- Root cause: WS origin gate allowed upgrades when `DASH_ALLOWED_ORIGINS` was unset.
- Verification: `is_origin_allowed` now fails closed unless `DASHBOARD_DEV_MODE=1` (`server.py:475-498`).
- Regression check: WS tests still pass, including forbidden origin rejection (`tests/test_api.py:363-371`).
- Test coverage: Present, but missing an explicit test for "unset allowlist -> reject".

2. **H2 Mutating API unauthenticated by default**: **PARTIAL**
- Root cause addressed: env var mismatch fixed (`DASHBOARD_API_KEY` now wired in `create_app`, `server.py:894`).
- Remaining gap: auth remains optional when key is unset (`auth_middleware`, `server.py:205-213`), so mutating APIs are still unauthenticated by default.
- Regression check: keyed auth path works (`tests/test_api.py:201-227`).
- Test coverage: covers keyed enforcement; does not enforce fail-closed default behavior.

3. **H3 Test suite red**: **FIXED**
- Root cause: websocket contract test instability and aiohttp private internals usage were corrected (`ebab068`).
- Verification: requested suite now green (`21 passed`).
- Regression check: WS integration behavior still covered (`tests/test_api.py:325-396`).
- Test coverage: improved and passing.

4. **H4 Monolithic architecture fragility**: **OPEN**
- Root cause: large `server.py` and `static/index.html` remain monolithic; no decomposition/refactor plan landed in reviewed commits.
- Regression check: no architecture regression observed, but maintainability risk persists.
- Test coverage: N/A for structural refactor (none added).

5. **H5 Documentation trust-model contradictions**: **FIXED**
- Root cause: docs now align API key env var and trust model (`README.md`, `PROJECT.md`; commits `cffecb4`, `35f21a3`).
- Regression check: docs are consistent with backend auth wiring and WS origin model.
- Test coverage: N/A (documentation-only).

6. **M1 Non-atomic state persistence**: **FIXED**
- Root cause: direct write replaced with temp-file + `os.replace` atomic swap (`state.py:62-73`).
- Regression check: persistence logic still invoked under lock; no behavioral regression observed in API tests.
- Test coverage: no direct atomic-write failure-path test yet.

7. **M2 Missing cleanup/tmux lifecycle tests**: **FIXED**
- Root cause: lifecycle paths lacked unit tests.
- Verification: dedicated coverage added for tmux session checks and stale-agent cleanup transitions (`tests/test_lifecycle.py:11-77`).
- Regression check: existing API tests remain green.
- Test coverage: added and passing.

8. **M3 No request body/field size caps on JSON APIs**: **PARTIAL**
- Root cause partially addressed: 1 MB body cap added in `parse_json` (`server.py:137-156`).
- Remaining gap: no field-level length caps (`id`, `project`, `task`, `message`) and no app-wide `client_max_size`.
- Regression check: JSON parsing behavior unchanged for normal payloads.
- Test coverage: no explicit tests for 413 body-limit behavior.

9. **M4 Chat history endpoint leaks operator messages by default**: **OPEN**
- Root cause persists: `GET /api/chat/history` still returns full in-memory history without auth gating (`server.py:863-866`).
- Regression check: no new controls landed in reviewed commits.
- Test coverage: only happy-path history retrieval (`tests/test_api.py:120-130`), no access-control tests.

10. **M5 Startup script lacks port/process preflight**: **FIXED**
- Root cause addressed: startup script now checks port 8223 with `lsof`/`ss` before launch (`start.sh:29-39`).
- Regression check: startup behavior remains standard when port is free.
- Test coverage: no automated script test.

11. **M6 No standardized lint/type/security command pipeline**: **PARTIAL**
- Root cause partially addressed: `Makefile` adds `lint`, `test`, `typecheck` targets (`Makefile:1-10`).
- Remaining gap: no integrated security command/target in the pipeline.
- Regression check: command additions are non-breaking.
- Test coverage: N/A (ops/tooling).

12. **M7 Missing threat model + deployment runbook docs**: **FIXED**
- Root cause addressed: both docs added (`docs/THREAT-MODEL.md`, `docs/DEPLOYMENT.md`).
- Regression check: docs align with current runtime/env expectations.
- Test coverage: N/A (documentation-only).
