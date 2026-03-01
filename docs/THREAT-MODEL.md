# Threat Model

## Scope

This model covers the dashboard service in this repository:
- `server.py` (HTTP + WebSocket API)
- `state.py` (JSON-backed agent state persistence)
- `start.sh` runtime bootstrap
- `static/` dashboard frontend

## Assets

- API credentials (`DASHBOARD_API_KEY`, `OPENCLAW_GATEWAY_TOKEN`)
- Agent state and metadata in `agents.json`
- Chat history retained in server memory
- Availability of dashboard API and WebSocket paths

## Trust Boundaries

- Browser client to dashboard server (`/api/*`, `/ws/chat`)
- Dashboard server to OpenClaw gateway (`OPENCLAW_GATEWAY_URL`)
- Dashboard process to local OS (tmux inspection + filesystem writes)

## Threats

1. Unauthorized API mutation
- Risk: unauthenticated POSTs modify agent state.
- Existing controls: optional API key middleware.

2. Cross-site WebSocket abuse
- Risk: attacker origin opens dashboard WS and sends messages.
- Existing controls: origin allow-list check in `is_origin_allowed`.

3. Credential leakage
- Risk: tokens exposed via shell history, process lists, logs, or commit history.
- Existing controls: env-based config, no token response fields.

4. State tampering/corruption
- Risk: malformed writes or concurrent updates damage `agents.json`.
- Existing controls: lock-protected writes and atomic replace in `state.py`.

5. Resource exhaustion / DoS
- Risk: excessive WS/API traffic or large payloads degrades service.
- Existing controls: WS rate limiting and message-size cap.

6. Dependency/runtime drift
- Risk: deploy uses unexpected Python/aiohttp version and behavior changes.
- Existing controls: pinned versions in `requirements.txt` (when followed).

## Assumptions

- Dashboard runs behind a trusted network perimeter or reverse proxy.
- Production deploy sets strong non-default secrets.
- Host-level controls protect filesystem/process access.

## Required Minimum Controls

- Set `DASHBOARD_API_KEY` in non-dev environments.
- Set explicit `DASH_ALLOWED_ORIGINS` to trusted dashboard origins.
- Use `wss://` for non-local gateway URLs.
- Restrict dashboard port exposure to expected networks.
- Keep dependencies pinned and updated intentionally.
- Monitor error rates and reconnect loops for gateway failures.

## Residual Risk

- In-memory chat history is not encrypted and is process-accessible.
- Local machine compromise can bypass application-layer controls.
- Availability can still be impacted by upstream gateway outages.

