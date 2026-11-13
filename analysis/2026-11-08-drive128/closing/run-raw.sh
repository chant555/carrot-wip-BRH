set -euo pipefail
cd /data/openpilot
P=$(pgrep -fo '^[^ ]*python[0-9.]* .*manager[.]py')
mapfile -d '' E < /proc/$P/environ
env -i "${E[@]}" PWD=/data/openpilot PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 python3 -B /tmp/c4-drive128-closing.py
