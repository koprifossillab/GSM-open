#!/bin/bash
# 소개 화면(`/GSM/`)의 그림을 다시 찍는다 (wetherilli 113). 화면이 크게 바뀌면 돌린다.
#
#   deploy/host/intro_shots.sh [뿌리 주소] [장면 이름…]     기본 http://localhost/GSM/
#
# 한국어·영어 두 벌을 찍어 web/viewer/static/viewer/intro/{ko,en}/<장면>.webp 로 굽는다.
# 지도 주소는 `<뿌리>map/` 이고, 옛 판(지도가 뿌리에 있던 0.26 까지)이면 뿌리를 그대로 쓴다.
#
# playwright-core(npm)와 그 chromium 이 있어야 한다 — PW_CORE·PW_CHROME 으로 알려 준다.
#   PW_CORE=~/tools/pw/node_modules/playwright-core
#   PW_CHROME=~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ROOT="${1:-http://localhost/GSM/}"
ROOT="${ROOT%/}/"
shift || true
DEST="$REPO/web/viewer/static/viewer/intro"
PY="${PY:-$HOME/venv/GSM/bin/python}"
export PW_CORE="${PW_CORE:-$HOME/tools/pw/node_modules/playwright-core}"
export PW_CHROME="${PW_CHROME:-}"

MAP="${ROOT}map/"
if [[ "$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$MAP")" != "200" ]]; then
    MAP="$ROOT"
fi
echo "== 지도 $MAP · 뿌리 $ROOT =="

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for lang in ko en; do
    mkdir -p "$TMP/$lang" "$DEST/$lang"
    node "$HERE/intro_shots.js" "$MAP" "$ROOT" "$lang" "$TMP/$lang" "$@"
done

# webp 로 굽는다. 화면 그림은 1600 폭 그대로, 내려받은 PNG 는 제 크기
"$PY" - "$TMP" "$DEST" <<'EOF'
import sys
from pathlib import Path
from PIL import Image
src, dest = Path(sys.argv[1]), Path(sys.argv[2])
for png in sorted(src.glob("*/*.png")):
    out = dest / png.parent.name / (png.stem + ".webp")
    img = Image.open(png).convert("RGB")
    img.save(out, "WEBP", quality=78, method=6)
    print(f"  {out.relative_to(dest)}  {out.stat().st_size // 1024} KB")
    # 작은 판 — 첫 장면에 수십 장이 쏟아질 때와 갈래 단추에 쓴다 (wetherilli 115)
    thumb = dest / png.parent.name / "thumb" / (png.stem + ".webp")
    thumb.parent.mkdir(parents=True, exist_ok=True)
    img.resize((480, round(480 * img.height / img.width))).save(thumb, "WEBP", quality=70, method=6)
EOF
