## Summary

## Why

Closes #

## Testing

- [ ] `python -m ruff check sidecar tests`
- [ ] `python -m pytest -q`
- [ ] `python -m build --wheel`
- [ ] Live Windows UIA smoke test (only check if performed)

## Safety and compatibility

- [ ] No secrets, screenshots, UI snapshots, client data, or unsanitized logs
- [ ] Raw UI values remain redacted by default
- [ ] UIA worker isolation and traversal limits remain intact
- [ ] Action execution remains deny-by-default and HWND-scoped
- [ ] Stale-state and post-action verification remain intact
- [ ] README/security documentation updated where needed

## AI assistance

Describe AI-assisted work and the human review performed.

## Live verification

State exactly which real applications were tested versus mocks or fixtures.
