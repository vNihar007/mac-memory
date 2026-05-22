#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
UV="$(command -v uv)"
PLIST="$HOME/Library/LaunchAgents/com.macmemory.daemon.plist"
mkdir -p "$HOME/.mac-memory"
cd "$REPO" && "$UV" sync
sed "s#__UV__#$UV#g; s#__REPO__#$REPO/src#g; s#__HOME__#$HOME#g" \
  "$REPO/scripts/daemon.plist.tmpl" > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "mac-memory daemon installed. Health:"; sleep 2; curl -s localhost:8765/health