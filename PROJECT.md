# Dashboard Project Context

Read this file before making any changes to the dashboard.

## Architecture
- **Server:** Python/aiohttp on port 8223
- **Frontend:** Single HTML file (static/index.html) with inline CSS + JS
- **State:** JSON file persistence (agents.json) via state.py
- **Design system:** Dark-tech (OKLCH colors, monospace data, borders over shadows)
- **Design reference:** design-craft-dark-tech/skill.md (MUST follow for all UI work)

## Authentication
- **Cloudflare Access is the ONLY auth layer.** The entire site (dash.clwiop.xyz) is behind Cloudflare Zero Trust with email OTP.
- **Do NOT add application-level authentication** (no API keys, no login forms, no WS auth tokens). If someone reaches the dashboard, they're already authenticated.
- The optional DASH_API_KEY env var exists for local dev/testing only and should NOT be required in production.

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
- `DASH_API_KEY` - Optional, local dev only, not needed behind Cloudflare

## Deployment
- Cloudflare tunnel: dash.clwiop.xyz -> localhost:8223
- Tunnel config: ~/.cloudflared/config.yml
- Server start: `OPENCLAW_GATEWAY_TOKEN=<token> ./venv/bin/python server.py`

## Constraints
- Single HTML file, no build tools
- Dark-tech design system is mandatory (read design-craft-dark-tech/skill.md)
- Do not add redundant auth layers (Cloudflare handles it)
- Keep psutil for system stats
- Keep aiohttp for server
