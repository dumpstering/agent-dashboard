import asyncio
import json
import os
import tempfile
from pathlib import Path

import aiohttp
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp.test_utils import unused_port

import server
from routes.chat import MAX_CHAT_MESSAGE_BYTES
from state import AgentState


class BaseApiTestCase(AioHTTPTestCase):
    DASH_API_KEY: str | None = None

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self._original_api_key = os.environ.get("DASHBOARD_API_KEY")
        self._original_gateway_url = os.environ.get("OPENCLAW_GATEWAY_URL")
        self._original_gateway_token = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
        self._original_allowed_origins = os.environ.get("DASH_ALLOWED_ORIGINS")
        self._original_dev_mode = os.environ.get("DASHBOARD_DEV_MODE")

        if self.DASH_API_KEY is None:
            os.environ.pop("DASHBOARD_API_KEY", None)
        else:
            os.environ["DASHBOARD_API_KEY"] = self.DASH_API_KEY
        os.environ["DASHBOARD_DEV_MODE"] = "1"

        server.state = AgentState(db_path=str(Path(self.tmp_dir.name) / "agents.json"))
        server.sse_clients = set()
        server.chat_messages = []
        super().setUp()

    def tearDown(self):
        if self._original_api_key is None:
            os.environ.pop("DASHBOARD_API_KEY", None)
        else:
            os.environ["DASHBOARD_API_KEY"] = self._original_api_key
        if self._original_gateway_url is None:
            os.environ.pop("OPENCLAW_GATEWAY_URL", None)
        else:
            os.environ["OPENCLAW_GATEWAY_URL"] = self._original_gateway_url
        if self._original_gateway_token is None:
            os.environ.pop("OPENCLAW_GATEWAY_TOKEN", None)
        else:
            os.environ["OPENCLAW_GATEWAY_TOKEN"] = self._original_gateway_token
        if self._original_allowed_origins is None:
            os.environ.pop("DASH_ALLOWED_ORIGINS", None)
        else:
            os.environ["DASH_ALLOWED_ORIGINS"] = self._original_allowed_origins
        if self._original_dev_mode is None:
            os.environ.pop("DASHBOARD_DEV_MODE", None)
        else:
            os.environ["DASHBOARD_DEV_MODE"] = self._original_dev_mode
        self.tmp_dir.cleanup()
        super().tearDown()

    async def get_application(self):
        return server.create_app()


