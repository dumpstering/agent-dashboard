import os
from pathlib import Path

import pytest

from state import AgentState


@pytest.mark.asyncio
async def test_atomic_save_cleans_up_tmp_file_on_replace_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "agents.json"
    state = AgentState(db_path=str(db_path))
    await state.add_agent(id="a1", project="Dashboard", task="Atomic save", status="queued")

    original_replace = os.replace

    def failing_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        await state._save()

    tmp_files = list(Path(tmp_path).glob(".agents.json.*.tmp"))
    assert tmp_files == []

    # Ensure monkeypatch cleanup does not hide accidental permanent patching.
    assert os.replace is not original_replace
