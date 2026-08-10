import json
from pathlib import Path
from types import SimpleNamespace

from sidecar import plugin_runtime


def test_runtime_path_is_scoped_to_active_hermes_home(monkeypatch, tmp_path):
    work = tmp_path / "work"
    personal = tmp_path / "personal"

    monkeypatch.setenv("HERMES_HOME", str(work))
    work_runtime = plugin_runtime.runtime_dir()
    monkeypatch.setenv("HERMES_HOME", str(personal))
    personal_runtime = plugin_runtime.runtime_dir()

    assert work_runtime != personal_runtime
    assert "hermes-eats-world" in str(work_runtime)
    assert work_runtime.name == plugin_runtime.PLUGIN_VERSION


def test_setup_uses_short_windows_safe_transient_names(monkeypatch, tmp_path):
    target = tmp_path / "deep-profile-root" / "plugin-runtimes" / "hermes-eats-world" / "1.1.0"
    commands = []

    monkeypatch.setattr(plugin_runtime, "runtime_dir", lambda: target)

    def fake_run(command, **_kwargs):
        commands.append(command)
        if command[1:3] == ["-m", "venv"]:
            staging = Path(command[3])
            (staging / "Scripts").mkdir(parents=True)
            (staging / "Scripts" / "python.exe").write_text("", encoding="utf-8")

    monkeypatch.setattr(plugin_runtime, "_run_checked", fake_run)

    result = plugin_runtime.setup_runtime()

    transient = Path(commands[0][3]).name
    assert transient.startswith(".stg-")
    assert len(transient) <= 13
    assert result == target


def test_worker_transport_sanitizes_child_stderr(monkeypatch, tmp_path):
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(plugin_runtime, "runtime_python", lambda: python)

    class FailedProcess:
        returncode = 1

        def communicate(self, _input=None, timeout=None):
            return "", "client-secret-123"

    monkeypatch.setattr(plugin_runtime.subprocess, "Popen", lambda *a, **k: FailedProcess())

    result = plugin_runtime.run_runtime_worker({"window_id": 1}, timeout=1)

    assert result["error"] == "tree_worker_failed"
    assert "client-secret-123" not in json.dumps(result)


def test_status_reports_profile_runtime(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(plugin_runtime, "runtime_available", lambda: True)
    monkeypatch.setattr(plugin_runtime, "runtime_dir", lambda: Path(tmp_path))
    args = SimpleNamespace(heaw_command="status")

    assert plugin_runtime.handle_cli(args) == 0
    assert "ready" in capsys.readouterr().out
