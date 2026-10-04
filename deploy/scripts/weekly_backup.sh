#!/bin/bash
# 매주 한 번(월요일 01:40): GSM 운영 자료를 백업하고, 상류에서 모아 두는 것을 새로 받는다 (koprifossillab P01).
# paleoadmin 의 crontab 에서 돈다 — deploy/host/crontab.GSM. 도는 것은 /srv/GSM/scripts/ 의 사본이다(koprifossillab 005). 틀은 WegenersDream 의 weekly_refresh.sh 다.
#
#   /srv/GSM/scripts/weekly_backup.sh                 ①–④ 백업 → ⑤–⑦ 받기
#   /srv/GSM/scripts/weekly_backup.sh --backup-only   ①② 와 NAS 사본만
#   /srv/GSM/scripts/weekly_backup.sh --no-fetch      ①–④ (거울까지, 받지 않는다)
#
# 바뀌는 빠르기대로 넷으로 가른다 — 한 tar 에 다 넣으면 주 2.7 GB 가운데 2.6 GB 가 안 바뀐 것이다.
#   ① 주간 tar   /data/GSM/backups/GSM.<YYYYMMDD>.tar.gz — 다시 못 얻는 것. 모두 둔다
#                GSM.db(sqlite 사본) · 스위치(dev_direct_wms·public, 있으면) · kopri/ · kigam50k/ · earth/pbdb_collections.csv(있으면)
#                · docker-compose.yml · manifest-built.txt(② 의 목록, sha256)
#   ② 구운 것    /data/GSM/backups/GSM-built.<YYYYMMDD>.tar — db/ 의 나머지. **목록이 지난번과 다를 때만** 뜬다.
#                압축하지 않는다(webp·tif 가 대부분). 30 일까지 전부, 그 뒤 달마다 가장 새 것 하나
#   ③ 캐시 거울  /data/GSM/tiles/ → NAS GSM/tiles/ (지우지 않는다, 이력 없음)
#   ④ 원본 거울  NAS GSM/sources/ → /data/GSM/sources/ (지우지 않는다) — 원본이 NAS 에 하나뿐이다
# ①② 는 NAS(/nfs/temp-share/GSM/backup/)에도 둔다 — DiaRUGA·ForGIA·WegenersDream 과 같은 자리 규약.
#
# 키·비밀키·이메일(kigam_key·vworld_key·secret_key·geus_whoami·allowed_hosts)과 .env 는 **뺀다** — NAS 는 누구나
# 읽는 공유다. 키는 각 누리집에서 다시 보고, 비밀키는 컨테이너가 새로 만든다.
#
# **받기 전에 백업한다** — fetch_kopri 는 목록에서 사라진 자료를 파일에서도 뺀다. 받기는 컨테이너 안에서 부른다
# (KPDC 의 extra_hosts 가 거기 있다, wetherilli 095). 받기가 실패해도 지난 파일이 그대로다.
#   ⑤ fetch_kopri       매주 — 목록 여덟 장과 새 상세만, 수 분
#   ⑥ (뺐다) fetch_kigam50k — 사람이 가끔 부른다. 문서에 없는 KIGAM GeoServer 로 정기적으로 나가지 않는다 (사용자, 2026-10-04, wetherilli 208)
#   ⑦ fetch_pbdb        그달의 첫 월요일 — db/earth/ 가 운영에 섰을 때만 (WegenersDream 이 매주 받으므로 여기는 매달)
#
# NAS 가 안 붙었거나 실패해도 로컬 백업과 받기는 한다 — 결과의 "nas" 에 남는다. 결과는 logs/last_backup.json.
set -uo pipefail
# /data 는 누구나 들어오는 디스크다 — 백업은 paleoadmin 그룹까지만 읽게
umask 027
export LC_ALL=C

