# Security Audit - Agent Orchestration Dashboard

Date: 2026-03-01
Scope: `server.py`, `state.py`, `static/index.html`, `start.sh`, `README.md`, tests

## Executive Summary
Security posture is heavily dependent on perimeter controls (Cloudflare Access) and is not self-protecting at application level. If edge controls are bypassed, misconfigured, or not present in a given environment, sensitive operations are exposed.

Score: **42/100**

## High Findings

### H1 - Insecure-by-default WS trust boundary
Evidence:
- `server.py:472-474` allows all origins when `DASH_ALLOWED_ORIGINS` is unset.
- `server.py:626-630` only checks origin if configured; otherwise accepts upgrade.
- `server.py:903` exposes `/ws/chat`; `server.py:919` binds to `0.0.0.0`.

Risk:
- Cross-site WebSocket hijack and unauthorized chat relay are possible if deployment forgets `DASH_ALLOWED_ORIGINS` or perimeter auth is absent.

Recommendation:
- Fail closed: require explicit allowlist in production mode.
- Add `DASH_ENV=production` guard that rejects startup when `DASH_ALLOWED_ORIGINS` is missing.

### H2 - Mutating API endpoints unauthenticated by default
Evidence:
- `server.py:199-208` only enforces auth when `DASH_API_KEY` is set.
- `server.py:899-902` exposes POST mutators (`/api/agents`, `/status`, `/remove`, `/api/chat`).

Risk:
- Any client with network reach can mutate orchestration state if edge controls are missing or bypassed.

Recommendation:
- Add mandatory auth mode for non-local binds.
- At minimum, reject mutating requests when no app auth is configured and bind is non-loopback.

## Medium Findings

### M1 - Chat history endpoint exposes potentially sensitive content
Evidence:
- `server.py:856-858` returns full in-memory chat history with no auth by default.

Risk:
- Data leakage of operator conversation history.

Recommendation:
- Restrict endpoint by auth or remove in production.
- Add TTL and redaction policy.

### M2 - No request size limits on JSON API endpoints
Evidence:
- `parse_json` (`server.py:136-151`) parses arbitrary payload size.

Risk:
- Memory pressure / DoS via oversized POST bodies.

Recommendation:
- Set `client_max_size` on `aiohttp.web.Application` and cap field lengths (`id`, `project`, `task`, `message`).

### M3 - Lack of security headers/CSP at app layer
Evidence:
- No middleware setting CSP, X-Frame-Options, Referrer-Policy, etc.

Risk:
- Weak browser-side hardening if edge policies are inconsistent.

Recommendation:
- Add strict CSP for inline script nonce strategy or refactor JS into static file with hash.

## Low Findings

### L1 - tmux subprocess invocation is safe from shell injection
Evidence:
- `subprocess.run([...])` argument lists at `server.py:48-65` (no shell).

Risk:
- Low.

Recommendation:
- Keep list-based subprocess invocation.

## Positive Controls
- TLS guard for non-local gateway URLs (`server.py:451-452`).
- WS message size/rate limits (`server.py:22-24`, `server.py:802-814`).
- Frontend uses `textContent` instead of unsafe HTML insertion (`static/index.html:907`, `926`, `997`, `1001`).

## Priority Remediation (7 Days)
1. Make production startup fail when `DASH_ALLOWED_ORIGINS` missing.
2. Require explicit auth mode for mutating endpoints when not loopback.
3. Gate or remove `/api/chat/history` in production.
4. Add body and field size limits.
