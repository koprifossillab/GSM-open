#!/bin/sh
# 판 하나의 소스를 공개용 저장소(koprifossillab/GSM-open)에 민다 — AGPL 13조의 소스 길 (wetherilli 149).
#
#   sh deploy/publish_open.sh v0.40.0
#
# 판 세션이 GitHub 릴리스를 만든 뒤에 부른다(CLAUDE.md "커밋과 PR"). 개발 저장소의 역사는 옮기지 않는다 —
# 판마다 그 태그의 파일을 통째로 한 커밋으로 덮고 같은 태그를 단다. 그래서 GSM-open 의 커밋 하나가 곧 판 하나다.
#
# 빼는 것: `.claude/`(세션 설정)와 `.github/`(CI — 공개 사본은 소스를 두는 곳이라 시험·이미지 굽기를 돌리지 않는다.
# 그대로 두면 사본에서 시험이 돌고, 태그마다 Docker Hub 비밀값 없이 굽기가 깨진다). 나머지는 그 판의 소스 그대로다 — 운영 이미지(`koprifossillab/gsm:<태그>`)가
# 그 태그에서 구워지므로, 밖에서 쓰는 사람이 받는 소스와 도는 코드가 같다.
#
# 미는 계정은 GSM-open 에 쓰기 권한이 있어야 한다(지금 gh 로 로그인한 계정). 자료 파일(<DB 옆>/…)은 원래 저장소에
# 없으니 따라가지 않는다.
set -eu

TAG="${1:?쓰는 법: sh deploy/publish_open.sh <태그 — 예: v0.40.0>}"
OPEN="${GSM_OPEN_REPO:-https://github.com/koprifossillab/GSM-open.git}"
cd "$(dirname "$0")/.."

git rev-parse -q --verify "refs/tags/$TAG" >/dev/null || git fetch -q origin "refs/tags/$TAG:refs/tags/$TAG"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone -q "$OPEN" "$WORK/open" 2>/dev/null || { echo "GSM-open 을 받지 못했다: $OPEN"; exit 1; }
if git -C "$WORK/open" rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "GSM-open 에 이미 $TAG 가 있다 — 건너뛴다"
  exit 0
fi

# 판의 파일로 통째로 덮는다(.git 만 남기고 지운 뒤 풀기) — 지운 파일도 사본에서 지워진다
find "$WORK/open" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git archive "$TAG" | tar -x -C "$WORK/open"
rm -rf "$WORK/open/.claude" "$WORK/open/.github"

cd "$WORK/open"
git add -A
git -c user.name="$(git -C "$OLDPWD" config user.name || echo GSM)" \
    -c user.email="$(git -C "$OLDPWD" config user.email || echo gsm@localhost)" \
    commit -q -m "$TAG 의 소스

개발 저장소(koprifossillab/GSM)의 $TAG 태그를 그대로 옮겼다 — deploy/publish_open.sh" || {
  echo "바뀐 것이 없다 — 태그만 단다"
}
git tag "$TAG"
git push -q origin HEAD:main "refs/tags/$TAG"
echo "GSM-open 에 $TAG 를 밀었다"
