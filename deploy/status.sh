#!/usr/bin/env bash
# 판 세션의 순찰을 한 번에 — 열린 PR·CI, 판에 아직 안 든 병합, 운영의 판을 짧게 (wetherilli 371).
#
#   bash deploy/status.sh            지금의 모습
#   bash deploy/status.sh <찾을 말>  그 말이 든 PR(열린 것·병합한 것)을 찾는다 — 일을 맡기기 전에, 끝난 일을 또 맡기지 않게
#
# 순찰마다 gh·docker 를 여러 번 부르고 긴 출력을 대화에 쌓던 것을 스무 줄 남짓으로 줄인다.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="${GSM_COMPOSE:-/srv/GSM/docker-compose.yml}"

if [ -n "${1:-}" ]; then
  gh pr list --state all --search "$1 in:title" --limit 15 \
    --json number,state,title,headRefName --jq '.[] | "#\(.number) \(.state) \(.title)  [\(.headRefName)]"'
  exit 0
fi

git fetch -q origin --tags
last="$(git describe --tags --abbrev=0 origin/main 2>/dev/null || echo '')"
say_prod() {
  docker compose -f "$COMPOSE" exec -T web python -c "
import json, urllib.request
r = json.load(urllib.request.urlopen('http://127.0.0.1:9090/GSM/healthz/', timeout=10))
print(r['version'], r['status'])" 2>/dev/null || echo "모름"
}
echo "운영 $(say_prod) · main $(git show origin/main:web/gsmweb/version.py | sed -n 's/^VERSION = "\(.*\)"/\1/p') · 마지막 태그 ${last:-없음}"

echo "── 열린 PR"
gh pr list --state open --json number,title,headRefName,statusCheckRollup --jq '.[] |
  ([.statusCheckRollup[]? | (.conclusion // .status)] | if length == 0 then "—"
     elif all(. == "SUCCESS") then "ok" elif any(. == "FAILURE") then "깨짐" else "도는 중" end) as $ci |
  "#\(.number) [\($ci)] \(.title)"'

if [ -n "$last" ]; then
  n="$(git log --oneline --merges --first-parent "$last..origin/main" | grep -c 'Merge pull request' || true)"
  echo "── $last 뒤 병합 $n 개 (판은 하루 두세 번 — 서넛 모이면 낸다)"
  git log --format='%s%n%b' --merges --first-parent "$last..origin/main" | grep -v '^Merge pull request' | grep -v '^$' | head -10 | sed 's/^/  /'
fi
