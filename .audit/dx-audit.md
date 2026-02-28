# Developer Experience Audit

Score: **3/5 (Adequate)**

Scope focus: setup, debugging, errors, maintainability of new chat integration.

## Findings

### MEDIUM - Setup docs omit WS chat prerequisites
- **File:Line:** `README.md:40`
- **What is wrong:** Env var section documents `DASH_API_KEY` only; does not mention `OPENCLAW_GATEWAY_URL` and `OPENCLAW_GATEWAY_TOKEN` needed for live WS chat.
- **Suggested fix:** Add explicit WS chat prerequisite section with local/dev/prod examples.

### MEDIUM - Test invocation friction is undocumented
- **File:Line:** `README.md:359`
- **What is wrong:** README documents only deterministic script (`test_agents.py`), not unit tests. In this workspace, tests required `source venv/bin/activate` and `PYTHONPATH=.`.
- **Suggested fix:** Add a `Testing` section with exact commands and expected outcomes.

### LOW - Runtime chat errors are user-visible but not operator-friendly
- **File:Line:** `server.py:548`, `static/index.html:1032`
- **What is wrong:** Browser receives generic errors (`Gateway disconnected, retrying...`) without actionable reason codes for debugging.
- **Suggested fix:** Standardize error payload schema (`code`, `message`, `retryable`) and log correlation IDs server-side.

## Positive Notes
- Frontend reconnect behavior is clear and automatic (`static/index.html:1130`-`static/index.html:1176`).
- Input rendering uses `textContent`, reducing XSS risk in UI message rendering.