class TestApiHappyPaths(BaseApiTestCase):
    async def test_agents_crud_status_and_stats(self):
        resp = await self.client.get("/api/agents")
        assert resp.status == 200
        assert await resp.json() == []

        add_resp = await self.client.post(
            "/api/agents",
            json={"id": "agent-1", "project": "Dashboard", "task": "Hardening", "status": "queued"},
        )
        assert add_resp.status == 200
        add_body = await add_resp.json()
        assert add_body["success"] is True
        assert add_body["agent"] == "agent-1"

        agents_resp = await self.client.get("/api/agents")
        agents = await agents_resp.json()
        assert len(agents) == 1
        assert agents[0]["id"] == "agent-1"
        assert agents[0]["status"] == "queued"

        update_resp = await self.client.post(
            "/api/agents/status", json={"id": "agent-1", "status": "working"}
        )
        assert update_resp.status == 200
        assert (await update_resp.json())["success"] is True

        stats_resp = await self.client.get("/api/stats")
        stats = await stats_resp.json()
        assert stats["active"] == 1
        assert stats["total"] == 1

        done_resp = await self.client.post(
            "/api/agents/status", json={"id": "agent-1", "status": "done"}
        )
        assert done_resp.status == 200

        stats_resp_2 = await self.client.get("/api/stats")
        stats_2 = await stats_resp_2.json()
        assert stats_2["completed_today"] >= 1

        remove_resp = await self.client.post("/api/agents/remove", json={"id": "agent-1"})
        assert remove_resp.status == 200
        assert (await remove_resp.json())["success"] is True

        final_agents_resp = await self.client.get("/api/agents")
        assert await final_agents_resp.json() == []

    async def test_system_endpoint(self):
        resp = await self.client.get("/api/system")
        assert resp.status == 200
        body = await resp.json()
        assert "uptime" in body
        assert "memory" in body
        assert "cpu" in body
        assert "network" in body
        assert "all_time" in body["network"]
        assert "last_24h" in body["network"]
        assert "last_1h" in body["network"]

    async def test_chat_endpoint_and_history(self):
        send_resp = await self.client.post("/api/chat", json={"message": "hello team"})
        assert send_resp.status == 200
        assert (await send_resp.json())["success"] is True

        history_resp = await self.client.get("/api/chat/history")
        assert history_resp.status == 200
        history = await history_resp.json()
        assert len(history["messages"]) == 1
        assert history["messages"][0]["text"] == "hello team"

    async def test_sse_initial_events_include_agents_and_system(self):
        await self.client.post(
            "/api/agents",
            json={"id": "agent-sse", "project": "Dashboard", "task": "SSE", "status": "queued"},
        )
        resp = await self.client.get("/api/sse")
        assert resp.status == 200
        try:
            first_event = await asyncio.wait_for(resp.content.readuntil(b"\n\n"), timeout=2)
            second_event = await asyncio.wait_for(resp.content.readuntil(b"\n\n"), timeout=2)
        finally:
            resp.close()

        first_text = first_event.decode()
        second_text = second_event.decode()
        assert "event: agents" in first_text
        assert "agent-sse" in first_text
        assert "event: system" in second_text


class TestApiErrorContracts(BaseApiTestCase):
    async def test_malformed_json_returns_400(self):
        resp = await self.client.post(
            "/api/agents", data="{", headers={"Content-Type": "application/json"}
        )
        assert resp.status == 400
        assert await resp.json() == {"success": False, "error": "Invalid JSON"}

    async def test_malformed_json_without_content_type_returns_400(self):
        resp = await self.client.post("/api/agents", data="{")
        assert resp.status == 400
        assert await resp.json() == {"success": False, "error": "Invalid JSON"}

    async def test_missing_required_fields_returns_400(self):
        resp = await self.client.post("/api/agents", json={"id": "agent-2"})
        assert resp.status == 400
        body = await resp.json()
        assert body["success"] is False
        assert body["error"].startswith("Missing required field:")

    async def test_invalid_status_returns_400(self):
        add_resp = await self.client.post(
            "/api/agents",
            json={"id": "agent-3", "project": "Dashboard", "task": "Review", "status": "invalid"},
        )
        assert add_resp.status == 400
        assert await add_resp.json() == {"success": False, "error": "Invalid status"}

        await self.client.post(
            "/api/agents",
            json={"id": "agent-3", "project": "Dashboard", "task": "Review", "status": "queued"},
        )
        update_resp = await self.client.post(
            "/api/agents/status", json={"id": "agent-3", "status": "bad-status"}
        )
        assert update_resp.status == 400
        assert await update_resp.json() == {"success": False, "error": "Invalid status"}

    async def test_not_found_errors_are_normalized(self):
        update_resp = await self.client.post(
            "/api/agents/status", json={"id": "missing", "status": "working"}
        )
        assert update_resp.status == 404
        assert await update_resp.json() == {"success": False, "error": "Agent not found"}

        remove_resp = await self.client.post("/api/agents/remove", json={"id": "missing"})
        assert remove_resp.status == 404
        assert await remove_resp.json() == {"success": False, "error": "Agent not found"}

    async def test_request_body_limit_returns_413(self):
        oversize = "x" * (server.MAX_JSON_BODY_BYTES + 1)
        resp = await self.client.post("/api/chat", json={"message": oversize})
        assert resp.status == 413
        assert await resp.json() == {"success": False, "error": "Request body too large"}

    async def test_field_length_validation_returns_400(self):
        too_long_id = "a" * 1025
        resp = await self.client.post(
            "/api/agents",
            json={"id": too_long_id, "project": "Dashboard", "task": "Hardening", "status": "queued"},
        )
        assert resp.status == 400
        body = await resp.json()
        assert body["success"] is False
        assert "maximum length" in body["error"].lower()


