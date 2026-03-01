# Architecture Audit - Agent Orchestration Dashboard

Date: 2026-03-01

## Executive Summary
The system works as a pragmatic single-process tool, but architecture is brittle: global mutable state, high coupling, and mixed responsibilities in one module impede reliability, scale, and safe iteration.

Score: **50/100**

## High Findings

### H1 - God-module server design
Evidence:
- `server.py` is ~919 lines handling API, SSE, WS proxy, tmux lifecycle, and system metrics.

Impact:
- High change risk, weak isolation, difficult review/testing.

Recommendation:
- Split into `api_routes.py`, `chat_proxy.py`, `sse.py`, `cleanup.py`, `app_factory.py`.

### H2 - Global mutable runtime state
Evidence:
- Globals: `state`, `sse_clients`, `chat_messages`, `cleanup_task` (`server.py:27-31`).

Impact:
- Prevents multi-worker safety and complicates test determinism.

Recommendation:
- Store dependencies in `app[...]` context; eliminate module globals.

## Medium Findings

### M1 - Persistence is non-atomic and corruption-prone
Evidence:
- `state.py:64` writes directly to `agents.json` without atomic temp+rename.
- `state.py:56-58` silently resets memory state on load failure.

Impact:
- Crash during write can corrupt state; silent reset loses operational data.

Recommendation:
- Atomic writes (`NamedTemporaryFile` + `os.replace`) and backup/rollback on parse failure.

### M2 - Implicit coupling to tmux session naming
Evidence:
- Cleanup assumes `agent.id == tmux session name` (`server.py:95`).

Impact:
- False transitions when naming diverges.

Recommendation:
- Persist explicit `runtime_ref` for tmux session id.

### M3 - Cleanup logic treats missing tmux as failed agent
Evidence:
- `server.py:81-83` returns dead/error when tmux unavailable.

Impact:
- Operational false negatives on hosts without tmux or during command timeout.

Recommendation:
- Distinguish "unknown/infra error" from "agent failed".

### M4 - Transport contracts are not versioned
Evidence:
- WS/SSE payload parsing is ad-hoc (`server.py` + `static/index.html`).

Impact:
- Contract drift caused test failure.

Recommendation:
- Introduce protocol version + typed schemas.

## Strengths
- Locking around state operations (`state.py:40`, `68`, `83`, `97`, `106`, `111`).
- Good error normalization for API routes (`server.py:211-227`).

## Architecture Direction
1. Introduce app-context dependency injection.
2. Define typed message schema (Pydantic/dataclasses).
3. Isolate persistence and transport layers.
