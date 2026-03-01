"""Agent state management with JSON persistence."""
import asyncio
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psutil

VALID_STATUSES = {"queued", "dispatched", "working", "done", "error"}


@dataclass
class Agent:
    """Single agent state."""

    id: str
    project: str
    task: str
    status: str
    started_at: str
    completed_at: Optional[str] = None

    def duration_seconds(self) -> Optional[int]:
        """Calculate duration in seconds."""
        if not self.started_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at) if self.completed_at else datetime.now()
        return int((end - start).total_seconds())


class AgentState:
    """Thread-safe agent state manager."""

    def __init__(self, db_path: str = "agents.json"):
        self.db_path = Path(db_path)
        self.lock = asyncio.Lock()
        self.agents: Dict[str, Agent] = {}

    async def _load(self):
        """Load state from disk."""
        async with self.lock:
            if not self.db_path.exists():
                self.agents = {}
                return

            try:
                raw = await asyncio.to_thread(self.db_path.read_text)
                data = json.loads(raw)
                self.agents = {
                    agent_id: Agent(**agent_data) for agent_id, agent_data in data.items()
                }
            except Exception as e:
                print(f"Error loading state: {e}")
                self.agents = {}

    async def _save(self):
        """Persist state to disk."""
        data = {agent_id: asdict(agent) for agent_id, agent in self.agents.items()}
        payload = json.dumps(data, indent=2)
        tmp_path = self.db_path.with_name(f".{self.db_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            await asyncio.to_thread(tmp_path.write_text, payload)
            await asyncio.to_thread(os.replace, tmp_path, self.db_path)
        finally:
            if tmp_path.exists():
                await asyncio.to_thread(tmp_path.unlink)

    async def add_agent(self, id: str, project: str, task: str, status: str = "queued") -> Agent:
        """Add or update an agent."""
        async with self.lock:
            now = datetime.now().isoformat()
            agent = Agent(
                id=id,
                project=project,
                task=task,
                status=status,
                started_at=now,
            )
            self.agents[id] = agent
            await self._save()
            return agent

    async def update_status(self, id: str, status: str) -> Optional[Agent]:
        """Update agent status."""
        async with self.lock:
            agent = self.agents.get(id)
            if not agent:
                return None

            agent.status = status
            if status in {"done", "error"} and not agent.completed_at:
                agent.completed_at = datetime.now().isoformat()

            await self._save()
            return agent

    async def remove_agent(self, id: str) -> bool:
        """Remove an agent."""
        async with self.lock:
            if id in self.agents:
                del self.agents[id]
                await self._save()
                return True
            return False

    async def get_all(self) -> List[Agent]:
        """Get all agents."""
        async with self.lock:
            return list(self.agents.values())

    async def get_stats(self) -> Dict:
        """Calculate dashboard stats."""
        async with self.lock:
            agents = list(self.agents.values())
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            completed_today = sum(
                1
                for a in agents
                if a.status == "done"
                and a.completed_at
                and datetime.fromisoformat(a.completed_at) >= today_start
            )

            return {
                "active": sum(1 for a in agents if a.status == "working"),
                "completed_today": completed_today,
                "queued": sum(1 for a in agents if a.status == "queued"),
                "total": len(agents),
            }


class NetworkStatsTracker:
    """Periodic network stats snapshots for time-window deltas."""

    def __init__(self, snapshot_interval: int = 60):
        self.snapshot_interval = snapshot_interval
        self._snapshots: list[tuple[float, int, int]] = []
        self._task = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _format_bytes(value: int) -> str:
        num = float(value)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if num < 1024.0:
                return f"{num:.1f} {unit}"
            num /= 1024.0
        return f"{num:.1f} PB"

    @classmethod
    def format_window(cls, bytes_sent: int, bytes_recv: int) -> Dict[str, object]:
        return {
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "bytes_sent_str": cls._format_bytes(bytes_sent),
            "bytes_recv_str": cls._format_bytes(bytes_recv),
        }

    def get_all_time_totals(self):
        net = psutil.net_io_counters()
        return net.bytes_sent, net.bytes_recv

    async def start(self):
        await self._capture_snapshot()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._snapshot_loop())

    async def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _snapshot_loop(self):
        while True:
            await asyncio.sleep(self.snapshot_interval)
            await self._capture_snapshot()

    async def _capture_snapshot(self):
        net = psutil.net_io_counters()
        now_ts = time.time()
        async with self._lock:
            self._snapshots.append((now_ts, net.bytes_sent, net.bytes_recv))
            min_ts = now_ts - (25 * 60 * 60)
            self._snapshots = [snapshot for snapshot in self._snapshots if snapshot[0] >= min_ts]

    async def get_window_delta(self, window_seconds: int) -> Dict[str, object]:
        now_ts = time.time()
        net = psutil.net_io_counters()
        current_sent = net.bytes_sent
        current_recv = net.bytes_recv
        baseline_ts = now_ts - window_seconds

        async with self._lock:
            if not self._snapshots:
                return self.format_window(0, 0)

            baseline = self._snapshots[0]
            for snapshot in self._snapshots:
                if snapshot[0] <= baseline_ts:
                    baseline = snapshot
                else:
                    break

        delta_sent = max(0, current_sent - baseline[1])
        delta_recv = max(0, current_recv - baseline[2])
        return self.format_window(delta_sent, delta_recv)
