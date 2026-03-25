#!/bin/bash
# Fetch the WhatsApp Click-to-Chat link from the production admin API.
# Usage: bash scripts/get_chat_link.sh

set -euo pipefail

ENV_FILE="$(dirname "$0")/../envs/.env.production"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env.production not found at $ENV_FILE"
  exit 1
fi

# Load only the vars we need (avoids polluting the shell environment)
BACKEND_URL=$(grep -E '^BACKEND_URL=' "$ENV_FILE" | cut -d '=' -f2-)
ADMIN_SECRET_KEY=$(grep -E '^ADMIN_SECRET_KEY=' "$ENV_FILE" | cut -d '=' -f2-)

if [ -z "$BACKEND_URL" ] || [ -z "$ADMIN_SECRET_KEY" ]; then
  echo "ERROR: BACKEND_URL or ADMIN_SECRET_KEY missing from .env.production"
  exit 1
fi

echo "Calling $BACKEND_URL/admin/chat-link ..."
echo

curl -s -X GET "$BACKEND_URL/admin/chat-link" \
  -H "X-ADMIN-KEY: $ADMIN_SECRET_KEY" \
  -H "Content-Type: application/json" | python3 -m json.tool