SRV=/srv/GSM
DB=$SRV/db
COMPOSE=$SRV/docker-compose.yml
HOME_DIR=/data/GSM
TILES=$HOME_DIR/tiles
SOURCES=$HOME_DIR/sources
BACKUPS=$HOME_DIR/backups
LOGS=$HOME_DIR/logs
NAS_ROOT=/nfs/temp-share
NAS=$NAS_ROOT/GSM/backup
NAS_TILES=$NAS_ROOT/GSM/tiles
NAS_SOURCES=$NAS_ROOT/GSM/sources
DAY=$(date +%Y%m%d)
MODE=${1:-all}

# 백업에 넣지 않는 것 — 비밀과 이 스크립트가 적는 결과(backup_status.json), 지금의 바람(wind/gfs — 여섯 시간마다 바뀌고
# 다음 판이 이긴다. 넣으면 ② 가 매주 새로 뜬다, koprifossillab P02)
SECRETS='^\./(kigam_key|vworld_key|secret_key|geus_whoami|allowed_hosts|backup_status\.json|hourly_status\.json|wind/gfs/.*|wind/gmgsi/.*)$'
# ① 에 드는 것. ② 의 목록에서 뺀다. pbdb.sqlite 는 CSV 로 다시 굽는다. 스위치 파일을 ② 에 두면 켜고 끌 때마다
# 1.4 GB 를 새로 뜬다
WEEKLY='^\./(GSM\.db.*|dev_direct_wms|public|kopri/.*|kigam50k/.*|earth/pbdb_collections\.csv|earth/pbdb\.sqlite)$'

case "$MODE" in all|--backup-only|--no-fetch) ;; *) echo "모르는 선택: $MODE" >&2; exit 2 ;; esac

mkdir -p "$BACKUPS" "$LOGS"
chmod 750 "$BACKUPS" "$LOGS"
exec 9>"$LOGS/.weekly_backup.lock"
flock -n 9 || { echo "$(date -Is) 이미 돌고 있다 — 건너뜀"; exit 0; }

