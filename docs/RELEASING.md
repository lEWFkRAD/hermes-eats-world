# Releasing Hermes Eats World

Releases are created only from a reviewed, green commit on `main`.

## Prepare

1. Update `pyproject.toml`, `plugin.yaml`, `SCHEMA_VERSION`, and
   `POLICY_VERSION` intentionally.
2. Update `CHANGELOG.md` and the README support boundary.
3. Run:

   ```powershell
   python -m ruff check sidecar tests
   python -m pytest -q
   python -m build --wheel
   git diff --check
   ```

4. Merge the release PR after required CI and review are complete.

## Publish

From an up-to-date `main` checkout:

```powershell
git pull --ff-only origin main
git tag -s v1.0.0 -m "Hermes Eats World v1.0.0"
git push origin v1.0.0
```

If signed tags are unavailable for a documented reason, use an annotated tag.
The tag-triggered release workflow verifies that the tag matches all version
sources, reruns tests, builds the wheel, and creates the GitHub Release with the
wheel attached.

Do not tag a feature branch or create a release before the PR merges.
