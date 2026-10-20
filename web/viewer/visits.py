"""화면을 연 것을 센다 — 관리 화면의 "접속 기록" 탭 (wetherilli 399).

날짜·화면·접속 주소마다 한 줄(`VisitDay`)에 횟수와 마지막으로 연 때를 더한다. 요청마다 줄을 쌓지 않는 것은
타일이 아니라 화면만 세도 하루 수백 번이라서다 — 누가 언제 어느 화면을 열었는지는 날의 단위로 충분하다.

- **화면만 센다** (`SCREENS`). 타일·범례·속성은 화면이 열린 뒤 따라오는 것이라 세면 수가 부풀 뿐이다
- **접속 주소는 staff 만 본다** — 관리 화면의 데이터소스 탭과 같은 로그인이다. 밖에 연 판(`GSM_PUBLIC`)은 세지도 않는다
- **1 년을 둔다** (사람, 2026-10-20). 지난 줄은 하루에 한 번, 그날 처음 셀 때 지운다

세는 일이 실패해도 **화면은 뜬다** — 세는 것은 덤이다 (`usage.py` 와 같다).
"""
import datetime
import logging

from django.conf import settings
from django.db.models import Count, F, Max, Sum
from django.utils import timezone

from . import i18n
from .i18n import msg

log = logging.getLogger(__name__)

KEEP_DAYS = 365

#: 세는 화면 — url 이름 → 탭에 적는 이름. 차례가 표의 칸 차례다
SCREENS = {
    "map": msg("지역 지도"),
    "earth": msg("온 지구"),
    "moon": msg("달"),
    "mars": msg("화성"),
    "mercury": msg("수성"),
    "map3d": msg("3D"),
    "intro": msg("소개"),
    "manage": msg("관리"),
    "offline": msg("오프라인"),
}

_pruned_on = None


def client_of(request) -> str:
    """접속 주소. nginx 가 붙여 주는 X-Real-IP 가 먼저다 (deploy/nginx) — `views._client` 와 같다"""
    return (request.META.get("HTTP_X_REAL_IP")
            or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", ""))[:64]


def record(screen: str, client: str) -> None:
    from .models import VisitDay
    try:
        now = timezone.now()
        day = timezone.localdate()
        row, _ = VisitDay.objects.get_or_create(day=day, screen=screen, client=client, defaults={"last_at": now})
        VisitDay.objects.filter(pk=row.pk).update(count=F("count") + 1, last_at=now)
        _prune(day)
    except Exception as exc:                      # 세는 것은 덤이다
        log.debug("화면 연 것을 세지 못했다: %s", exc)


def _prune(day) -> None:
    global _pruned_on
    if _pruned_on == day:
        return
    from .models import VisitDay
    VisitDay.objects.filter(day__lt=day - datetime.timedelta(days=KEEP_DAYS)).delete()
    _pruned_on = day


class VisitMiddleware:
    """화면(`SCREENS`)의 GET 이 200 으로 나갈 때 한 번 센다. 304(브라우저가 들고 있던 것)는 세지 않는다"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == "GET" and response.status_code == 200 and not settings.PUBLIC:
            match = getattr(request, "resolver_match", None)
            name = match.url_name if match else None
            if name in SCREENS:
                record(name, client_of(request))
        return response


def summary(lang: str = "ko", days: int = 30, with_clients: bool = False) -> dict:
    """탭에 그릴 것 — 날마다 화면별 횟수와 접속 주소 수, staff 면 접속 주소별 횟수·화면·마지막으로 연 때"""
    from .models import VisitDay
    since = timezone.localdate() - datetime.timedelta(days=days - 1)
    rows = VisitDay.objects.filter(day__gte=since)
    screens = list(SCREENS)
    by_day = {}
    for r in rows.values("day", "screen").annotate(n=Sum("count")):
        by_day.setdefault(r["day"], {})[r["screen"]] = r["n"]
    people = {r["day"]: r["n"] for r in rows.values("day").annotate(n=Count("client", distinct=True))}
    out = {
        "days": days,
        "screens": [i18n.t(SCREENS[s], lang) for s in screens],
        "rows": [{"day": d.isoformat(), "total": sum(v.values()), "clients": people.get(d, 0),
                  "cells": [v.get(s, 0) for s in screens]}
                 for d, v in sorted(by_day.items(), reverse=True)],
        "total": rows.aggregate(n=Sum("count"))["n"] or 0,
        "clients_total": rows.values("client").distinct().count(),
    }
    if with_clients:
        seen = {}
        for r in rows.values("client", "screen").annotate(n=Sum("count"), last=Max("last_at")):
            c = seen.setdefault(r["client"], {"client": r["client"], "count": 0, "screens": {}, "last": r["last"]})
            c["count"] += r["n"]
            c["screens"][r["screen"]] = c["screens"].get(r["screen"], 0) + r["n"]
            c["last"] = max(c["last"], r["last"])
        out["clients"] = [
            {"client": c["client"], "count": c["count"],
             "screens": [(i18n.t(SCREENS[s], lang), c["screens"][s]) for s in screens if s in c["screens"]],
             "last": timezone.localtime(c["last"]).strftime("%Y-%m-%d %H:%M")}
            for c in sorted(seen.values(), key=lambda c: (-c["count"], c["client"]))]
    return out
