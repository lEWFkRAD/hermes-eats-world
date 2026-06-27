"""
Hermes Eats World — WebSocket Server
=====================================
Async WebSocket server that exposes the sidecar API over local WebSocket.

Hermes Agent connects to this server to drive Windows desktop apps remotely.
Runs on 127.0.0.1 (localhost only) with optional token authentication.

Usage:
    from sidecar.service.websocket_server import WebSocketServer

    server = WebSocketServer(host="127.0.0.1", port=8765)
    await server.start()
    # ... handle connections ...
    await server.stop()

Messages are JSON. Request/response pattern:
    Client → Server: {"id": 1, "method": "list_windows", "params": {}}
    Server → Client: {"id": 1, "result": [...]}
    Server → Client: {"id": 1, "error": "not found"}

Supported methods:
    - health: Health check
    - list_windows: List all visible windows
    - perceive_target: Walk UIA tree for a target window
    - run_goal: Run goal-directed automation
    - capture_screenshot: Screenshot of a window/element
"""

import asyncio
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol

from ..orchestrator import Orchestrator, OrchestratorConfig
from .service import ensure_environment, list_windows_api, perceive_target

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------

@dataclass
class WSRequest:
    """Incoming WebSocket request."""
    id: Any  # client-provided request ID (int, str, or None)
    method: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: str) -> "WSRequest":
        data = json.loads(raw)
        return cls(
            id=data.get("id"),
            method=data["method"],
            params=data.get("params", {}),
        )


