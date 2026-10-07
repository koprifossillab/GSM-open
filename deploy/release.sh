#!/usr/bin/env bash
# 판 하나를 붙여 운영에 내기까지 — 판 세션이 손으로 열 번 남짓 오가던 것을 명령 넷으로 (wetherilli 371).
#
#   bash deploy/release.sh prep    <판> <CHANGELOG 절 파일>   판 PR 을 연다(색인·CHANGELOG·version.py·HANDOFF)
#   bash deploy/release.sh ship    <판>                       CI 를 기다려(깨지면 한 번 다시) 병합·릴리스·이미지 받기
#   bash deploy/release.sh deploy  <판>                       컨테이너 안에 다른 일이 없으면 갈아 띄우고 healthz, 옛 이미지 정리
#   bash deploy/release.sh publish <판>                       GSM-open 에 소스, gh-pages 에 정적 판
#   bash deploy/release.sh all     <판>                       ship → deploy → publish
#
# 판 세션의 release worktree(`~/projects/GSM-wt-release`)에서 부른다 — prep·publish 가 그 트리의 브랜치를 바꾼다.
# 판은 `0.70.0` 처럼 v 없이. CHANGELOG 절 파일은 `## v<판> — <날짜> · <제목>` 로 시작하는 마크다운 한 절이다.
# 판은 하루 두세 번으로 묶는다 — 판마다 CI·이미지·배포·정적 판 굽기가 돈다.
# 출력을 `| tail` 로 받지 않는다 — 멈춘 까닭(마지막 줄)과 종료 코드가 가려진다. 중간에 멈추면 같은 명령을 다시 부른다.
set -euo pipefail

cmd="${1:-}"; ver="${2:-}"
[ -n "$cmd" ] && [ -n "$ver" ] || { sed -n '2,12p' "$0"; exit 2; }
ver="${ver#v}"; tag="v$ver"
cd "$(dirname "$0")/.."
COMPOSE="${GSM_COMPOSE:-/srv/GSM/docker-compose.yml}"
BAKED="${GSM_BAKED:-$HOME/gsm-baked}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

say() { printf '%s\n' "$*"; }
clean() { [ -z "$(git status --short)" ] || { say "트리가 깨끗하지 않다 — 멈춘다"; exit 1; }; }

# 옛 이미지를 정리한다 (.guides/web/deployment.md §5.1) — healthz 판 확인을 지난 뒤에만 부른다.
#
# 이 머신은 개발·운영을 겸하고 루트 SSD 가 늘 빠듯하다. 이미지는 판마다 쌓이고 손으로
# 치우면 잊는다 — 그래서 배포의 마지막 단계다. 저장소마다 **만든 시각으로 최근 N 개**
# (기본 3, 태그 글자순이 아니다 — v0.9 와 v0.10 은 글자순으로 거꾸로다)와 인자로 준
# 태그(지금 판·되돌리기에 쓸 앞 판), 컨테이너(멈춘 것·시험 인스턴스 포함)가 쓰는 이미지는
# 남긴다. 못 지운 것은 경고만 — 정리 실패가 배포를 실패로 만들지 않는다.
# 지울 목록만 보려면 PRUNE_DRY_RUN=1, 끄려면 PRUNE_KEEP=0.
prune_old_images() {   # $1 = 저장소, $2… = 지킬 태그
    local repo="$1" keep="${PRUNE_KEEP:-3}" protect img; shift
    [ "$keep" -gt 0 ] 2>/dev/null || { echo "  옛 이미지 정리를 건너뛴다 (PRUNE_KEEP=$keep)"; return 0; }
    protect="$(mktemp)"
    for img in "$@"; do [ -n "$img" ] && printf '%s:%s\n' "$repo" "$img" >> "$protect"; done
    docker ps -a --format '{{.Image}}' | grep "^$repo:" >> "$protect" || true
    docker images "$repo" --format '{{.CreatedAt}}\t{{.Repository}}:{{.Tag}}' \
        | grep -v '<none>' | sort -r | tail -n +"$((keep + 1))" | cut -f2 \
        | grep -vxF -f "$protect" \
        | while read -r img; do
            if [ "${PRUNE_DRY_RUN:-}" = 1 ]; then echo "  (dry-run) 지울 것: $img"
            elif docker rmi "$img" >/dev/null 2>&1; then echo "  옛 이미지를 지웠다: $img"
            else echo "  경고: $img 를 지우지 못했다 — 넘어간다" >&2; fi
        done || true   # 지울 것이 없으면 grep 이 1 — set -e·pipefail 아래서 배포를 죽이지 않게
    rm -f "$protect"
    [ "${PRUNE_DRY_RUN:-}" = 1 ] || docker image prune -f >/dev/null 2>&1 || true
    return 0
}

