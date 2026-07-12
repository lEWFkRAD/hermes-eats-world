from sidecar.service.env_check import EnvCheckResult


def test_report_is_safe_for_legacy_windows_consoles():
    result = EnvCheckResult(info={"Platform": "Windows"})
    result.add_warning("limited access")

    report = result.report()

    report.encode("cp1252")
    assert "WARNING: limited access" in report
    assert "Result: PASS" in report