class TestApiAuth(BaseApiTestCase):
    DASH_API_KEY: str | None = "super-secret"

    async def test_auth_rejection_returns_401(self):
        no_key_resp = await self.client.post(
            "/api/agents", json={"id": "a", "project": "p", "task": "t"}
        )
        assert no_key_resp.status == 401
        assert await no_key_resp.json() == {"success": False, "error": "Unauthorized"}

        wrong_key_resp = await self.client.post(
            "/api/agents",
            json={"id": "a", "project": "p", "task": "t"},
            headers={"X-API-Key": "wrong"},
        )
        assert wrong_key_resp.status == 401
        assert await wrong_key_resp.json() == {"success": False, "error": "Unauthorized"}

    async def test_auth_accepts_valid_key(self):
        ok_resp = await self.client.post(
            "/api/agents",
            json={"id": "agent-auth", "project": "p", "task": "t", "status": "queued"},
            headers={"X-API-Key": "super-secret"},
        )
        assert ok_resp.status == 200
        body = await ok_resp.json()
        assert body["success"] is True

    async def test_chat_history_requires_key_and_accepts_valid_key(self):
        no_key = await self.client.get("/api/chat/history")
        assert no_key.status == 401
        assert await no_key.json() == {"success": False, "error": "Unauthorized"}

        ok = await self.client.get("/api/chat/history", headers={"X-API-Key": "super-secret"})
        assert ok.status == 200
        body = await ok.json()
        assert "messages" in body


class TestApiFailClosedAuth(BaseApiTestCase):
    DASH_API_KEY = None

    def setUp(self):
        super().setUp()
        os.environ.pop("DASHBOARD_API_KEY", None)
        os.environ["DASHBOARD_DEV_MODE"] = "0"

    async def test_mutating_endpoints_require_auth_when_key_unset(self):
        add_resp = await self.client.post(
            "/api/agents",
            json={"id": "agent-fail-closed", "project": "Dashboard", "task": "Auth hardening"},
        )
        assert add_resp.status == 403
        assert await add_resp.json() == {"success": False, "error": "Forbidden"}

        status_resp = await self.client.post(
            "/api/agents/status",
            json={"id": "agent-fail-closed", "status": "working"},
        )
        assert status_resp.status == 403
        assert await status_resp.json() == {"success": False, "error": "Forbidden"}

        remove_resp = await self.client.post("/api/agents/remove", json={"id": "agent-fail-closed"})
        assert remove_resp.status == 403
        assert await remove_resp.json() == {"success": False, "error": "Forbidden"}

        chat_resp = await self.client.post("/api/chat", json={"message": "unauthorized"})
        assert chat_resp.status == 403
        assert await chat_resp.json() == {"success": False, "error": "Forbidden"}

    async def test_chat_history_requires_auth_when_key_unset(self):
        history_resp = await self.client.get("/api/chat/history")
        assert history_resp.status == 403
        assert await history_resp.json() == {"success": False, "error": "Forbidden"}


