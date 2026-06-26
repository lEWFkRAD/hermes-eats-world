#!/usr/bin/env python3
import subprocess, os

os.chdir(os.path.expanduser("~/hermes-eats-world"))

creds_path = os.path.expanduser("~/.git-credentials")
token = None
with open(creds_path, 'r') as f:
    for line in f:
        if "github.com" in line:
            parts = line.strip().split(":", 2)
            if len(parts) >= 3:
                token = parts[2].split("@")[0]
            break

push_url = f"https://{token}@github.com/lEWFkRAD/hermes-eats-world.git"

# Force push orphan branch as main
result = subprocess.run(
    ["git", "push", "--force", push_url, "main-init:main"],
    capture_output=True, text=True, timeout=120
)
print(f"Force push main: exit={result.returncode}")
print(f"STDOUT: {result.stdout.strip()}")
print(f"STDERR: {result.stderr.strip()}")

# Switch back to feature branch
subprocess.run(["git", "checkout", "feat/phase0-sprint1"], capture_output=True)
print("Switched back to feat/phase0-sprint1")

# Delete temp branch
subprocess.run(["git", "branch", "-D", "main-init"], capture_output=True)
print("Deleted main-init branch")
