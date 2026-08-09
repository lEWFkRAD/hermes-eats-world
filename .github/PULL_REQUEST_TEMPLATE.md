## Summary

## Why

Closes #

## Testing

- [ ] `python -m ruff check sidecar scripts tests`
- [ ] `python -m pytest -q`
- [ ] `python -m build --wheel`
- [ ] Live Windows UIA smoke test (only check if performed)

## Submission

- [ ] I searched existing issues and pull requests
- [ ] A tracking issue exists for substantial or security-boundary work
- [ ] Every commit is signed off under the DCO (`git commit -s`)
- [ ] Required CI passes and all review conversations are resolved before merge

## Safety and compatibility

- [ ] No secrets, screenshots, UI snapshots, client data, or unsanitized logs
- [ ] Raw UI values remain redacted by default
- [ ] UIA worker isolation and traversal limits remain intact
- [ ] Action execution remains deny-by-default and HWND-scoped
- [ ] Stale-state and post-action verification remain intact
- [ ] README/security documentation updated where needed
- [ ] I reviewed and understand all submitted code

## AI assistance

Describe AI-assisted work and the human review performed.

## Live verification

State exactly which real applications were tested versus mocks or fixtures.
