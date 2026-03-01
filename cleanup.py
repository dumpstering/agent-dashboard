"""Background cleanup tasks for stale tmux-backed agents."""
import asyncio
from collections.abc import Awaitable, Callable


async def cleanup_stale_agents(
    state,
    send_sse_update: Callable[[], Awaitable[None]],
    check_tmux_session: Callable[[str], tuple[bool, int | None]],
):
    """Check registered agents against tmux sessions and update status."""
    agents = await state.get_all()

    for agent in agents:
        if agent.status not in {"working", "queued"}:
            continue

        is_alive, exit_code = await asyncio.to_thread(check_tmux_session, agent.id)
        if is_alive:
            continue

        if exit_code == 0:
            await state.update_status(agent.id, "done")
            print(f"Agent {agent.id} tmux session exited cleanly, marked as done")
        else:
            await state.update_status(agent.id, "error")
            print(f"Agent {agent.id} tmux session failed (exit {exit_code}), marked as error")

        await send_sse_update()


async def agent_cleanup_loop(
    state,
    send_sse_update: Callable[[], Awaitable[None]],
    check_tmux_session: Callable[[str], tuple[bool, int | None]],
    interval_seconds: int = 60,
):
    """Background task that periodically cleans stale agents."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cleanup_stale_agents(state, send_sse_update, check_tmux_session)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"Error in agent cleanup loop: {exc}")