class TestRateLimiting(BaseApiTestCase):
    async def test_rate_limit_enforced_at_100_requests_per_minute(self):
        """Verify 100 requests per minute rate limit per IP."""
        import middleware

        # Clear any existing rate limit state
        middleware.rate_limit_store.clear()

        # Make 100 requests - all should succeed
        for i in range(100):
            resp = await self.client.get("/api/agents")
            assert resp.status == 200, f"Request {i+1} should succeed"

        # 101st request should be rate limited
        resp = await self.client.get("/api/agents")
        assert resp.status == 429
        body = await resp.json()
        assert body["success"] is False
        assert body["error"] == "Rate limit exceeded"

    async def test_rate_limit_uses_sliding_window(self):
        """Verify rate limiting uses a sliding window (timestamps expire after 60s)."""
        import middleware
        import time

        # Clear rate limit state
        middleware.rate_limit_store.clear()

        # Inject old timestamps (61 seconds ago) to simulate expired requests
        client_ip = "127.0.0.1"
        old_time = time.time() - 61  # 61 seconds ago (outside the 60s window)
        middleware.rate_limit_store[client_ip] = [old_time] * 100

        # New request should succeed because old timestamps are expired
        resp = await self.client.get("/api/agents")
        assert resp.status == 200

        # Verify old timestamps were cleaned up
        assert len(middleware.rate_limit_store[client_ip]) == 1  # Only the new request


