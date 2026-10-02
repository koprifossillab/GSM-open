#!/bin/bash
# /srv/GSM 을 세우고 nginx 에 얹고 paleolab 첫 화면에 카드를 건다.
#
#   sudo deploy/host/install-srv.sh
#
# **root 가 필요한 일만 모아 둔 것이다.** /srv 는 root 소유라 디렉토리를 못 만들고,
# /etc/nginx 와 /srv/paleolab/index.html 도 마찬가지다. 굽기와 시험은 sudo 없이
# 되므로 여기 넣지 않았다 (deploy/host/deploy.sh).
#
# 여러 번 돌려도 된다. 이미 되어 있는 것은 건드리지 않고, 고치기 전에 사본을 둔다.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRV=/srv/GSM
LANDING=/srv/paleolab/index.html
SNIPPET=/etc/nginx/snippets/GSM-subpath.conf
SITE=/etc/nginx/sites-enabled/phyloserver
OWNER=paleoadmin:paleoadmin
STAMP="$(date +%Y%m%d_%H%M%S)"

if [[ $EUID -ne 0 ]]; then
    echo "root 로 돌려야 한다: sudo $0" >&2
    exit 1
fi

say() { printf '\n== %s ==\n' "$1"; }

# ── 1. /srv/GSM ───────────────────────────────────────────────────────
say "/srv/GSM"
mkdir -p "$SRV"/{db,tiles,scripts}
cp -n "$REPO/deploy/srv/docker-compose.yml" "$SRV/docker-compose.yml"
if [[ ! -f "$SRV/.env" ]]; then
    cp "$REPO/deploy/srv/env.template" "$SRV/.env"
    chmod 640 "$SRV/.env"
    echo "  .env 를 새로 두었다 — **인증키를 채워야 한다**"
else
    echo "  .env 가 이미 있다. 건드리지 않는다"
fi
# 컨테이너가 1000:1000 으로 도니 그 앞으로 맞춘다
chown -R "$OWNER" "$SRV"
chmod -R g+ws "$SRV/db" "$SRV/tiles" "$SRV/scripts"
echo "  db/ tiles/ scripts/ 준비됨"

# ── 2. nginx 조각 ─────────────────────────────────────────────────────
say "nginx"
cp "$REPO/deploy/nginx/GSM-subpath.conf" "$SNIPPET"
echo "  $SNIPPET 놓았다"

if grep -q "GSM-subpath.conf" "$SITE"; then
    echo "  include 가 이미 있다"
else
    cp "$SITE" "$SITE.bak-$STAMP"
    # ForGIA 조각 바로 뒤에 끼운다 — 셋이 나란히 서게 한다
    if grep -q "ForGIATest-subpath.conf" "$SITE"; then
        sed -i '/ForGIATest-subpath.conf/a\    include snippets/GSM-subpath.conf;' "$SITE"
    else
        sed -i '/ForGIA-subpath.conf/a\    include snippets/GSM-subpath.conf;' "$SITE"
    fi
    echo "  include 를 넣었다 (사본: $SITE.bak-$STAMP)"
fi

# ── 3. paleolab 첫 화면의 카드 ────────────────────────────────────────
say "paleolab 카드"
if [[ ! -f "$LANDING" ]]; then
    echo "  $LANDING 이 없다. 건너뛴다"
elif grep -q 'href="/GSM/"' "$LANDING"; then
    echo "  카드가 이미 있다"
else
    cp "$LANDING" "$LANDING.bak-$STAMP"
    # Foram Viewer 카드 바로 뒤에 끼운다 — 뷰어끼리 모아 둔다
    python3 - "$LANDING" <<'PY'
import re, sys
path = sys.argv[1]
html = open(path, encoding="utf-8").read()
card = '''
  <a class="card" href="/GSM/">
    <div class="card-icon">\U0001faa8</div>
    <div class="card-title">GSM</div>
    <div class="card-desc">KIGAM geological theme maps &mdash; stack layers, click for attributes, overlay your own coordinates. 대돌여지도.</div>
    <div class="card-arrow">Open &rarr;</div>
  </a>
'''
anchor = re.search(r'<a class="card" href="/foram/">.*?</a>', html, re.S)
if anchor:
    html = html[:anchor.end()] + "\n" + card.strip("\n") + html[anchor.end():]
else:
    html = html.replace("</body>", card + "</body>", 1)
open(path, "w", encoding="utf-8").write(html)
print("  카드를 끼웠다")
PY
    chown "$OWNER" "$LANDING"
    echo "  사본: $LANDING.bak-$STAMP"
fi

# ── 4. nginx 점검과 되읽기 ────────────────────────────────────────────
say "nginx 점검"
nginx -t
systemctl reload nginx
echo "  되읽었다"

cat <<EOF

다 되었다. 다음은 sudo 없이 한다.

  1) 인증키를 채운다      $SRV/.env  의 GSM_KIGAM_KEY
  2) 띄운다               cd $SRV && GSM_TAG=v0.1.0 docker compose up -d web
  3) 살아 있는지 본다     $REPO/deploy/host/smoke.sh
  4) 열어 본다            http://paleolab/GSM/   (짧은 주소: /geomap/)

인증키가 아직 없어도 뜬다 — 타일 자리에 안내가 뜰 뿐이다.
EOF
