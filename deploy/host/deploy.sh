#!/bin/bash
# 저장소에서 굽고 /srv/GSM 에 올린다. 호스트(굽는 장비)에서 돌린다.
#
#   deploy/host/deploy.sh v0.1.0
#
# 운영 장비에 저장소를 두지 않는 갈래라(ForGIA 와 같다), 굽기는 여기서 하고
# 돌리기는 /srv/GSM/docker-compose.yml 이 한다.
set -euo pipefail

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
    echo "판 번호를 준다: deploy/host/deploy.sh v0.1.0" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

echo "== 시험 =="
( cd web && python manage.py test viewer )

echo "== 굽기 $TAG =="
GSM_TAG="$TAG" docker compose -f deploy/docker-compose.yml build web

echo "== 밀어 올리기 =="
GSM_TAG="$TAG" docker compose -f deploy/docker-compose.yml push web

echo
echo "굽고 올렸다: koprifossillab/gsm:$TAG"
echo "운영 장비에서:"
echo "    cd /srv/GSM && GSM_TAG=$TAG docker compose pull && GSM_TAG=$TAG docker compose up -d web"
echo "    deploy/host/smoke.sh"
