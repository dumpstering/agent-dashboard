"""Deterministic API exerciser for the dashboard server.

This script validates:
- agent create/upsert
- status transitions
- agent removal
- stats schema presence
- chat validation and history writes
"""
import asyncio
from typing import Any, Dict, List

import aiohttp


BASE_URL = "http://localhost:8223"
TEST_AGENTS: List[Dict[str, str]] = [
    {
        "id": "test-agent-1",
        "project": "dashboard",
        "task": "render hardening",
        "status": "queued",
    },
    {
        "id": "test-agent-2",
        "project": "docs",
        "task": "api contract update",
        "status": "queued",
    },
    {
        "id": "test-agent-3",
        "project": "qa",
        "task": "deterministic client checks",
        "status": "queued",
    },
]


def print_step(message: str) -> None:
    """Print a standardized progress line."""
    print(f"[STEP] {message}")


def print_pass(message: str) -> None:
    """Print a standardized pass line."""
    print(f"[PASS] {message}")


def assert_true(condition: bool, message: str) -> None:
    """Assert a condition with clear output."""
    if not condition:
        raise AssertionError(message)
    print_pass(message)


async def request_json(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    *,
    json_body: Dict[str, Any] | None = None,
    expected_status: int = 200,
) -> Any:
    """Perform an HTTP request and return parsed JSON."""
    url = f"{BASE_URL}{path}"
    async with session.request(method, url, json=json_body) as response:
        payload = await response.json()
        assert_true(
            response.status == expected_status,
            f"{method} {path} returned HTTP {expected_status}",
        )
        return payload


async def run() -> None:
    """Run deterministic API checks against a running server."""
    async with aiohttp.ClientSession() as session:
        print("Deterministic dashboard API check")
        print("Target:", BASE_URL)

        # Best effort cleanup (ignore not-found outcomes).
        for agent in TEST_AGENTS:
            async with session.post(f"{BASE_URL}/api/agents/remove", json={"id": agent["id"]}) as response:
                if response.status not in (200, 404):
                    payload = await response.text()
                    raise AssertionError(f"Unexpected cleanup status {response.status}: {payload}")

        print_step("Creating deterministic agents")
        for agent in TEST_AGENTS:
            payload = await request_json(session, "POST", "/api/agents", json_body=agent)
            assert_true(payload.get("success") is True, f"Created {agent['id']}")

        print_step("Validating created agents via GET /api/agents")
        agents_payload = await request_json(session, "GET", "/api/agents")
        by_id = {agent["id"]: agent for agent in agents_payload}
        for expected in TEST_AGENTS:
            found = by_id.get(expected["id"])
            assert_true(found is not None, f"{expected['id']} exists in agent list")
            assert_true(found["project"] == expected["project"], f"{expected['id']} has expected project")
            assert_true(found["task"] == expected["task"], f"{expected['id']} has expected task")
            assert_true(found["status"] == expected["status"], f"{expected['id']} has expected status")

        print_step("Applying deterministic status transitions")
        transitions = [
            ("test-agent-1", "dispatched"),
            ("test-agent-1", "working"),
            ("test-agent-1", "done"),
            ("test-agent-2", "working"),
        ]
        for agent_id, status in transitions:
            payload = await request_json(
                session,
                "POST",
                "/api/agents/status",
                json_body={"id": agent_id, "status": status},
            )
            assert_true(payload.get("success") is True, f"{agent_id} -> {status}")

        print_step("Verifying post-transition state")
        agents_payload = await request_json(session, "GET", "/api/agents")
        by_id = {agent["id"]: agent for agent in agents_payload}
        assert_true(by_id["test-agent-1"]["status"] == "done", "test-agent-1 finalized as done")
        assert_true(by_id["test-agent-2"]["status"] == "working", "test-agent-2 now working")
        assert_true(by_id["test-agent-3"]["status"] == "queued", "test-agent-3 remains queued")

        print_step("Checking stats payload shape")
        stats = await request_json(session, "GET", "/api/stats")
        for key in ("active", "completed_today", "queued", "total"):
            assert_true(key in stats, f"stats contains key '{key}'")
            assert_true(isinstance(stats[key], int), f"stats['{key}'] is an integer")

        print_step("Verifying chat validation and persistence")
        empty_chat = await request_json(
            session,
            "POST",
            "/api/chat",
            json_body={"message": "   "},
            expected_status=400,
        )
        assert_true(empty_chat.get("success") is False, "empty chat message rejected")

        chat_text = "deterministic test message"
        chat_ok = await request_json(
            session,
            "POST",
            "/api/chat",
            json_body={"message": chat_text},
        )
        assert_true(chat_ok.get("success") is True, "chat message accepted")

        history = await request_json(session, "GET", "/api/chat/history")
        messages = history.get("messages", [])
        assert_true(isinstance(messages, list), "chat history returns a list")
        assert_true(
            any(msg.get("text") == chat_text for msg in messages),
            "chat history includes deterministic test message",
        )

        print_step("Removing deterministic agents")
        for agent in TEST_AGENTS:
            payload = await request_json(
                session,
                "POST",
                "/api/agents/remove",
                json_body={"id": agent["id"]},
            )
            assert_true(payload.get("success") is True, f"Removed {agent['id']}")

        print("\nAll deterministic API checks passed.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        raise
