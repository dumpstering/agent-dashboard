# Dashboard V2 - Agent Task

## Overview
Enhance the existing agent orchestration dashboard at `/Users/open/.openclaw/workspace/projects/dashboard/`.

The server runs on port 8223 with aiohttp. The frontend is a single `static/index.html` file using the dark-tech design system (OKLCH colors, monospace data, borders over shadows, 13px base). psutil is already installed in the venv.

Read `design-craft-dark-tech/skill.md` for the full dark-tech design system reference. Follow it strictly for all UI work.

## Tasks

### 1. System Stats Section
Add a new section to the LEFT side of the page showing live system metrics. Use a sidebar or column layout (stats on left, agent table + chat on right).

Metrics to display:
- **Uptime** (system uptime, formatted as "Xd Xh Xm")
- **RAM Usage** (used/total GB + percentage bar)
- **CPU Load** (1m/5m/15m averages + small sparkline or bar)
- **Network Throughput** (bytes sent/received since boot, formatted human-readable)

Backend: Add `GET /api/system` endpoint using psutil:
```python
import psutil
# psutil.boot_time(), psutil.virtual_memory(), psutil.cpu_percent(), 
# psutil.getloadavg(), psutil.net_io_counters()
```

Frontend: Auto-refresh every 90 seconds. Use monospace font for all values. Show subtle progress bars for RAM/CPU.

### 2. Chat Integration
The chat panel currently only adds messages to the local DOM. Wire it up:

Backend: Add these endpoints:
- `POST /api/chat` - accepts `{"message": "text"}`, stores in a messages list (in-memory is fine), broadcasts to SSE
- `GET /api/chat/history` - returns last 50 messages

Frontend:
- On send: POST to `/api/chat`, clear input
- Receive chat messages via the existing SSE stream (add a `chat` field to SSE data)
- Display with timestamps, distinguish system vs user messages
- Auto-scroll to bottom on new messages

### 3. Layout Improvements
- Two-column layout: left sidebar (system stats, ~280px) | right main area (stats cards, agent table, chat)
- Make the chat panel taller (400px min)
- Add a subtle header bar with "Agent Orchestration" title and connection status dot
- Ensure mobile responsive (stack to single column on <768px)

### 4. Polish
- Add loading states for initial data fetch
- Connection indicator should pulse green when connected
- Format durations nicely (e.g., "12m 34s" not "754")
- Add empty state illustrations/text when no agents are active
- Smooth transitions on data updates

## Constraints
- Single HTML file (inline CSS + JS) - no build tools
- Must work with existing server.py API routes (don't break them)
- Follow dark-tech design system from `design-craft-dark-tech/skill.md`
- Use OKLCH colors, monospace for data, borders not shadows
- 13px base font size
- Test that the server starts and responds correctly when done

## Files to Edit
- `server.py` - add /api/system and /api/chat endpoints
- `static/index.html` - full UI overhaul with new layout
- `requirements.txt` - add psutil if not listed

## When Done
Run `python server.py` and verify:
1. http://localhost:8223/ loads the dashboard
2. /api/system returns system stats JSON
3. /api/chat accepts POST and returns in SSE
4. Layout looks correct with two columns