@dataclass
class WSResponse:
    """Outgoing WebSocket response."""
    id: Any
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "result": self.result,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
        }


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class WebSocketServer:
    """WebSocket server exposing the sidecar API.

    Only binds to 127.0.0.1 by default (localhost only, not accessible from
    the network). Supports optional token authentication and rate limiting.

    Attributes:
        host: Bind address (default: 127.0.0.1).
        port: Bind port (default: 8765).
        token: Optional auth token. Clients send {"token": "..."} as first msg.
        max_connections: Max concurrent WebSocket connections (default: 5).
        request_timeout: Per-request timeout in seconds (default: 120).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: Optional[str] = None,
        max_connections: int = 5,
        request_timeout: float = 120.0,
    ):
        self.host = host
        self.port = port
        self.token = token
        self.max_connections = max_connections
        self.request_timeout = request_timeout

        self._server: Optional[Any] = None
        self._connections: Dict[WebSocketServerProtocol, str] = {}
        self._orchestrator: Optional[Orchestrator] = None
        self._started_at: Optional[float] = None
        self._request_count: int = 0
        self._running: bool = False

    @property
    def orchestrator(self) -> Orchestrator:
        if self._orchestrator is None:
            self._orchestrator = Orchestrator()
        return self._orchestrator

    # ─── Lifecycle ──────────────────────────────────────────────────

    async def start(self):
        """Start the WebSocket server."""
        logger.info("Starting WebSocket server on %s:%d", self.host, self.port)

        # Ensure environment is ready
        ensure_environment()

        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024,  # 10MB max message
            ping_interval=20,
            ping_timeout=20,
        )
        self._started_at = time.time()
        self._running = True
        logger.info(
            "WebSocket server listening on ws://%s:%d (max %d connections)",
            self.host, self.port, self.max_connections,
        )

    async def stop(self):
        """Stop the WebSocket server and close all connections."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for ws in list(self._connections.keys()):
            await ws.close()
        self._connections.clear()
        logger.info("WebSocket server stopped. Handled %d requests total.", self._request_count)

    async def _handler(self, ws: WebSocketServerProtocol, path: str = ""):
        """Handle a single WebSocket connection."""
        authenticated = False

        # Enforce max connections
        if len(self._connections) >= self.max_connections:
            await ws.close(1013, "Too many connections")
            return

        self._connections[ws] = datetime.now(timezone.utc).isoformat()
        logger.info("Client connected (%d active)", len(self._connections))

        try:
            async for raw in ws:
                self._request_count += 1

                # Auth check on first message
                if not authenticated:
                    if self.token:
                        try:
                            first_msg = json.loads(raw)
                            if first_msg.get("token") != self.token:
                                await ws.send(json.dumps({"error": "Authentication required"}))
                                await ws.close(4001, "Auth failed")
                                return
                            authenticated = True
                            logger.info("Client authenticated")
                            continue
                        except json.JSONDecodeError:
                            await ws.send(json.dumps({"error": "Auth token required"}))
                            await ws.close(4001, "Auth failed")
                            return
                    else:
                        authenticated = True

                # Parse and dispatch
                try:
                    request = WSRequest.from_json(raw)
                    start = time.time()

                    response = await self._dispatch(request)

                    response.duration_ms = (time.time() - start) * 1000
                    await ws.send(response.to_json())
                except Exception as e:
                    logger.exception("Unhandled error in request handler")
                    error_response = WSResponse(
                        id=None,
                        error=f"Internal error: {str(e)}",
                    )
                    await ws.send(error_response.to_json())

        except websockets.ConnectionClosed:
            logger.info("Client disconnected")
        finally:
            self._connections.pop(ws, None)

    # ─── Dispatch ───────────────────────────────────────────────────

    async def _dispatch(self, request: WSRequest) -> WSResponse:
        """Dispatch a request to the appropriate handler."""
        handlers = {
            "health": self._handle_health,
            "list_windows": self._handle_list_windows,
            "perceive_target": self._handle_perceive_target,
            "run_goal": self._handle_run_goal,
            "capture_screenshot": self._handle_capture_screenshot,
        }

        handler = handlers.get(request.method)
        if handler is None:
            return WSResponse(
                id=request.id,
                error=f"Unknown method: {request.method}. Available: {', '.join(handlers.keys())}",
            )

        try:
            result = await asyncio.wait_for(
                handler(request.params),
                timeout=self.request_timeout,
            )
            return WSResponse(id=request.id, result=result)
        except asyncio.TimeoutError:
            return WSResponse(
                id=request.id,
                error=f"Request timed out after {self.request_timeout}s",
            )
        except Exception as e:
            return WSResponse(
                id=request.id,
                error=f"{type(e).__name__}: {str(e)}",
            )

    # ─── Method handlers ────────────────────────────────────────────

    async def _handle_health(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Health check endpoint."""
        uptime = time.time() - self._started_at if self._started_at else 0
        return {
            "status": "ok",
            "version": "0.5.0",
            "uptime_seconds": round(uptime, 1),
            "connections": len(self._connections),
            "requests_handled": self._request_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_list_windows(self, params: Dict[str, Any]) -> list:
        """List all visible windows."""
        return list_windows_api()

    async def _handle_perceive_target(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perceive a target window's UIA tree."""
        title = params.get("title")
        process = params.get("process")
        window_class = params.get("class")
        max_depth = params.get("max_depth", 3)

        if not title and not process and not window_class:
            raise ValueError("At least one of title, process, or class is required")

        result = perceive_target(
            title=title,
            process=process,
            window_class=window_class,
            max_depth=max_depth,
        )
        return result

    async def _handle_run_goal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run goal-directed automation."""
        title = params.get("title")
        process = params.get("process")
        window_class = params.get("class")
        goal = params.get("goal")
        max_steps = params.get("max_steps", 20)
        recovery = params.get("recovery", "retry")

        if not goal:
            raise ValueError("goal is required")
        if not title and not process and not window_class:
            raise ValueError("At least one of title, process, or class is required")

        config = OrchestratorConfig(max_steps=max_steps)
        orch = Orchestrator(config=config)

        target = title or process or window_class
        result = orch.run(goal=goal, target_title=target)

        return {
            "goal": result.goal,
            "status": result.status.value,
            "steps_total": result.steps_total,
            "steps_completed": result.steps_completed,
            "elapsed": round(result.elapsed, 2),
        }

    async def _handle_capture_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Capture a screenshot of a window."""
        from ..capture.screenshot import capture_window

        title = params.get("title")
        process = params.get("process")
        output_path = params.get("output_path")

        if not title and not process:
            raise ValueError("At least one of title or process is required")

        return capture_window(title=title, process=process, output_path=output_path)

    # ─── Sync convenience ───────────────────────────────────────────

    def run_forever(self):
        """Run the server until interrupted. Convenience wrapper."""
        async def _run():
            await self.start()
            try:
                while self._running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                await self.stop()

        asyncio.run(_run())
