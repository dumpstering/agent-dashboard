# Dashboard Chat Integration - Agent Task

## Goal
Make the dashboard chat a real bidirectional channel to Op (OpenClaw agent). User types on dashboard, Op sees it immediately. Op replies, user sees it on dashboard in real-time.

## Architecture
```
Browser (index.html) <--WebSocket--> Dashboard Server (server.py) <--WebSocket--> OpenClaw Gateway (localhost:18789)
```

The dashboard server acts as a WebSocket PROXY between the browser and the OpenClaw gateway.

## OpenClaw Gateway WebSocket Protocol

### Connection
- URL: `ws://localhost:18789`
- First frame from server: `{"type":"event","event":"connect.challenge","payload":{"nonce":"...","ts":...}}`
- Client must reply with connect request (see below)
- Server replies with `{"type":"res","id":"...","ok":true,"payload":{"type":"hello-ok",...}}`

### Connect Request
```json
{
  "type": "req",
  "id": "connect-1",
  "method": "connect",
  "params": {
    "minProtocol": 3,
    "maxProtocol": 3,
    "client": {
      "id": "dashboard-chat",
      "version": "1.0.0",
      "platform": "web",
      "mode": "operator"
    },
    "role": "operator",
    "scopes": ["operator.read", "operator.write"],
    "caps": [],
    "commands": [],
    "permissions": {},
    "auth": { "token": "GATEWAY_TOKEN_HERE" },
    "locale": "en-US",
    "userAgent": "dashboard-chat/1.0.0"
  }
}
```

NOTE: `gateway.controlUi.dangerouslyDisableDeviceAuth` is true, so we can omit the `device` field.

### Sending a chat message
```json
{
  "type": "req",
  "id": "msg-1",
  "method": "chat.send",
  "params": {
    "message": "Hello from dashboard",
    "idempotencyKey": "unique-key-here"
  }
}
```

Response is non-blocking: `{"type":"res","id":"msg-1","ok":true,"payload":{"runId":"...","status":"started"}}`

### Receiving responses
Op's reply streams as `chat` events:
```json
{
  "type": "event",
  "event": "chat",
  "payload": { ... }
}
```

### Chat history
```json
{
  "type": "req",
  "id": "history-1", 
  "method": "chat.history",
  "params": {}
}
```

## Engineer 1 (Backend) - server.py

### File domain: server.py ONLY

### Tasks:
1. Add `aiohttp` WebSocket endpoint at `/ws/chat`
2. When a browser client connects to `/ws/chat`:
   - Open a WebSocket connection to `ws://localhost:18789` (OpenClaw gateway)
   - Handle the connect.challenge event
   - Send the connect request with auth token from `OPENCLAW_GATEWAY_TOKEN` env var
   - Wait for hello-ok response
3. Relay messages bidirectionally:
   - Browser sends `{"message": "text"}` -> server sends `chat.send` to gateway
   - Gateway sends `chat` events -> server forwards to browser as `{"type":"reply","text":"..."}` or `{"type":"stream","delta":"..."}` 
4. Handle reconnection: if gateway WS drops, try to reconnect
5. Keep the existing REST chat endpoints for backwards compatibility but mark them as legacy
6. Remove the wake event forwarding code (the `_forward_to_openclaw` function) - no longer needed

### Key details:
- Gateway URL: `os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:18789")` -> convert to `ws://`
- Gateway token: `os.getenv("OPENCLAW_GATEWAY_TOKEN", "")`
- Generate unique IDs for requests: use `uuid.uuid4().hex[:8]`
- Generate unique idempotencyKey for each chat.send

## Engineer 2 (Frontend) - static/index.html

### File domain: static/index.html ONLY

### Tasks:
1. Replace the REST-based chat with WebSocket client connecting to `/ws/chat`
2. On page load: `new WebSocket("ws://" + location.host + "/ws/chat")`
3. On send: `ws.send(JSON.stringify({message: text}))`
4. On receive: parse messages and display:
   - `{"type":"reply","text":"..."}` -> display as Op's message (complete)
   - `{"type":"stream","delta":"..."}` -> append to current streaming message
   - `{"type":"stream_end"}` -> finalize current streaming message
   - `{"type":"history","messages":[...]}` -> populate chat history on connect
   - `{"type":"connected"}` -> update connection indicator
   - `{"type":"error","text":"..."}` -> show error in chat
5. Visual updates:
   - Show "Op is typing..." indicator during streaming
   - Differentiate user messages (right-aligned or different color) from Op messages (left-aligned)
   - Show timestamps on messages
   - Keep the dark-tech design system
6. Auto-reconnect on WebSocket close (with backoff)

## Constraints
- Keep ALL existing functionality (agent table, stats, system stats sidebar)
- Don't break the SSE connection for agent/system updates (SSE stays for agent data, WS is for chat only)
- Dark-tech design system must be preserved
- Single HTML file, no build tools