class TestChatWebSocket(BaseApiTestCase):
    DASH_API_KEY: str | None = "ws-secret"
    WS_ORIGIN = "https://dash.test"

    def setUp(self):
        super().setUp()
        os.environ["DASHBOARD_DEV_MODE"] = "0"
        os.environ["DASH_ALLOWED_ORIGINS"] = self.WS_ORIGIN

    async def _start_gateway(self, send_ok=True):
        self.gateway_messages = []
        self.gateway_send_ok = send_ok

        async def gateway_ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"type": "event", "event": "connect.challenge", "payload": {}})

            connect_req = await ws.receive_json(timeout=2)
            self.gateway_messages.append(connect_req)
            await ws.send_json({"type": "res", "id": connect_req["id"], "ok": True, "payload": {}})

            history_req = await ws.receive_json(timeout=2)
            self.gateway_messages.append(history_req)
            await ws.send_json({"type": "res", "id": history_req["id"], "ok": True, "payload": {"messages": []}})

            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        break
                    continue

                frame = json.loads(msg.data)
                self.gateway_messages.append(frame)
                if frame.get("method") != "chat.send":
                    continue

                if self.gateway_send_ok:
                    await ws.send_json({"type": "res", "id": frame["id"], "ok": True, "payload": {}})
                    await ws.send_json(
                        {
                            "type": "event",
                            "event": "chat",
                            "payload": {
                                "runId": frame["id"],
                                "state": "delta",
                                "message": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "pong",
                                        }
                                    ]
                                },
                            },
                        }
                    )
                    await ws.send_json(
                        {
                            "type": "event",
                            "event": "chat",
                            "payload": {
                                "runId": frame["id"],
                                "state": "final",
                            },
                        }
                    )
                else:
                    await ws.send_json({"type": "res", "id": frame["id"], "ok": False, "error": "denied"})

            return ws

        app = web.Application()
        app.router.add_get("/", gateway_ws_handler)
        self.gateway_runner = web.AppRunner(app)
        await self.gateway_runner.setup()
        gateway_port = unused_port()
        self.gateway_site = web.TCPSite(self.gateway_runner, host="127.0.0.1", port=gateway_port)
        await self.gateway_site.start()

        os.environ["OPENCLAW_GATEWAY_URL"] = f"ws://127.0.0.1:{gateway_port}/"
        os.environ["OPENCLAW_GATEWAY_TOKEN"] = "gateway-test-token"

    async def _stop_gateway(self):
        if hasattr(self, "gateway_runner"):
            await self.gateway_runner.cleanup()

    async def _next_message(self, ws, timeout=2):
        msg = await ws.receive(timeout=timeout)
        assert msg.type == aiohttp.WSMsgType.TEXT
        return json.loads(msg.data)

    async def test_ws_connect_send_and_response_tracking(self):
        await self._start_gateway(send_ok=True)
        try:
            ws = await self.client.ws_connect(
                "/ws/chat?key=ws-secret", headers={"Origin": self.WS_ORIGIN}
            )
            connected = await self._next_message(ws)
            assert connected["type"] == "connected"
            history = await self._next_message(ws)
            assert history["type"] == "history"

            await ws.send_json({"message": "hello gateway"})
            send_ok = await self._next_message(ws)
            assert send_ok["type"] == "send_ok"
            assert isinstance(send_ok["id"], str)

            stream = await self._next_message(ws)
            assert stream == {"type": "stream", "delta": "pong"}
            stream_end = await self._next_message(ws)
            assert stream_end == {"type": "stream_end"}

            chat_send = next(
                frame for frame in self.gateway_messages if frame.get("type") == "req" and frame.get("method") == "chat.send"
            )
            assert chat_send["params"]["message"] == "hello gateway"
            assert send_ok["id"] == chat_send["id"]

            await ws.close()
            assert ws.closed
        finally:
            await self._stop_gateway()

    async def test_ws_rejects_bad_auth(self):
        os.environ["OPENCLAW_GATEWAY_TOKEN"] = "gateway-test-token"
        with self.assertRaises(aiohttp.WSServerHandshakeError) as ctx:
            await self.client.ws_connect("/ws/chat?key=wrong", headers={"Origin": self.WS_ORIGIN})
        assert ctx.exception.status == 401

    async def test_ws_rejects_forbidden_origin(self):
        await self._start_gateway(send_ok=True)
        os.environ["DASH_ALLOWED_ORIGINS"] = "https://dash.clwiop.xyz"
        try:
            with self.assertRaises(aiohttp.WSServerHandshakeError) as ctx:
                await self.client.ws_connect("/ws/chat?key=ws-secret", headers={"Origin": "https://evil.test"})
            assert ctx.exception.status == 403
        finally:
            await self._stop_gateway()

    async def test_ws_rejects_non_local_plaintext_gateway_url(self):
        os.environ["OPENCLAW_GATEWAY_URL"] = "ws://gateway.example.com"
        os.environ["OPENCLAW_GATEWAY_TOKEN"] = "gateway-test-token"
        ws = await self.client.ws_connect("/ws/chat?key=ws-secret", headers={"Origin": self.WS_ORIGIN})
        error = await self._next_message(ws)
        assert error["type"] == "error"
        assert "must use TLS" in error["text"]
        closed = await ws.receive(timeout=2)
        assert closed.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)

    async def test_ws_closes_on_message_too_large(self):
        await self._start_gateway(send_ok=True)
        try:
            ws = await self.client.ws_connect(
                "/ws/chat?key=ws-secret", headers={"Origin": self.WS_ORIGIN}
            )
            await self._next_message(ws)  # connected
            await self._next_message(ws)  # history
            await ws.send_json({"message": "x" * (MAX_CHAT_MESSAGE_BYTES + 1)})
            error = await self._next_message(ws)
            assert error == {"type": "error", "text": "Message too large"}
            closed = await ws.receive(timeout=2)
            assert closed.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)
        finally:
            await self._stop_gateway()

    async def test_ws_rejects_when_origin_allowlist_unset(self):
        await self._start_gateway(send_ok=True)
        os.environ.pop("DASH_ALLOWED_ORIGINS", None)
        os.environ["DASHBOARD_DEV_MODE"] = "0"
        try:
            with self.assertRaises(aiohttp.WSServerHandshakeError) as ctx:
                await self.client.ws_connect("/ws/chat?key=ws-secret", headers={"Origin": self.WS_ORIGIN})
            assert ctx.exception.status == 403
        finally:
            await self._stop_gateway()


class TestCSPHeaders(BaseApiTestCase):
    """Test Content-Security-Policy headers."""

    async def test_csp_header_present_on_responses(self):
        resp = await self.client.get("/api/system")
        csp = resp.headers.get("Content-Security-Policy")
        assert csp is not None, "CSP header missing"
        assert "default-src" in csp
        assert "'self'" in csp
