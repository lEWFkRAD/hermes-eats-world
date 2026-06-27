"""Tests for sidecar.service.websocket_server — WebSocket models & serialization."""

import json
import pytest

from sidecar.service.websocket_server import (
    WSRequest,
    WSResponse,
)


class TestWSRequest:
    """Test WebSocket request model."""

    def test_basic_request(self):
        req = WSRequest(id=None, method="health")
        assert req.method == "health"
        assert req.params == {}
        assert req.id is None

    def test_request_with_int_id(self):
        req = WSRequest(id=42, method="list_windows")
        assert req.id == 42

    def test_request_with_str_id(self):
        req = WSRequest(id="abc", method="health")
        assert req.id == "abc"

    def test_request_with_params(self):
        req = WSRequest(
            id=1,
            method="run_goal",
            params={"goal": "click Save", "title": "Notepad"},
        )
        assert req.params["goal"] == "click Save"

    def test_from_json(self):
        raw = json.dumps({
            "id": 1,
            "method": "health",
            "params": {},
        })
        req = WSRequest.from_json(raw)
        assert req.id == 1
        assert req.method == "health"

    def test_from_json_no_id(self):
        raw = json.dumps({
            "method": "list_windows",
        })
        req = WSRequest.from_json(raw)
        assert req.id is None
        assert req.method == "list_windows"

    def test_from_json_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            WSRequest.from_json("not json")

    def test_from_json_missing_method_raises(self):
        raw = json.dumps({"params": {}})
        with pytest.raises(KeyError):
            WSRequest.from_json(raw)


class TestWSResponse:
    """Test WebSocket response model."""

    def test_success_response(self):
        resp = WSResponse(id=1, result={"status": "ok"})
        assert resp.result == {"status": "ok"}
        assert resp.error is None

    def test_error_response(self):
        resp = WSResponse(id=1, error="Something broke")
        assert resp.error == "Something broke"
        assert resp.result is None

    def test_duration(self):
        resp = WSResponse(id=1, result={}, duration_ms=42.5)
        assert resp.duration_ms == 42.5

    def test_to_json_success(self):
        resp = WSResponse(id=1, result={"count": 5})
        raw = resp.to_json()
        parsed = json.loads(raw)
        assert parsed["id"] == 1
        assert parsed["result"]["count"] == 5
        # error key is present but None
        assert parsed["error"] is None

    def test_to_json_error(self):
        resp = WSResponse(id=1, error="fail")
        raw = resp.to_json()
        parsed = json.loads(raw)
        assert parsed["error"] == "fail"
        # result key is present but None
        assert parsed["result"] is None

    def test_to_json_no_id(self):
        resp = WSResponse(id=None, error="anon error")
        raw = resp.to_json()
        parsed = json.loads(raw)
        assert parsed["id"] is None

    def test_to_dict(self):
        resp = WSResponse(id=1, result={"ok": True}, duration_ms=10.4)
        d = resp.to_dict()
        assert d["id"] == 1
        assert d["result"]["ok"] is True
        assert d["duration_ms"] == 10.4

    def test_roundtrip(self):
        req = WSRequest(id=99, method="health")
        resp = WSResponse(id=req.id, result={"status": "ok"})
        raw = resp.to_json()
        parsed = json.loads(raw)
        assert parsed["id"] == 99
        assert parsed["result"]["status"] == "ok"
