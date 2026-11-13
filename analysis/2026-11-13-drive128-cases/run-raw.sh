# [클코] 기기에서 실행합니다(정차 중, 읽기 전용). 128 정체 구간(15:39~15:50) 앞뒤를 포함한 구간 16~31을 코덱 형식 raw로 압축해 뽑습니다.
set -euo pipefail
cd /data/openpilot
test "$(cat /data/params/d/IsOffroad)" = 1
P=$(pgrep -fo '^[^ ]*python[0-9.]* .*manager[.]py')
mapfile -d '' E < /proc/$P/environ
D=/tmp/c4-drive128
env -i "${E[@]}" PWD=/data/openpilot PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 nice -n 15 python3 -B $D/extract_raw.py 00000128--996b87d9ef $(seq 16 31) 2> $D/raw128.stderr | gzip > $D/raw128.jsonl.gz
ls -la $D/raw128.jsonl.gz; tail -n 1 $D/raw128.stderr; grep -ci traceback $D/raw128.stderr || true
