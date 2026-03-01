# Commands Audit - Agent Orchestration Dashboard

Date: 2026-03-01

Score: **48/100**

## Findings

### H1 - Startup command flow is not deployment-safe
Evidence:
- `start.sh` always installs deps (`start.sh:21-23`) and starts server without port/process checks (`start.sh:37`).
- Runtime probe showed port conflict condition on 8223.

Impact:
- Repeated installs slow startup and can introduce nondeterminism; port conflicts cause failed boots.

Recommendation:
- Add preflight: venv check, pinned lock verification, port conflict detection, clear failure messages.

### M1 - No canonical task runner
Evidence:
- No `Makefile`, `justfile`, or npm scripts.

Impact:
- Inconsistent operator workflows and onboarding friction.

Recommendation:
- Add `make`/`just` commands: `setup`, `run`, `test`, `lint`, `smoke`, `audit`.

### M2 - Missing lint/type/security scan commands
Evidence:
- Repo lacks ruff/mypy/bandit/pip-audit command paths.

Impact:
- Quality/security checks are ad hoc.

Recommendation:
- Add a `scripts/check.sh` pipeline and CI hook.

### M3 - Requirements pinning lacks hash integrity
Evidence:
- `requirements.txt` pins versions but no hashes/lockfile.

Impact:
- Supply-chain reproducibility risk.

Recommendation:
- Generate locked hashes (`pip-compile --generate-hashes`) for production.

### L1 - Explicit gateway token requirement in startup script
Evidence:
- `start.sh:34` hard-fails if `OPENCLAW_GATEWAY_TOKEN` missing.

Impact:
- Good guardrail.
