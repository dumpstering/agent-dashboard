# QA Review (Final, Round 4)

Date: 2026-03-01
Baseline: `c0a3930`
Reviewed commits: `c2b7eca`..`9fb93fc` (all commits since baseline)
Reviewed changed files:
- `projects/dashboard/.github/workflows/ci.yml`
- `projects/dashboard/Makefile`
- `projects/dashboard/README.md`
- `projects/dashboard/requirements-dev.txt`
- `projects/dashboard/requirements.txt`
- `projects/dashboard/.codex/*` (agent config only; no runtime impact)

Required regression run:
- `python3 -m pytest tests/ -q` -> **28 passed**

Additional ops validation:
- `make setup` (system Python) -> fails on this machine due PEP 668 externally-managed environment
- `make setup` (inside local venv) -> pass
- `make lint` -> **fails** (3 unused-import violations in `server.py`)
- `make typecheck` -> **fails** (10 mypy errors across `state.py`, `routes/system.py`, `server.py`, `tests/test_api.py`, `test_agents.py`)
- `make security` -> pass (bandit: no issues identified)

## Final Status of 12 Original Findings

1. **H1 Insecure-by-default WebSocket origin policy**: **FIXED**
- Origin validation remains fail-closed outside dev mode (`middleware.py`).
- Regression coverage still passes in `tests/test_api.py`.

2. **H2 Mutating API unauthenticated by default**: **FIXED**
- Auth gating remains fail-closed when key is unset outside dev mode (`middleware.py`).
- Keyed/fail-closed paths remain covered and green.

3. **H3 Test suite red**: **FIXED**
- Required suite passes: `python3 -m pytest tests/ -q` -> **28 passed**.

4. **H4 Monolithic architecture fragility**: **FIXED**
- Route decomposition and stylesheet extraction introduced in prior round remain intact.

5. **H5 Documentation trust-model contradictions**: **FIXED**
- Security and auth model documentation remains consistent with code behavior.

6. **M1 Non-atomic state persistence**: **FIXED**
- Atomic write/replace behavior and cleanup path remain present and tested.

7. **M2 Missing cleanup/tmux lifecycle tests**: **FIXED**
- Lifecycle cleanup coverage remains in place and green.

8. **M3 No request body/field size caps on JSON APIs**: **FIXED**
- Request/body field caps remain enforced with passing tests.

9. **M4 Chat history endpoint leaks operator messages by default**: **FIXED**
- Chat history remains auth-protected in non-dev mode with passing tests.

10. **M5 Startup script lacks port/process preflight**: **FIXED**
- Preflight occupancy checks remain present in `start.sh`.

11. **M6 No standardized lint/type/security command pipeline**: **PARTIAL (still open)**
- Improvement: `requirements-dev.txt`, `make setup`, `make ci`, and CI workflow now exist.
- Remaining closure gap: documented local pipeline is still not green because `make lint` and `make typecheck` fail on current codebase.

12. **M7 Missing threat model + deployment runbook docs**: **FIXED**
- Threat model and deployment runbook remain present and aligned.

## Root-Cause and Coverage Verdict

- Root-cause closure: **11/12 fixed, 1 partial (M6)**.
- The specific claim "all 12 fixed" is not yet true in practice because lint/type gates fail.
- Runtime behavior and security controls remain strongly covered by tests.
- Residual gap: no automated tests for shell workflow (`start.sh`) execution paths.

## Round 4 Decision

- **Not ready for 95+ / final sign-off yet.**
- Required to close Round 4: make `make ci` pass end-to-end (`setup + lint + typecheck + security + test`) in a clean venv workflow.
