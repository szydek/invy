#!/bin/bash
set -e

echo "▶ Activating virtualenv"
. ~/venv/bin/activate

echo "▶ Loading environment"
. ./.env

echo "▶ Ensuring Colima is running"
colima start >/dev/null 2>&1 || true

# echo "▶ Ensuring DokuWiki container is running"
# if ! docker ps --format '{{.Names}}' | grep -q '^dokuwiki$'; then
#  if docker ps -a --format '{{.Names}}' | grep -q '^dokuwiki$'; then
#    docker start dokuwiki
#  else
#    echo "❌ dokuwiki container not found"
#    echo "   (expected container name: dokuwiki)"
#    exit 1
#  fi
# fi

echo "▶ Starting Flask app"
python3 ./app.py

