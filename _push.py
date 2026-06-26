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

if not token:
    print("ERROR: No token")
    exit(1)

push_url = f"https://{token}@github.com/lEWFkRAD/hermes-eats-world.git"

result = subprocess.run(
    ["git", "push", "-u", push_url, "main"],
    capture_output=True, text=True, timeout=120
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print(f"Exit code: {result.returncode}")
