"""Agent CRUD and SSE routes."""
import asyncio
import json

from aiohttp import web

from middleware import error_response
from state import VALID_STATUSES


def register_routes(app: web.Application, state, sse_clients: set, parse_json):
    """Register agent and SSE routes and return SSE callbacks."""

    async def broadcast_message(message: str):
        """Broadcast one SSE message to all clients with queue backpressure handling."""
        dead_clients = set()
        for queue in list(sse_clients):
            try:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(message)
            except Exception:
                dead_clients.add(queue)

        sse_clients.difference_update(dead_clients)

    async def broadcast_event(event_name: str, payload):
        """Broadcast one typed SSE event."""
        message = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
        await broadcast_message(message)

    async def send_sse_update():
        """Broadcast agents and system stats updates."""
        agents = await state.get_all()
        stats = await state.get_stats()

        agents_payload = [
            {
                "id": a.id,
                "project": a.project,
                "task": a.task,
                "status": a.status,
                "started_at": a.started_at,
                "completed_at": a.completed_at,
                "duration": a.duration_seconds(),
            }
            for a in agents
        ]

        await broadcast_event("agents", agents_payload)
        await broadcast_event("system", stats)

    async def handle_sse(request):
        """SSE endpoint for live updates."""
        response = web.StreamResponse()
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        await response.prepare(request)

        queue = asyncio.Queue(maxsize=100)
        sse_clients.add(queue)

        try:
            agents = await state.get_all()
            stats = await state.get_stats()
            initial_agents = [
                {
                    "id": a.id,
                    "project": a.project,
                    "task": a.task,
                    "status": a.status,
                    "started_at": a.started_at,
                    "completed_at": a.completed_at,
                    "duration": a.duration_seconds(),
                }
                for a in agents
            ]
            await queue.put(f"event: agents\ndata: {json.dumps(initial_agents)}\n\n")
            await queue.put(f"event: system\ndata: {json.dumps(stats)}\n\n")

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    break
                await response.write(message.encode())
        except Exception:
            pass
        finally:
            sse_clients.discard(queue)

        return response

    async def handle_get_agents(request):
        """Get all agents."""
        agents = await state.get_all()
        return web.json_response(
            [
                {
                    "id": a.id,
                    "project": a.project,
                    "task": a.task,
                    "status": a.status,
                    "started_at": a.started_at,
                    "completed_at": a.completed_at,
                    "duration": a.duration_seconds(),
                }
                for a in agents
            ]
        )

    async def handle_add_agent(request):
        """Add a new agent."""
        data, error = await parse_json(request, required_fields=["id", "project", "task"])
        if error:
            return error

        status = data.get("status", "queued")
        if status not in VALID_STATUSES:
            return error_response("Invalid status", status=400)

        agent = await state.add_agent(
            id=data["id"],
            project=data["project"],
            task=data["task"],
            status=status,
        )
        await send_sse_update()
        return web.json_response({"success": True, "agent": agent.id})

    async def handle_update_status(request):
        """Update agent status."""
        data, error = await parse_json(request, required_fields=["id", "status"])
        if error:
            return error

        if data["status"] not in VALID_STATUSES:
            return error_response("Invalid status", status=400)

        agent = await state.update_status(data["id"], data["status"])
        if not agent:
            return error_response("Agent not found", status=404)

        await send_sse_update()
        return web.json_response({"success": True})

    async def handle_remove_agent(request):
        """Remove an agent."""
        data, error = await parse_json(request, required_fields=["id"])
        if error:
            return error

        success = await state.remove_agent(data["id"])
        if not success:
            return error_response("Agent not found", status=404)

        await send_sse_update()
        return web.json_response({"success": True})

    app.router.add_get("/api/sse", handle_sse)
    app.router.add_get("/api/agents", handle_get_agents)
    app.router.add_post("/api/agents", handle_add_agent)
    app.router.add_post("/api/agents/status", handle_update_status)
    app.router.add_post("/api/agents/remove", handle_remove_agent)

    return send_sse_update, broadcast_event
