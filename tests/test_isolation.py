import time

from sidecar.service.isolation import run_isolated
from tests.isolation_helpers import exit_without_result, hang_forever, raise_error, return_value


def test_isolated_worker_returns_value():
    result = run_isolated(return_value, {"ok": True}, timeout=5)

    assert result.status == "success"
    assert result.value == {"ok": True}
    assert result.exit_code == 0


def test_isolated_worker_returns_structured_exception():
    result = run_isolated(raise_error, timeout=5)

    assert result.status == "error"
    assert result.error == "ValueError: worker boom"
    assert "raise ValueError" in result.traceback


def test_isolated_worker_is_forcefully_terminated_on_timeout():
    started = time.monotonic()
    result = run_isolated(hang_forever, timeout=0.2)

    assert result.status == "timeout"
    assert time.monotonic() - started < 3
    assert result.exit_code is not None


def test_isolated_worker_reports_crash_without_payload():
    result = run_isolated(exit_without_result, timeout=5)

    assert result.status == "crash"
    assert result.exit_code == 7
