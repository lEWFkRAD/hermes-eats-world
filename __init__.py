"""Hermes plugin entry point for directory-based installations."""

if __package__:
    from .sidecar.hermes_plugin import register
else:  # Pytest may import a repository-root __init__.py as a top-level module.
    from sidecar.hermes_plugin import register

__all__ = ["register"]