checks() {   # PR 의 검사 상태를 한 줄로 — 모두 SUCCESS 면 ok
  gh pr checks "$1" --json state --jq '[.[].state] | if length > 0 and all(. == "SUCCESS") then "ok" else join(",") end'
}

prep() {
  local entry="${1:-}"
  [ -f "$entry" ] || { say "CHANGELOG 절 파일이 없다: $entry"; exit 2; }
  head -1 "$entry" | grep -q "^## $tag " || { say "절의 머리가 '## $tag — …' 가 아니다"; exit 2; }
  clean
  git fetch -q origin
  git switch -q -C "release/$tag" origin/main
  python3 - "$ver" "$entry" <<'EOF'
import glob, os, re, sys
ver, entry = sys.argv[1], open(sys.argv[2], encoding="utf-8").read().rstrip("\n") + "\n\n"
# devlog 색인 — 색인에 없는 파일을 글쓴이 표의 끝에 한 줄씩
p = "devlog/README.md"; s = open(p, encoding="utf-8").read()
have = set(re.findall(r"\]\(([^)]+\.md)\)", s))
added = []
for path in sorted(glob.glob("devlog/2*_*.md")):
    f = os.path.basename(path)
    m = re.match(r"(\d{8})_([a-z0-9-]+)_(P?\d+)_", f)
    if not m or f in have:
        continue
    date, author, num = m.groups()
    rows = [l for l in s.splitlines(True) if l.startswith(f"| {author} ")]
    if not rows:
        print(f"색인에 {author} 의 표가 없다 — 손으로: {f}"); continue
    title = open(path, encoding="utf-8").readline().lstrip("# ").strip()
    row = f"| {author} {num} | {date[:4]}-{date[4:6]}-{date[6:]} | [{title}]({f}) |\n"
    s = s.replace(rows[-1], rows[-1] + row, 1); added.append(f"{author} {num}")
open(p, "w", encoding="utf-8").write(s)
print("색인에 더한 것:", ", ".join(added) or "없다")
# CHANGELOG — 맨 위 판 절 앞에
p = "CHANGELOG.md"; s = open(p, encoding="utf-8").read()
i = s.index("\n## v") + 1
open(p, "w", encoding="utf-8").write(s[:i] + entry + s[i:])
# version.py · HANDOFF
p = "web/gsmweb/version.py"; s = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write(re.sub(r'VERSION = "[^"]+"', f'VERSION = "{ver}"', s, 1))
p = "HANDOFF.md"; s = open(p, encoding="utf-8").read()
day = re.search(r"— (\d{4}-\d{2}-\d{2})", entry)
s2 = re.sub(r"(\*\*브랜치\*\* `main` = `)[^`]+`(\([^)]*\))?",
            lambda m: f"{m.group(1)}{ver}`" + (f"({day.group(1)} 배포)" if day else ""), s, 1)
if s2 == s:
    print("HANDOFF 의 '**브랜치** `main` = `…`' 줄을 못 찾았다 — 손으로")
open(p, "w", encoding="utf-8").write(s2)
EOF
  local title; title="$(head -1 "$entry" | sed 's/^## v[^ ]* — [0-9-]* · //')"
  printf '판 %s — %s\n\nCo-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>\n' "$ver" "$title" > "$TMP/msg"
  git commit -q -F "$TMP/msg" -- CHANGELOG.md web/gsmweb/version.py devlog/README.md HANDOFF.md
  git push -q -u origin "release/$tag"
  gh pr create --base main --head "release/$tag" --title "판 $ver — $title" \
    --body "$(printf 'CHANGELOG·version.py·HANDOFF·devlog 색인. `bash deploy/release.sh all %s` 로 낸다.\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)' "$ver")"
}

