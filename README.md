# Agent Orchestration Dashboard

Dark-tech dashboard for monitoring agent activity with a JSON-backed state store and a realtime SSE stream.

## Prerequisites

- Python `3.10+`
- `pip` (bundled with most Python installs)
- OS support for Python virtual environments (`venv`)

Required runtime packages (from `requirements.txt`):

- `aiohttp==3.9.3`
- `psutil==5.9.8`

Required development packages (from `requirements-dev.txt`):

- `pytest`
- `pytest-aiohttp`
- `ruff`
- `mypy`
- `bandit`

## Setup

```bash
# 1) Create virtual environment
python3 -m venv venv

# 2) Activate
source venv/bin/activate

# 3) Install runtime dependencies
pip install -r requirements.txt

# 4) Install development dependencies
pip install -r requirements-dev.txt

# 5) Run server
python server.py
```

App URL: `http://localhost:8223`

Shortcut:

```bash
./start.sh
```

## Standard Dev Workflow

Run the full local CI chain before pushing changes:

```bash
make ci
```

Equivalent manual commands:

```bash
pip install -r requirements-dev.txt
make ci
```

## Environment Variables

WebSocket chat requires gateway configuration:

- `OPENCLAW_GATEWAY_URL` (required): OpenClaw gateway WebSocket URL the dashboard proxies to.
- `OPENCLAW_GATEWAY_TOKEN` (required): bearer token used by dashboard server when authenticating to the gateway.
- `DASHBOARD_API_KEY` (optional): when set, required for mutating APIs (`POST /api/*`) and `/ws/chat`.
- `DASH_ALLOWED_ORIGINS` (required unless `DASHBOARD_DEV_MODE=1`): comma-separated browser origins allowed to open `/ws/chat`.
- `DASHBOARD_DEV_MODE` (optional, dev only): set to `1` to bypass WS Origin allowlist checks locally.

Required request header for mutating REST endpoints when `DASHBOARD_API_KEY` is enabled:

- `X-API-Key: <DASHBOARD_API_KEY>`

## Chat Architecture (Primary: WebSocket)

Primary chat interface is WebSocket, not REST.

- Browser connects to dashboard WS endpoint: `/ws/chat`
- Dashboard server acts as a proxy/relay to gateway:
  - Browser -> `ws(s)://<dash-host>/ws/chat`
  - Dashboard -> `OPENCLAW_GATEWAY_URL`
- Gateway token auth is performed server-side by dashboard using `OPENCLAW_GATEWAY_TOKEN`

Browser auth for chat when `DASHBOARD_API_KEY` is enabled:

- Include API key as query param: `/ws/chat?key=<DASHBOARD_API_KEY>`
- Unless `DASHBOARD_DEV_MODE=1`, the request `Origin` must match `DASH_ALLOWED_ORIGINS`
- If origin/key checks fail, WS upgrade is rejected

## API Contract

Full OpenAPI 3.0 spec: [`docs/openapi.yaml`](docs/openapi.yaml)

Base URL: `http://localhost:8223`

Content type for JSON request bodies:

- `Content-Type: application/json`

### Error format

Application-level API errors return JSON in this shape:

```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

Common statuses:

- `400` validation/input errors (example: empty chat message)
- `404` resource-not-found operations (example: unknown agent ID)

### Data model

Agent object:

```json
{
  "id": "agent-1",
  "project": "dashboard",
  "task": "Build UI",
  "status": "working",
  "started_at": "2026-02-27T12:00:00.000000",
  "completed_at": null,
  "duration": 42
}
```

Known status values in UI/state semantics:

- `working`
- `done`
- `queued`
- `dispatched`
- `error`

### Endpoints

#### `GET /`

Returns `static/index.html`.

#### `GET /api/agents`

Returns all tracked agents.

Response `200`:

```json
[
  {
    "id": "agent-1",
    "project": "dashboard",
    "task": "Build UI",
    "status": "working",
    "started_at": "2026-02-27T12:00:00.000000",
    "completed_at": null,
    "duration": 42
  }
]
```

#### `POST /api/agents`

Create or update-by-id (upsert) an agent.

Request body:

```json
{
  "id": "agent-1",
  "project": "dashboard",
  "task": "Build UI",
  "status": "queued"
}
```

Notes:

- `status` is optional; defaults to `queued`.
- Route is upsert semantics: posting an existing `id` overwrites that agent record.

Response `200`:

```json
{
  "success": true,
  "agent": "agent-1"
}
```

#### `POST /api/agents/status`

Update an agent status.

Request body:

```json
{
  "id": "agent-1",
  "status": "done"
}
```

Response `200`:

```json
{
  "success": true
}
```

Not found `404`:

```json
{
  "success": false,
  "error": "Agent not found"
}
```

#### `POST /api/agents/remove`

Delete an agent by ID.

Request body:

```json
{
  "id": "agent-1"
}
```

Response `200`:

```json
{
  "success": true
}
```

Not found `404`:

```json
{
  "success": false,
  "error": "Agent not found"
}
```

#### `GET /api/stats`

Returns summary counters.

Response `200`:

```json
{
  "active": 2,
  "completed_today": 5,
  "queued": 1,
  "total": 7
}
```

#### `GET /api/system`

Returns host-level system metrics for the sidebar.

Response `200`:

```json
{
  "uptime": "2d 3h 11m",
  "uptime_seconds": 184260,
  "memory": {
    "used_gb": 8.52,
    "total_gb": 16.0,
    "percent": 53.2
  },
  "cpu": {
    "percent": 17.3,
    "load_1m": 1.42,
    "load_5m": 1.11,
    "load_15m": 0.97
  },
  "network": {
    "all_time": {
      "bytes_sent": 123456,
      "bytes_recv": 654321,
      "bytes_sent_str": "120.6 KB",
      "bytes_recv_str": "639.0 KB"
    },
    "last_24h": {
      "bytes_sent": 12345,
      "bytes_recv": 54321,
      "bytes_sent_str": "12.1 KB",
      "bytes_recv_str": "53.0 KB"
    },
    "last_1h": {
      "bytes_sent": 456,
      "bytes_recv": 789,
      "bytes_sent_str": "456 B",
      "bytes_recv_str": "789 B"
    }
  }
}
```

#### `GET /ws/chat`

Primary chat transport (WebSocket).

Notes:

- This is the canonical chat interface for the dashboard UI.
- The server proxies frames between browser and OpenClaw gateway.
- Cloudflare Access is typically used as perimeter auth in production.
- If `DASHBOARD_API_KEY` is set, include query param `?key=<DASHBOARD_API_KEY>`.

#### `POST /api/chat`

Legacy chat endpoint (kept for compatibility; WebSocket is primary).

Request body:

```json
{
  "message": "Hello operators"
}
```

Response `200`:

```json
{
  "success": true
}
```

Validation failure `400` (empty/whitespace message):

```json
{
  "success": false,
  "error": "Message cannot be empty"
}
```

#### `GET /api/chat/history`

Legacy chat history endpoint (kept for compatibility; WebSocket is primary).

Response `200`:

```json
{
  "messages": [
    {
      "text": "Hello operators",
      "timestamp": 1700000000,
      "is_system": false
    }
  ]
}
```

#### `GET /api/sse`

Server-Sent Events stream.

Headers:

- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`

SSE event types:

- `agents`: full agent list snapshots
- `chat`: new chat messages
- `system`: dashboard stat counters (`/api/stats` shape)

Example payloads:

`agents`

```json
[
  {
    "id": "agent-1",
    "project": "dashboard",
    "task": "Build UI",
    "status": "working",
    "started_at": "2026-02-27T12:00:00.000000",
    "completed_at": null,
    "duration": 42
  }
]
```

`chat`

```json
{
  "text": "Hello operators",
  "timestamp": 1700000000,
  "is_system": false
}
```

`system`

```json
{
  "active": 1,
  "completed_today": 0,
  "queued": 0,
  "total": 1
}
```

## Deterministic API Exerciser

Run:

```bash
source venv/bin/activate
python test_agents.py
```

What it verifies:

- Agent create/upsert route behavior
- Agent status transitions (`queued -> dispatched -> working -> done`)
- Agent remove behavior
- Stats endpoint shape and counters
- Chat validation (`400` on empty message)
- Chat write + history visibility

The script uses fixed agent IDs and deterministic transitions so runs are repeatable.
