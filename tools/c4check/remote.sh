#!/usr/bin/env bash
# Uploaded helper: preserve every child status; do not filter stderr or output.
set -uo pipefail
cd /data/openpilot || exit 2
result=0
run_check() {
  local rc=0
  "$@" || rc=$?
  if (( rc > 2 )); then rc=2; fi
  if (( rc > result )); then result=$rc; fi
}
mode=${1:-}
shift || exit 2
if [[ $mode == boot ]]; then
  P=$(pgrep -fo '^[^ ]*python[0-9.]* .*manager[.]py') || { echo '판정 불가: manager 없음'; exit 2; }
  [[ -r /proc/$P/environ ]] || { echo '판정 불가: manager 환경 없음'; exit 2; }
  mapfile -d '' E < "/proc/$P/environ" || exit 2
  for script in buildcheck.py bootcheck.py mstate.py pandafaults.py jetlink.py; do
    echo "=== $script"
    run_check env -i "${E[@]}" PWD=/data/openpilot python3 "/tmp/chk/$script"
  done
elif [[ $mode == drives ]]; then
  if (( $# == 0 )); then
    routes_text=$(/usr/local/venv/bin/python3 - <<'PY'
from pathlib import Path
import re
routes={}
for p in Path('/data/media/0/realdata').iterdir():
  m=re.fullmatch(r'([A-Za-z0-9_-]+)--\d+',p.name)
  if p.is_dir() and m and (p/'qlog.zst').exists():
    routes[m[1]]=max(routes.get(m[1],0),(p/'qlog.zst').stat().st_mtime)
print('\n'.join(sorted(routes,key=routes.get)[-4:]))
PY
    ) || exit 2
    [[ -n $routes_text ]] || { echo '판정 불가: 주행 로그 없음'; exit 2; }
    mapfile -t routes <<< "$routes_text"
  else
    routes=("$@")
  fi
  for route in "${routes[@]}"; do
    [[ $route =~ ^[A-Za-z0-9_-]+--[A-Za-z0-9_-]+$ ]] || { echo '잘못된 route'; exit 2; }
    for script in drive.py stops.py; do
      echo "=== $script $route"
      run_check nice -n 19 env PYTHONPATH=/data/openpilot/pydeps:/data/openpilot /usr/local/venv/bin/python3 "/tmp/chk/$script" "$route"
    done
  done
else
  echo 'mode must be boot or drives'; exit 2
fi
exit "$result"
