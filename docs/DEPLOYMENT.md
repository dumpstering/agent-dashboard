# Deployment Runbook

## Purpose

Deploy and validate the dashboard service safely, with clear rollback steps.

## Prerequisites

- Python 3.11+ available as `python3`
- `tmux` installed on host
- Access to runtime environment variables/secrets
- Repository checked out on target host

## Required Environment Variables

- `DASHBOARD_API_KEY`: API key for mutating `/api/*` routes
- `OPENCLAW_GATEWAY_URL`: gateway base URL or WS URL
- `OPENCLAW_GATEWAY_TOKEN`: gateway auth token
- `DASH_ALLOWED_ORIGINS`: comma-separated origin allow-list for `/ws/chat`

Optional:
- `DASHBOARD_DEV_MODE=1` (development only; do not use in production)

## Deploy Steps

1. Install/update dependencies:
```bash
python3 -m pip install -r requirements.txt
```
2. Run validation commands:
```bash
make test
```
3. Export environment variables for target environment.
4. Start/restart service:
```bash
./start.sh
```

## Post-Deploy Verification

Run each check before declaring success:

1. Process health:
```bash
ps aux | rg "server.py"
```
2. API health:
```bash
curl -sf http://127.0.0.1:8223/api/system
```
3. Auth enforcement:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8223/api/agents -H "Content-Type: application/json" -d '{"id":"x","project":"p","task":"t"}'
```
Expected: `401` when `DASHBOARD_API_KEY` is set.
4. WebSocket policy:
- Confirm allowed origin connects.
- Confirm disallowed origin receives `403`.

## Rollback

If verification fails:

1. Stop the new process.
2. Restore last known-good revision.
3. Reinstall dependencies from the known-good revision if needed.
4. Restart service with previous environment values.
5. Re-run post-deploy verification checks.

## Incident Notes

- Capture failing command output, timestamps, and environment differences.
- If auth/origin checks fail, treat as security-impacting and pause rollout.