ship() {
  # 다시 불러도 된다 — 이미 병합했으면 병합을, 이미 릴리스가 있으면 릴리스를 건너뛴다
  local pr state
  read -r pr state < <(gh pr list --head "release/$tag" --state all --json number,state --jq '.[0] | "\(.number) \(.state)"')
  [ -n "${pr:-}" ] && [ "$pr" != null ] || { say "release/$tag 의 PR 이 없다"; exit 1; }
  if [ "$state" = OPEN ]; then
    say "#$pr 의 CI 를 기다린다"
    sleep 20; gh pr checks "$pr" --watch --interval 60 >/dev/null 2>&1 || true
    local c; c="$(checks "$pr")"
    if [ "$c" != ok ]; then
      # 휴대폰 화면 job 이 가끔 깨진다 — 한 번만 다시 돌리고, 또 깨지면 멈춘다
      local run; run="$(gh pr checks "$pr" --json link,state --jq '.[] | select(.state == "FAILURE") | .link' | grep -o 'runs/[0-9]*' | head -1 | cut -d/ -f2 || true)"
      say "깨졌다($c) — run $run 을 한 번 다시"
      gh run rerun "$run" --failed; sleep 30
      gh run watch "$run" --interval 60 >/dev/null 2>&1 || true
      c="$(checks "$pr")"; [ "$c" = ok ] || { say "다시 돌려도 깨졌다($c) — 멈춘다"; exit 1; }
    fi
    gh pr merge "$pr" --merge >/dev/null
    sleep 10
  elif [ "$state" != MERGED ]; then
    say "#$pr 가 $state 다 — 멈춘다"; exit 1
  fi
  say "#$pr 병합됨"
  if gh release view "$tag" >/dev/null 2>&1; then
    say "릴리스 $tag 는 이미 있다"
  else
    git fetch -q origin
    local sha; sha="$(gh pr view "$pr" --json mergeCommit --jq .mergeCommit.oid)"
    # 파이프 끝에서 일찍 닫으면(grep -m1) pipefail 이 SIGPIPE 를 실패로 본다 — 파일로 떠 두고 읽는다
    git show "origin/main:CHANGELOG.md" > "$TMP/changelog"
    awk -v t="## $tag " 'index($0, t) == 1 {p = 1; next} /^## v/ {p = 0} p' "$TMP/changelog" > "$TMP/notes"
    local title; title="$(grep -m1 "^## $tag " "$TMP/changelog" | sed 's/^## \(v[^ ]*\) — [0-9-]* · /\1 — /')"
    gh release create "$tag" --target "$sha" --title "$title" -F "$TMP/notes" >/dev/null
    say "릴리스 $tag"
    sleep 30
  fi
  say "태그 CI 가 이미지를 올리기를 기다린다"
  local run; run="$(gh run list --branch "$tag" --limit 1 --json databaseId --jq '.[0].databaseId')"
  gh run watch "$run" --interval 60 >/dev/null 2>&1 || true
  [ "$(gh run view "$run" --json conclusion --jq .conclusion)" = success ] || { say "태그 CI 가 깨졌다 — 멈춘다"; exit 1; }
  for _ in $(seq 1 20); do docker pull -q "koprifossillab/gsm:$tag" >/dev/null 2>&1 && { say "이미지를 받았다"; return; }; sleep 30; done
  say "이미지를 받지 못했다"; exit 1
}

deploy() {
  local id prev; id="$(docker compose -f "$COMPOSE" ps -q web)"
  prev="$(docker inspect -f '{{.Config.Image}}' "$id" 2>/dev/null | sed 's/.*://')"   # 되돌리기에 쓸 앞 판
  # 컨테이너 안에서 도는 명령(미리 데우기·받기)이 있으면 갈아 띄우지 않는다 — 세션들이 돌린 것일 수 있다
  docker top "$id" -o pid,args > "$TMP/top"
  local busy; busy="$(tail -n +2 "$TMP/top" | grep -v gunicorn || true)"
  if [ -n "$busy" ] && [ "${GSM_FORCE:-}" != 1 ]; then say "컨테이너 안에 도는 일이 있다 — 멈춘다(GSM_FORCE=1 로 무시):"; say "$busy"; exit 1; fi
  (cd "$(dirname "$COMPOSE")" && GSM_TAG="$tag" docker compose -f "$COMPOSE" up -d --force-recreate web 2>&1 | tail -1)
  for _ in $(seq 1 24); do
    sleep 10
    out="$(docker compose -f "$COMPOSE" exec -T web python -c "
import json, urllib.request
r = json.load(urllib.request.urlopen('http://127.0.0.1:9090/GSM/healthz/', timeout=10))
print(r['status'], r['version'], '|', '; '.join(n[:60] for n in r.get('notes') or []))" 2>/dev/null)" && break
  done
  say "healthz: ${out:-대답 없음}"
  case "$out" in *" $ver "*) ;; *) say "판이 $ver 가 아니다"; exit 1;; esac
  say "옛 이미지를 정리한다 (최근 ${PRUNE_KEEP:-3}개 + $tag + ${prev:-앞 판 모름})"
  prune_old_images koprifossillab/gsm "$tag" "$prev"
}

publish() {
  clean
  git fetch -q origin --tags
  git switch -q --detach "$tag"
  sh deploy/publish_open.sh "$tag" > "$TMP/open.log" 2>&1 || { tail -5 "$TMP/open.log"; exit 1; }
  tail -1 "$TMP/open.log"
  timeout 1800 sh deploy/publish_pages.sh "$BAKED" > "$TMP/pages.log" 2>&1 || { grep -v '^rm:' "$TMP/pages.log" | tail -5; exit 1; }
  grep -v '^rm:' "$TMP/pages.log" | tail -2
}

case "$cmd" in
  prep) prep "${3:-}" ;;
  ship) ship ;;
  deploy) deploy ;;
  publish) publish ;;
  all) ship; deploy; publish ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
