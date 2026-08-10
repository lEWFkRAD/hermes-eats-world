# Hermes Eats World installed

Hermes installed this plugin in the active profile's persistent plugin directory.

1. Run `hermes heaw setup` to create a versioned UIA runtime under the active
   profile's `HERMES_HOME`; Hermes's own Python environment is not modified.
2. Restart this profile's gateway with `hermes gateway restart`.
3. Confirm `hermes heaw status` reports `ready` and `hermes tools` lists
   `uia_perceive_window`.
4. Open an interactive Windows desktop session and confirm only the expected
   windows are visible to the sidecar.
5. In Hermes HUD mode, pass a fresh `read_window_below.window.id` to the
   `uia_perceive_window` tool; do not reuse the handle after moving the HUD or
   switching applications.
6. Treat every UI tree as sensitive. ValuePattern text and password controls are
   redacted, but labels, titles, geometry, and AutomationIds can still disclose data.
7. Keep action execution disabled until the intended HWND is explicitly
   allowlisted and before/after conditions are defined.

For additional profiles, run `hermes profile use <profile>`, then `hermes plugins
install lEWFkRAD/hermes-eats-world --enable`, `hermes heaw setup`, and `hermes
gateway restart`. Profile selection is sticky in Hermes 0.20; switch back with
`hermes profile use default` when finished. Plugin state, runtime dependencies,
and responses remain scoped to the active profile's `HERMES_HOME`.

Read `SECURITY.md` before enabling this sidecar on a workstation containing
client, financial, health, credential, or other sensitive information.
