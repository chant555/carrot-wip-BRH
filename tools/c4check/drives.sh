#!/usr/bin/env bash
# PC에서 실행: bash tools/c4check/drives.sh [route ...]
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
for route in "$@"; do
  [[ $route =~ ^[A-Za-z0-9_-]+--[A-Za-z0-9_-]+$ ]] || { echo '잘못된 route'; exit 2; }
done
ssh -o ConnectTimeout=8 c4 'mkdir -p /tmp/chk'
scp -q "$D"/*.py "$D/remote.sh" c4:/tmp/chk/
# Only the validated ASCII identifier alphabet reaches the remote command.
ssh -o ConnectTimeout=8 c4 "bash /tmp/chk/remote.sh drives $*"
