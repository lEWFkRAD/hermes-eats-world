# Hermes Eats World installed

Hermes installed this standalone plugin in its persistent user-plugin directory.

1. Open an interactive Windows desktop session.
2. Run `hermes eats-world check` when the plugin command is available, or run
   `heaw --list` directly from the installed Python environment.
3. Confirm only the expected windows are visible to the sidecar.
4. Keep raw UI values disabled. Use `--include-raw-values` only for a scoped,
   approved debugging session.
5. Keep action execution disabled until the intended HWND is explicitly
   allowlisted and before/after conditions are defined.

Read `SECURITY.md` before enabling this sidecar on a workstation containing
client, financial, health, credential, or other sensitive information.
