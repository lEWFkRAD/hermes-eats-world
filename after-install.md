# Hermes Eats World installed

Hermes installed this plugin in the active profile's persistent plugin directory.

1. Install the package and dependencies into Hermes's Python environment with
   `python -m pip install -e <this-plugin-directory>`.
2. Restart the active profile's gateway.
3. Confirm `hermes tools` lists `uia_perceive_window`.
4. Open an interactive Windows desktop session and confirm only the expected
   windows are visible to the sidecar.
5. In Hermes HUD mode, pass a fresh `read_window_below.window.id` to the
   `uia_perceive_window` tool; do not reuse the handle after moving the HUD or
   switching applications.
6. Keep raw UI values disabled. Use the CLI's `--include-raw-values` only for a scoped,
   approved debugging session.
7. Keep action execution disabled until the intended HWND is explicitly
   allowlisted and before/after conditions are defined.

For additional profiles, install the package only once and enable the entry-point
plugin separately with `hermes -p <profile> plugins enable hermes-eats-world`.
Plugin state and responses remain scoped to the active profile's `HERMES_HOME`.

Read `SECURITY.md` before enabling this sidecar on a workstation containing
client, financial, health, credential, or other sensitive information.
