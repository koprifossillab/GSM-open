#!/bin/sh
# 연구소 밖 정적 판을 구워 GSM-open 의 gh-pages 가지로 민다 — https://koprifossillab.github.io/GSM-open/ (wetherilli P11·162).
#
#   sh deploy/publish_pages.sh [bake_static 의 출력 폴더]
#
# 판 세션이 판을 올린 뒤 `publish_open.sh`(소스)에 이어 부른다. gh-pages 는 **한 커밋만** 둔다 — 판마다 통째로
# 새로 굽고 덮는다(역사를 쌓으면 구운 타일이 저장소를 키운다). Pages 의 Source 는 저장소 주인이 한 번
# "Deploy from a branch → gh-pages / (root)" 로 켜 둔다.
#
# 굽는 데에 운영 DB 를 쓰지 않는다 — static_site.py 가 빈 DB 에 씨앗만 넣는다. 인증키도 싣지 않는다.
set -eu

BAKED="${1:-}"
OPEN="${GSM_OPEN_REPO:-https://github.com/koprifossillab/GSM-open.git}"
cd "$(dirname "$0")/.."
PY="${GSM_PYTHON:-$HOME/venv/GSM/bin/python}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ -n "$BAKED" ]; then
  "$PY" deploy/static_site.py "$WORK/site" --baked "$BAKED"
else
  "$PY" deploy/static_site.py "$WORK/site"
fi

# 밀기 전에 구운 판을 띄워 브라우저로 열어 본다 — 깨지면 밀지 않는다(set -e). 브라우저가 없으면 건너뛴다 (wetherilli 315).
# 급할 때만 GSM_SKIP_SMOKE=1
if [ "${GSM_SKIP_SMOKE:-}" != "1" ]; then
  "$PY" deploy/static_smoke.py "$WORK/site"
fi

VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' web/gsmweb/version.py)"
cd "$WORK/site"
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$OLDPWD" config user.name || echo GSM)" \
    -c user.email="$(git -C "$OLDPWD" config user.email || echo gsm@localhost)" \
    commit -q -m "정적 판 v$VERSION

개발 저장소(koprifossillab/GSM)의 deploy/static_site.py 가 구웠다 — 소스는 이 저장소의 main"
git push -q --force "$OPEN" gh-pages
echo "GSM-open 의 gh-pages 에 정적 판 v$VERSION 을 밀었다 — https://koprifossillab.github.io/GSM-open/"
