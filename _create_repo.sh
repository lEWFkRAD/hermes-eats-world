#!/bin/bash
cd /c/Users/OnyxB/hermes-eats-world

TOKEN=$(grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')

echo "Token prefix: ${TOKEN:0:6}"

echo "Creating repo..."
RESPONSE=$(curl -s -X POST \
  -H "Authorization: token ${TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d '{"name":"hermes-eats-world","private":true,"auto_init":false,"description":"Hermes Agent desktop automation sidecar"}')

echo "API response:"
echo "${RESPONSE}" | head -5

echo ""
echo "Waiting 2s for repo creation..."
sleep 2

echo "Pushing to origin..."
git push -u origin main 2>&1
