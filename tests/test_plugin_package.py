from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_standalone_plugin_manifest_has_required_identity():
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")

    assert "manifest_version: 1" in manifest
    assert "name: hermes-eats-world" in manifest
    assert "version: 1.0.0" in manifest
    assert "kind: standalone" in manifest
    assert "  - windows" in manifest
    assert "  - uia_perceive_window" in manifest
    assert (ROOT / "__init__.py").is_file()


def test_package_exposes_hermes_plugin_entry_point():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '[project.entry-points."hermes_agent.plugins"]' in metadata
    assert 'hermes-eats-world = "sidecar.hermes_plugin:register"' in metadata


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
