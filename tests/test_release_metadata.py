import re
from pathlib import Path

from sidecar.action.policy import POLICY_VERSION
from sidecar.plugin_runtime import PLUGIN_VERSION
from sidecar.schema import SCHEMA_VERSION

ROOT = Path(__file__).parents[1]


def project_version():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"$', metadata, re.MULTILINE)
    assert match
    return match.group(1)


def plugin_version():
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(\S+)$", manifest, re.MULTILINE)
    assert match
    return match.group(1)


def test_release_versions_are_synchronized():
    assert project_version() == "1.1.0"
    assert plugin_version() == project_version()
    assert SCHEMA_VERSION == project_version()
    assert POLICY_VERSION == project_version()
    assert PLUGIN_VERSION == project_version()


def test_changelog_contains_current_release():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## [{project_version()}]" in changelog
