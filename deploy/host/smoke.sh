#!/bin/bash
# 올린 뒤 살아 있는지 본다. 돌아가는 장비에서 돌린다.
#
#   deploy/host/smoke.sh [주소]      기본 http://127.0.0.1:8094/GSM/
#
# 상류를 타는 것(타일·속성)은 인증키가 있어야 하므로, 키가 없으면 그 둘은
# 건너뛰고 화면과 카탈로그만 본다.
set -uo pipefail

BASE="${1:-http://127.0.0.1:8094/GSM/}"
BASE="${BASE%/}"
fail=0

check() {
    local name="$1" url="$2" want="$3"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$url")
    if [[ "$code" == "$want" ]]; then
        printf '  %-22s %s\n' "$name" "$code"
    else
        printf '  %-22s %s  (바란 것 %s)\n' "$name" "$code" "$want" >&2
        fail=1
    fi
}

echo "== $BASE =="
check "소개"      "$BASE/"          200
check "지도"      "$BASE/map/"      200
check "카탈로그"  "$BASE/catalog/"  200
check "점묶음"    "$BASE/pointsets/" 200
check "좌표"      "$BASE/coords/parse/?q=37.5,127.0" 200

# /healthz/ — unhealthy(503)면 멈춘다. degraded(백업이 멈췄거나 낡았다)는 **알리기만 한다** — 백업 때문에 화면을
# 올리는 일을 막지 않는다. 걸리는 것은 그대로 적어 사람이 본다 (koprifossillab 002)
echo "== /healthz/ =="
health=$(curl -s -m 20 "$BASE/healthz/")
echo "$health" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("  상태", d["status"], "· 판", d.get("version"), "· DB", d.get("db"))
b = d.get("backup") or {}
if b:
    print("  백업", b.get("result"), b.get("at"), "(%s 일 전)" % b.get("age_days"))
h = d.get("hourly") or {}
if h.get("jobs"):
    print("  매시", " · ".join("%s %s" % (k, v.get("result")) for k, v in sorted(h["jobs"].items())),
          "(%s 시간 전)" % h.get("age_hours"))
for k, v in sorted((h.get("fresh") or {}).items()):
    print("  받은 것", k, v.get("t"), "(%s 시간 전)" % v.get("age_hours"))
for n in d.get("notes", []):
    print("  !", n)
sys.exit(1 if d["status"] == "unhealthy" else 0)
' || { echo "  /healthz/ 가 unhealthy 이거나 읽지 못했다" >&2; fail=1; }

echo "== 카탈로그에 든 레이어 =="
curl -s -m 20 "$BASE/catalog/" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  레이어군", len(d["groups"]), "· 레이어", sum(len(g["layers"]) for g in d["groups"]))' \
  || { echo "  카탈로그를 읽지 못했다" >&2; fail=1; }

if [[ $fail -eq 0 ]]; then
    echo "== 다 돈다 =="
else
    echo "== 멈춘 것이 있다 ==" >&2
fi
exit $fail
