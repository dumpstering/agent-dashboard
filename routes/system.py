"""System and health-related routes."""
import time
from pathlib import Path

import psutil
from aiohttp import web


def register_routes(app: web.Application, state, network_tracker_key):
    """Register system routes."""

    async def handle_index(request):
        """Serve index.html for root path."""
        return web.FileResponse(Path(__file__).parent.parent / "static" / "index.html")

    async def handle_system_stats(request):
        """Get system statistics."""
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)
        uptime_days = uptime_seconds // 86400
        uptime_hours = (uptime_seconds % 86400) // 3600
        uptime_mins = (uptime_seconds % 3600) // 60
        uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_mins}m"

        mem = psutil.virtual_memory()
        mem_used_gb = mem.used / (1024**3)
        mem_total_gb = mem.total / (1024**3)

        cpu_percent = psutil.cpu_percent(interval=0.1)
        load_avg = psutil.getloadavg()
        network_tracker = request.app[network_tracker_key]

        return web.json_response(
            {
                "uptime": uptime_str,
                "uptime_seconds": uptime_seconds,
                "memory": {
                    "used_gb": round(mem_used_gb, 2),
                    "total_gb": round(mem_total_gb, 2),
                    "percent": mem.percent,
                },
                "cpu": {
                    "percent": cpu_percent,
                    "load_1m": round(load_avg[0], 2),
                    "load_5m": round(load_avg[1], 2),
                    "load_15m": round(load_avg[2], 2),
                },
                "network": {
                    "all_time": network_tracker.format_window(*network_tracker.get_all_time_totals()),
                    "last_24h": await network_tracker.get_window_delta(24 * 60 * 60),
                    "last_1h": await network_tracker.get_window_delta(60 * 60),
                },
            }
        )

    async def handle_health_stats(request):
        """Return summarized dashboard state counts."""
        return web.json_response(await state.get_stats())

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/system", handle_system_stats)
    app.router.add_get("/api/stats", handle_health_stats)

