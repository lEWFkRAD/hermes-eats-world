from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).parents[1]


def test_standalone_plugin_manifest_has_required_identity():
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")

    assert "manifest_version: 1" in manifest
    assert "name: hermes-eats-world" in manifest
    assert "version: 1.1.0" in manifest
    assert "kind: standalone" in manifest
    assert "  - windows" in manifest
    assert "  - uia_perceive_window" in manifest
    assert (ROOT / "__init__.py").is_file()


def test_package_exposes_hermes_plugin_entry_point():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '[project.entry-points."hermes_agent.plugins"]' in metadata
    assert 'hermes-eats-world = "sidecar.hermes_plugin:register"' in metadata
    assert (ROOT / "sidecar" / "runtime-requirements.txt").is_file()


def test_base_wheel_has_no_host_dependencies_and_runtime_is_explicit():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["dependencies"] == []
    assert metadata["project"]["optional-dependencies"]["runtime"]


def test_plugin_package_contains_operator_and_security_guidance():
    for filename in (
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "AGENTS.md",
        "after-install.md",
        "LICENSE",
    ):
        assert (ROOT / filename).is_file(), filename


def test_repository_has_structured_submission_templates():
    template_dir = ROOT / ".github" / "ISSUE_TEMPLATE"

    assert (template_dir / "bug_report.yml").is_file()
    assert (template_dir / "feature_request.yml").is_file()
    assert (template_dir / "config.yml").is_file()
    assert (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file()
    assert (ROOT / ".github" / "dependabot.yml").is_file()


def test_github_actions_are_pinned_to_commit_shas():
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if "uses: actions/" in line:
                reference = line.split("@", 1)[1].split()[0]
                assert len(reference) == 40, (workflow.name, line)
                assert all(character in "0123456789abcdef" for character in reference)
