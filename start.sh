#!/bin/bash
# Agent Orchestration Dashboard - Startup Script

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Agent Orchestration Dashboard${NC}"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Activate and install
echo "Installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo -e "${GREEN}✓ Ready${NC}"
echo ""

if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:8223 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Error: port 8223 is already in use. Stop the existing process before starting."
    exit 1
  fi
elif command -v ss >/dev/null 2>&1; then
  if ss -ltn | grep -q ':8223 '; then
    echo "Error: port 8223 is already in use. Stop the existing process before starting."
    exit 1
  fi
fi

echo "📡 Starting server on http://localhost:8223"
echo "Press Ctrl+C to stop"
echo ""

# OpenClaw gateway integration (for chat forwarding)
export OPENCLAW_GATEWAY_URL="${OPENCLAW_GATEWAY_URL:-http://localhost:18789}"
export OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:?OPENCLAW_GATEWAY_TOKEN must be set}"

# Start server
python server.py
