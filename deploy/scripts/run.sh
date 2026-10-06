#!/bin/bash
# cron 이 관리 명령을 부르는 문 — 전용 venv 로 `app/` 의 사본을 돌린다 (koprifossillab 005).
#
#   /srv/GSM/scripts/run.sh fetch_araon
#   /srv/GSM/scripts/run.sh fetch_gfs_wind
#
# **venv 는 스스로 맞춘다.** `app/requirements-*.txt` 와 호스트 파이썬 판의 지문을 `venv/.stamp` 에 적어 두고,
# 판이 올라 requirements 가 바뀌면 다음 차례에 다시 만든다. 사람이 venv 를 손볼 일이 없게 하려는 것이다.
# 다시 만드는 동안 다른 명령은 기다린다(flock — 돌고 있는 명령은 공유 잠금, 만드는 쪽은 배타 잠금).
#
# 같은 명령이 겹치면 뒤의 것은 건너뛴다 — 상류가 느려 한 시간을 넘겨도 두 벌이 돌지 않는다.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/app"
VENV="$HERE/venv"
PY="${GSM_SCRIPTS_PYTHON:-/usr/bin/python3}"

[[ $# -gt 0 ]] || { echo "쓰임: $(basename "$0") <관리 명령> [인자...]" >&2; exit 2; }
[[ -f "$APP/web/manage.py" ]] || { echo "$APP 에 앱이 없다 — install.sh 가 아직 돌지 않았다" >&2; exit 1; }

exec 7>"$HERE/.$1.lock"
flock -n 7 || { echo "$(date -Is) $1 이 이미 돌고 있다 — 건너뜀"; exit 0; }

stamp() {
    { "$PY" -c 'import sys; print(sys.version)'; cat "$APP"/requirements-*.txt; } | sha256sum | cut -d' ' -f1
}

exec 8>"$HERE/.venv.lock"
flock -s 8
want="$(stamp)"
if [[ "$(cat "$VENV/.stamp" 2>/dev/null)" != "$want" ]]; then
    flock -x 8
    if [[ "$(cat "$VENV/.stamp" 2>/dev/null)" != "$want" ]]; then
        echo "$(date -Is) venv 를 새로 만든다 ($VENV)"
        rm -rf "$VENV"
        "$PY" -m venv "$VENV"
        "$VENV/bin/pip" install -q --upgrade pip
        for req in "$APP"/requirements-*.txt; do
            "$VENV/bin/pip" install -q -r "$req"
        done
        echo "$want" > "$VENV/.stamp"           # 다 깔린 뒤에만 적는다 — 깔다 멈추면 다음 차례에 다시 한다
    fi
    flock -s 8
fi

export GSM_DB_PATH="${GSM_DB_PATH:-/srv/GSM/db/GSM.db}"
# 호스트에서 돈다 — 기록 표(store.sqlite)에 쓰지 않고 hourly_status.json·fetch_log_host.jsonl 에 남긴다 (jikhanjung P02)
export GSM_RUN_PLACE=host
export GSM_DEBUG="${GSM_DEBUG:-0}"
cd "$APP/web"
"$VENV/bin/python" manage.py "$@"
