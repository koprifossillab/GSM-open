#!/bin/bash
# 뷰어 컨테이너 시작.
set -e

cd /app/web

# ── 비밀키 ────────────────────────────────────────────────────────────
# `.env` 의 GSM_SECRET_KEY 가 비어 있으면 **여기서 만들어 자료 자리에 둔다.**
#
# 왜 이렇게 하는가: /srv/GSM/.env 는 배포한 사람(root)의 것이라 앱을 돌리는
# 사람이 못 고친다. 빈 값이면 Django 가 ImproperlyConfigured 로 **멈춘다** —
# 2026-09-23 첫 배포가 그렇게 멈췄다. 사람에게 다시 부탁하러 가는 대신,
# 쓸 수 있는 자리(DB 옆)에 한 번 만들어 두고 계속 쓴다.
#
# **워커가 아니라 여기서 만드는 것이 요점이다.** gunicorn 워커 셋이 저마다
# 만들면 서로 다른 키를 들게 되고, 그러면 세션이 워커를 옮길 때마다 풀린다.
if [[ -z "${GSM_SECRET_KEY:-}" ]]; then
    KEY_FILE="$(dirname "${GSM_DB_PATH:-/srv/GSM/db/GSM.db}")/secret_key"
    if [[ ! -s "$KEY_FILE" ]]; then
        python -c "import secrets; print(secrets.token_urlsafe(64))" > "$KEY_FILE"
        chmod 600 "$KEY_FILE" 2>/dev/null || true
        echo "비밀키를 새로 만들어 두었다: $KEY_FILE"
    fi
    export GSM_SECRET_KEY="$(cat "$KEY_FILE")"
fi

# ── cron 스크립트 ─────────────────────────────────────────────────────
# 호스트 cron 이 부르는 스크립트와 앱 코드 사본을 /srv/GSM/scripts 에 깐다 — 판을 올리면 cron 도 그 판을 돈다
# (koprifossillab 005). 그 자리를 마운트하지 않았으면 건너뛴다.
/app/deploy/scripts/install.sh /app "${GSM_SCRIPTS_DIR:-/srv/GSM/scripts}" || echo "스크립트를 옮기지 못했다 — 화면은 뜬다"

# 이미 적용돼 있으면 아무 일도 하지 않는다. 새 장비에 올릴 때를 위해 둔다.
python manage.py migrate --noinput

# 카탈로그가 비어 있으면 저장소에 든 씨앗으로 채운다. 상류를 타지 않는다.
python manage.py seed_catalog || echo "씨앗을 넣지 못했다 — 화면은 뜬다"
# 받아 두는 자료원의 명세 — 운영에 없는 id 만 덧붙인다 (jikhanjung P02)
python manage.py sources_seed || echo "자료원 명세를 놓지 못했다 — 화면은 뜬다"

# ── 기록 ──────────────────────────────────────────────────────────────
# 판을 다시 띄우면 docker logs 가 사라진다 — 붙은 자리(DB 옆)에 하루 한 장씩 남긴다. 30 일, 하루 한 장 50 MB 까지 (wetherilli 351)
export GSM_LOG_DIR="${GSM_LOG_DIR:-$(dirname "${GSM_DB_PATH:-/srv/GSM/db/GSM.db}")/logs}"
mkdir -p "$GSM_LOG_DIR" 2>/dev/null || { echo "기록 자리를 만들지 못했다 — 화면에만 낸다: $GSM_LOG_DIR"; GSM_LOG_DIR=""; }

# --timeout 60 은 요청 한계가 아니다 — 스레드 워커(gthread)는 워커가 살아 있는지만 본다. 요청의 한계는 nginx 90 초 > 문 60 초 + 잠금 20 초 (wetherilli 300)
exec gunicorn gsmweb.wsgi:application \
    --config /app/deploy/gunicorn.conf.py \
    --bind 0.0.0.0:9090 \
    --workers 3 \
    --threads 8 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
