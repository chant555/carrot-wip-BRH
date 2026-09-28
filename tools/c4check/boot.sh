#!/usr/bin/env bash
# PC에서 실행. 읽기 전용 점검 파일만 /tmp/chk에 업로드한다.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
ssh -o ConnectTimeout=8 c4 'mkdir -p /tmp/chk'
scp -q "$D"/*.py "$D/remote.sh" c4:/tmp/chk/
ssh -o ConnectTimeout=8 c4 'bash /tmp/chk/remote.sh boot'