STAGE=$(mktemp -d "$HOME_DIR/.stage.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT

STEP=start
ARCHIVE=""; BUILT=same; NAS_RESULT=skip; TILES_RESULT=skip; SOURCES_RESULT=skip; FETCH=skip
# 결과는 로그 자리와 **DB 옆**(`backup_status.json`)에 둘 다 적는다 — 로그 자리는 컨테이너에 붙어 있지 않고,
# `/GSM/healthz/` 가 DB 옆의 것을 읽는다 (koprifossillab 002). 설명의 따옴표·빗금은 JSON 을 깨지 않게 바꾼다
status() {   # status <ok|fail> <설명>
    local note=${2//\\//}; note=${note//\"/\'}
    printf '{"at": "%s", "result": "%s", "step": "%s", "note": "%s", "backup": "%s", "built": "%s", "nas": "%s", "tiles": "%s", "sources": "%s", "fetch": "%s"}\n' \
        "$(date -Is)" "$1" "$STEP" "$note" "$ARCHIVE" "$BUILT" "$NAS_RESULT" "$TILES_RESULT" "$SOURCES_RESULT" "$FETCH" \
        > "$LOGS/last_backup.json"
    cp "$LOGS/last_backup.json" "$DB/backup_status.json.part" && mv "$DB/backup_status.json.part" "$DB/backup_status.json"
    echo "$(date -Is) [$1] $STEP — $2"
}
fail() { status fail "$1"; exit 1; }

nas_up() { mountpoint -q "$NAS_ROOT"; }

# nas_put <파일> — NAS 에 .part 로 옮기고 sha256 을 대조한 뒤 이름을 바꾼다. hard 마운트라 timeout 으로 감싼다
nas_put() {
    local f=$1 name want
    name=$(basename "$f")
    nas_up && timeout 30 mkdir -p "$NAS" || return 1
    want=$(sha256sum "$f" | cut -d' ' -f1)
    if timeout 1800 cp "$f" "$NAS/$name.part" \
       && [ "$(timeout 900 sha256sum "$NAS/$name.part" | cut -d' ' -f1)" = "$want" ] \
       && timeout 30 mv "$NAS/$name.part" "$NAS/$name"; then
        echo "NAS: $NAS/$name (sha256 일치)"
        return 0
    fi
    timeout 30 rm -f "$NAS/$name.part"
    return 1
}

# prune_built <디렉토리> — ② 를 나이로 줄인다: 30 일까지 전부, 그 뒤 달마다 가장 새 것 하나.
# 개수가 아니라 나이로 — 개수는 판을 자주 올리는 달과 드문 달에 뜻이 바뀐다
prune_built() {
    local dir=$1 cutoff kept="" f d m
    cutoff=$(date -d '30 days ago' +%Y%m%d)
    for f in $(timeout 60 ls -1 "$dir" 2>/dev/null | grep -E '^GSM-built\.[0-9]{8}\.tar$' | sort -r); do
        d=${f#GSM-built.}; d=${d%.tar}
        [ "$d" -ge "$cutoff" ] && continue
        m=${d:0:6}
        if [ "$m" = "$kept" ]; then
            timeout 60 rm -f "$dir/$f" && echo "지움: $dir/$f"
        else
            kept=$m
        fi
    done
}

echo "== $(date -Is) GSM 주간 백업 ($MODE) =="

# ── 목록 — db/ 의 파일을 비밀·쓰다 만 것(.new·.part)을 빼고 ─────────────────────
STEP=manifest
(cd "$DB" && find . \( -name '*.new' -o -name '*.part' \) -prune -o -type f -print0) \
    | sort -z | grep -zvE "$SECRETS" > "$STAGE/all.z" || fail "db/ 목록을 못 만들었다"
grep -zvE "$WEEKLY" "$STAGE/all.z" > "$STAGE/built.z"
(cd "$DB" && xargs -0 -r sha256sum < "$STAGE/built.z") > "$STAGE/manifest-built.txt" \
    || fail "구운 것의 sha256 을 못 냈다"

# ── ① 주간 tar ──────────────────────────────────────────────────────────
STEP=backup
python3 - "$DB/GSM.db" "$STAGE/GSM.db" <<'EOF' || fail "GSM.db 사본을 못 떴다"
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
assert dst.execute("pragma integrity_check").fetchone()[0] == "ok", "integrity_check"
dst.close(); src.close()
EOF
cp "$COMPOSE" "$STAGE/docker-compose.yml" || fail "compose 를 못 읽었다"
extra=()
for p in dev_direct_wms public kopri kigam50k earth/pbdb_collections.csv; do [ -e "$DB/$p" ] && extra+=("$p"); done

ARCHIVE=$BACKUPS/GSM.$DAY.tar.gz
args=(-C "$STAGE" GSM.db docker-compose.yml manifest-built.txt)
[ ${#extra[@]} -gt 0 ] && args+=(-C "$DB" "${extra[@]}")
tar -czf "$ARCHIVE.part" "${args[@]}" 2>"$LOGS/tar.err" \
    || fail "tar 실패: $(tail -1 "$LOGS/tar.err")"
tar -tzf "$ARCHIVE.part" >/dev/null 2>&1 || fail "만든 백업을 읽을 수 없다"
mv "$ARCHIVE.part" "$ARCHIVE"
echo "백업: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1)) — ${extra[*]:-모아 둔 것 없음}"
if nas_put "$ARCHIVE"; then NAS_RESULT=ok; else NAS_RESULT=fail; echo "NAS: ① 을 못 옮겼다 — 로컬 백업은 있다"; fi

# ── ② 구운 것 — 목록이 지난번과 다를 때만 ─────────────────────────────────────
STEP=built
LAST=$BACKUPS/.manifest-built.last
if [ -f "$LAST" ] && cmp -s "$LAST" "$STAGE/manifest-built.txt"; then
    echo "구운 것: 지난번과 같다 — 뜨지 않는다"
else
    BUILT_TAR=$BACKUPS/GSM-built.$DAY.tar
    tar -cf "$BUILT_TAR.part" -C "$DB" --null -T "$STAGE/built.z" 2>"$LOGS/tar.err" \
        || fail "구운 것 tar 실패: $(tail -1 "$LOGS/tar.err")"
    tar -tf "$BUILT_TAR.part" >/dev/null 2>&1 || fail "만든 구운 것 tar 를 읽을 수 없다"
    mv "$BUILT_TAR.part" "$BUILT_TAR"
    cp "$STAGE/manifest-built.txt" "$LAST"
    BUILT=$BUILT_TAR
    echo "구운 것: $BUILT_TAR ($(du -h "$BUILT_TAR" | cut -f1), 파일 $(wc -l < "$STAGE/manifest-built.txt"))"
fi
# NAS 에 가장 새 ② 가 없으면(방금 뜬 것이든, 지난번에 못 옮긴 것이든) 옮긴다
NEWEST=$(ls -1 "$BACKUPS" | grep -E '^GSM-built\.[0-9]{8}\.tar$' | sort | tail -1)
if [ -n "$NEWEST" ] && nas_up && ! timeout 30 test -f "$NAS/$NEWEST"; then
    nas_put "$BACKUPS/$NEWEST" || { NAS_RESULT=fail; echo "NAS: ② 를 못 옮겼다 — 로컬에는 있다"; }
fi
prune_built "$BACKUPS"
nas_up && prune_built "$NAS"

[ "$MODE" = "--backup-only" ] && { status ok "①② 만"; exit 0; }

# ── ③ 캐시 거울 — 로컬 → NAS ─────────────────────────────────────────────
STEP=tiles
if nas_up && timeout 30 mkdir -p "$NAS_TILES"; then
    if timeout 3600 rsync -rt "$TILES/" "$NAS_TILES/"; then TILES_RESULT=ok; else TILES_RESULT=fail; fi
else
    TILES_RESULT=fail
fi
echo "캐시 거울: $TILES_RESULT"

# ── ④ 원본 거울 — NAS → 로컬 ─────────────────────────────────────────────
STEP=sources
if nas_up && timeout 30 test -d "$NAS_SOURCES"; then
    mkdir -p "$SOURCES"
    if timeout 3600 rsync -rt "$NAS_SOURCES/" "$SOURCES/"; then SOURCES_RESULT=ok; else SOURCES_RESULT=fail; fi
else
    SOURCES_RESULT=fail
fi
echo "원본 거울: $SOURCES_RESULT ($(du -sh "$SOURCES" 2>/dev/null | cut -f1))"

[ "$MODE" = "--no-fetch" ] && { status ok "①–④"; exit 0; }

# ── ⑤–⑦ 받기 — 컨테이너 안에서 ────────────────────────────────────────────
STEP=fetch
# timeout 이 부를 수 있게 함수가 아니라 배열로 둔다
MANAGE=(docker compose -f "$COMPOSE" exec -T -w /app/web web python manage.py)
FIRST_MONDAY=$([ "$((10#$(date +%d)))" -le 7 ] && echo 1 || echo 0)
done_=(); failed=()
run() {   # run <명령> <timeout> — 컨테이너 안의 manage.py <명령>
    echo "-- $1"
    if timeout "$2" "${MANAGE[@]}" "$1"; then done_+=("$1"); else failed+=("$1"); fi
}

run fetch_kopri 10800
if [ "$FIRST_MONDAY" = 1 ]; then
    if [ -d "$DB/earth" ]; then
        run fetch_pbdb 3600
    fi
fi
FETCH="${done_[*]:-}${failed[*]:+ / 실패: ${failed[*]}}"

[ ${#failed[@]} -eq 0 ] || fail "받기 실패(${failed[*]}) — 지난 파일 그대로. 백업은 떴다"
[ "$NAS_RESULT" = ok ] && [ "$TILES_RESULT" = ok ] && [ "$SOURCES_RESULT" = ok ] \
    && status ok "다 했다" \
    || status ok "로컬 백업·받기는 했다 — NAS 쪽을 본다"
