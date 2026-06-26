#!/usr/bin/env python3
import subprocess, os

os.chdir(os.path.expanduser("~/hermes-eats-world"))

# Rename local branch
result = subprocess.run(["git", "branch", "-m", "feat/phase0-sprint1"], capture_output=True, text=True)
print(f"Rename local: {result.stdout.strip() or result.stderr.strip()}")

# Delete remote main and push as feat/phase0-sprint1
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

# Push as new branch name (upstream will auto-create the branch ref)
result = subprocess.run(
    ["git", "push", push_url, "feat/phase0-sprint1:feat/phase0-sprint1"],
    capture_output=True, text=True, timeout=120
)
print(f"Push feat branch: {result.stdout.strip()}")
print(f"STDERR: {result.stderr.strip()}")
print(f"Exit: {result.returncode}")

# Delete remote main
result = subprocess.run(
    ["git", "push", push_url, "--delete", "main"],
    capture_output=True, text=True, timeout=120
)
print(f"Delete remote main: {result.stdout.strip()}")
print(f"STDERR: {result.stderr.strip()}")
print(f"Exit: {result.returncode}")
