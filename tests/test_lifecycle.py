import asyncio
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import server
from state import AgentState


def test_check_tmux_session_returns_alive_when_session_exists():
    with patch("server.subprocess.run", return_value=Mock(returncode=0)) as run_mock:
        assert server.check_tmux_session("agent-1") == (True, None)
    run_mock.assert_called_once_with(
        ["tmux", "has-session", "-t", "agent-1"],
        capture_output=True,
        text=True,
        timeout=5,
    )


def test_check_tmux_session_reads_dead_exit_code_from_list_panes():
    has_session = Mock(returncode=1)
    list_panes = Mock(returncode=0, stdout="agent-1 1 42\n")
    with patch("server.subprocess.run", side_effect=[has_session, list_panes]):
        assert server.check_tmux_session("agent-1") == (False, 42)


def test_check_tmux_session_falls_back_to_killed_when_no_history():
    has_session = Mock(returncode=1)
    list_panes = Mock(returncode=0, stdout="other 1 0\n")
    with patch("server.subprocess.run", side_effect=[has_session, list_panes]):
        assert server.check_tmux_session("agent-1") == (False, 1)


def test_check_tmux_session_handles_tmux_errors_as_dead():
    with patch("server.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="tmux", timeout=5)):
        assert server.check_tmux_session("agent-1") == (False, 1)


def test_cleanup_stale_agents_updates_done_and_error_and_emits_sse():
    async def run_case():
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_state = server.state
            original_sse = server.send_sse_update
            try:
                server.state = AgentState(db_path=str(Path(tmp_dir) / "agents.json"))
                await server.state.add_agent("alive", "p", "t", "working")
                await server.state.add_agent("clean-exit", "p", "t", "queued")
                await server.state.add_agent("failed-exit", "p", "t", "working")
                await server.state.add_agent("already-done", "p", "t", "done")

                def fake_tmux_check(agent_id):
                    if agent_id == "alive":
                        return True, None
                    if agent_id == "clean-exit":
                        return False, 0
                    if agent_id == "failed-exit":
                        return False, 2
                    raise AssertionError(f"Unexpected agent checked: {agent_id}")

                server.send_sse_update = AsyncMock()
                with patch("server.check_tmux_session", side_effect=fake_tmux_check):
                    await server.cleanup_stale_agents()

                agents = {agent.id: agent async for agent in _iter_agents(server.state)}
                assert agents["alive"].status == "working"
                assert agents["clean-exit"].status == "done"
                assert agents["failed-exit"].status == "error"
                assert agents["already-done"].status == "done"
                assert server.send_sse_update.await_count == 2
            finally:
                server.state = original_state
                server.send_sse_update = original_sse

    asyncio.run(run_case())


async def _iter_agents(state):
    for agent in await state.get_all():
        yield agent
