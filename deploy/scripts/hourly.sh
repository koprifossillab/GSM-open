#!/bin/bash
# 매시 한 번 — 상류에서 시시각각 바뀌는 것을 받는 일을 차례로 부른다 (koprifossillab 013). cron 에는 이 한 줄뿐이다.
#
#   /srv/GSM/scripts/hourly.sh            아래 일을 다 부른다
#   /srv/GSM/scripts/hourly.sh fetch_gmgsi   이 일만
#
# 일은 저마다 따로 남는다 — `run.sh <관리 명령>` 으로 손으로도 부를 수 있다. 여기는 차례와 기록만 맡는다.
#   fetch_gfs_wind   지금의 바람·구름 (GFS 분석과 +12 시간까지 예보, koprifossillab 003·008·011)
#   fetch_gmgsi      위성 구름 (NOAA GMGSI, koprifossillab 012)
#   fetch_araon      아라온호 위치 (극지연구소, koprifossillab 004)
#
# 한 일이 멈추거나 늦어도 다음 일은 부른다. 일마다 timeout 이 있다.
#
# 기록 둘:
#   /data/GSM/logs/hourly.log          일마다 머리줄(시각·일 이름) 아래에 그 일이 낸 것을 그대로
#   <DB 옆>/hourly_status.json         일마다 결과·걸린 초·마지막 줄·마지막으로 된 때. `/GSM/healthz/` 가 읽는다 — 로그 자리는
#                                       컨테이너에 붙어 있지 않아 DB 옆에 둔다(주간 백업의 `backup_status.json` 과 같다)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS="${GSM_HOURLY_STATUS:-/srv/GSM/db/hourly_status.json}"
LOG="${GSM_HOURLY_LOG:-/data/GSM/logs/hourly.log}"
JOBS=(fetch_gfs_wind fetch_gmgsi fetch_araon)
[[ $# -gt 0 ]] && JOBS=("$@")
LIMIT=900                    # 일 하나에 주는 초 — 판이 오른 뒤 첫 차례는 venv 를 새로 만들어 길다

mkdir -p "$(dirname "$LOG")"
exec 9>"$HERE/.hourly.lock"
flock -n 9 || { echo "$(date -Is) hourly 가 이미 돌고 있다 — 건너뜀" >> "$LOG"; exit 0; }

OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT

for job in "${JOBS[@]}"; do
    started=$(date +%s)
    echo "== $(date -Is) $job" >> "$LOG"
    timeout "$LIMIT" "$HERE/run.sh" "$job" > "$OUT" 2>&1
    code=$?
    cat "$OUT" >> "$LOG"
    seconds=$(( $(date +%s) - started ))
    # 마지막 줄 — 로그 줄(INFO …)은 건너뛰고 명령이 사람에게 한 말을
    note=$(grep -v -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9:,.+]+ (INFO|DEBUG|WARNING) ' "$OUT" | grep -v '^\s*$' | tail -1)
    [[ $code -eq 124 ]] && note="${LIMIT}초를 넘겨 멈췄다"
    echo "-- $job 끝: 코드 $code, ${seconds}초" >> "$LOG"
    # 상태 파일은 일마다 고쳐 쓴다 — 지난번의 "마지막으로 된 때" 를 지키려고 읽어서 고친다
    /usr/bin/python3 - "$STATUS" "$job" "$code" "$seconds" "$note" <<'EOF'
import datetime, json, os, sys
path, job, code, seconds, note = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
try:
    with open(path, encoding="utf-8") as f:
        status = json.load(f)
except (OSError, ValueError):
    status = {}
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
jobs = status.setdefault("jobs", {})
entry = jobs.setdefault(job, {})
entry.update(at=now, result="ok" if code == 0 else "fail", code=code, seconds=seconds, note=note[:300])
if code == 0:
    entry["last_ok"] = now
status["at"] = now
tmp = path + ".part"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(status, f, ensure_ascii=False, indent=1)
os.replace(tmp, path)
EOF
done
echo "== $(date -Is) 끝" >> "$LOG"
