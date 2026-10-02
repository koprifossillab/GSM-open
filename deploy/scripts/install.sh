#!/bin/bash
# cron 이 부르는 스크립트와 그것이 쓰는 앱 코드를 `/srv/GSM/scripts/` 에 옮긴다 (koprifossillab 005).
#
#   install.sh [원본] [자리]        원본 기본 /app(이미지 안), 자리 기본 /srv/GSM/scripts
#
# **컨테이너가 뜰 때 entrypoint 가 부른다** — 그래서 판을 올리면 cron 이 도는 것도 같은 판이 된다. 저장소에서
# 손으로 부를 수도 있다(`deploy/scripts/install.sh . /srv/GSM/scripts`) — 판을 올리기 전에 고친 것을 돌려 볼 때다.
#
# 옮기는 것
#   *.sh                   이 디렉토리의 스크립트 (run.sh·weekly_backup.sh …)
#   app/                   앱 코드 사본 — web/{manage.py,gsmweb,viewer}·data/·requirements. 관리 명령이 viewer 를 타므로
#                          코드가 함께 가야 한다. 정적 파일·시험은 cron 이 쓰지 않아 뺀다
# 옮기지 않는 것
#   venv/                  호스트가 만든다(run.sh). 컨테이너의 파이썬은 /usr/local 이라 호스트에서 못 쓴다
#
# 자리가 없거나 쓸 수 없으면 아무것도 하지 않는다 — 마운트하지 않은 compose 로 떠도 화면은 뜬다.
set -euo pipefail

SRC="${1:-/app}"
DEST="${2:-/srv/GSM/scripts}"
SRC="$(cd "$SRC" && pwd)"

if [[ ! -d "$DEST" || ! -w "$DEST" ]]; then
    echo "스크립트 자리($DEST)가 없거나 쓸 수 없다 — 옮기지 않는다"
    exit 0
fi

# venv 를 맞출 requirements — 바람은 numpy·ecCodes·numcodecs 를 쓴다(koprifossillab P02). 운영 이미지에는 없다
REQS=(requirements-web.txt requirements-wind.txt)

stage="$DEST/.app.new"
rm -rf "$stage"
mkdir -p "$stage"
tar -C "$SRC" -cf - \
    --exclude=__pycache__ --exclude='*.pyc' \
    --exclude=web/viewer/static --exclude=web/viewer/tests --exclude='data/*.xml' \
    web/manage.py web/gsmweb web/viewer data "${REQS[@]}" \
  | tar -C "$stage" -xf -

# 다 풀고 나서 바꿔 끼운다 — 옮기다 멈춰도 앞의 사본이 깨지지 않는다
rm -rf "$DEST/.app.old"
[[ -d "$DEST/app" ]] && mv "$DEST/app" "$DEST/.app.old"
mv "$stage" "$DEST/app"
rm -rf "$DEST/.app.old"

for f in "$SRC"/deploy/scripts/*.sh; do
    install -m 755 "$f" "$DEST/"
done
version="$(sed -n 's/^VERSION *= *"\(.*\)"/\1/p' "$SRC/web/gsmweb/version.py" 2>/dev/null || true)"
echo "${version:-?} $(date -Is)" > "$DEST/app/INSTALLED"
echo "스크립트를 옮겼다: $DEST (판 ${version:-?})"
