# Dashboard Project Context

Read this file before making any changes to the dashboard.

## Architecture
- **Server:** Python/aiohttp on port 8223
- **Frontend:** Single HTML file (static/index.html) with inline CSS + JS
- **State:** JSON file persistence (agents.json) via state.py
- **Design system:** Dark-tech (OKLCH colors, monospace data, borders over shadows)
- **Design reference:** design-craft-dark-tech/skill.md (MUST follow for all UI work)

## Authentication
- Cloudflare Access is the primary perimeter auth layer for production deployments.
- The server also supports optional application-level auth for mutating operations via `DASHBOARD_API_KEY`.
- When `DASHBOARD_API_KEY` is set, all mutating REST APIs (`POST /api/*`) and `/ws/chat` require that key.
- `DASHBOARD_DEV_MODE=1` is a local-development override for WebSocket origin checks only.

## Chat Integration
- Dashboard chat connects to Op (OpenClaw agent) via WebSocket proxy
- Path: Browser -> WS /ws/chat -> server.py -> WS ws://localhost:18789 -> OpenClaw Gateway
- Gateway auth uses OPENCLAW_GATEWAY_TOKEN env var (server-side only, never exposed to browser)
- OpenClaw gateway protocol version: 3
- dangerouslyDisableDeviceAuth is enabled on the gateway

## Data Sources
- **Agent data:** SSE stream (/api/sse) with typed events (agents, chat, system)
- **System stats:** /api/system endpoint using psutil (refreshed every 90s by frontend)
- **Chat:** WebSocket /ws/chat (primary), REST /api/chat (legacy)

## Environment Variables
- `OPENCLAW_GATEWAY_TOKEN` - Required for chat proxy to OpenClaw gateway
- `OPENCLAW_GATEWAY_URL` - Gateway URL (default: http://localhost:18789)
- `DASHBOARD_API_KEY` - Optional app-level key; when set, required for mutating APIs and `/ws/chat`
- `DASH_ALLOWED_ORIGINS` - Comma-separated allowlist for `/ws/chat` Origin validation
- `DASHBOARD_DEV_MODE` - Set to `1` only for local dev to bypass fail-closed WS Origin checks

## Deployment
- Cloudflare tunnel: dash.clwiop.xyz -> localhost:8223
- Tunnel config: ~/.cloudflared/config.yml
- Server start: `OPENCLAW_GATEWAY_TOKEN=<token> ./venv/bin/python server.py`

## Constraints
- Single HTML file, no build tools
- Dark-tech design system is mandatory (read design-craft-dark-tech/skill.md)
- Keep auth docs aligned with actual server behavior
- Keep psutil for system stats
- Keep aiohttp for server
