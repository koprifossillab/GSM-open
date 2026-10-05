"""화면 하나, 프록시 둘, 점묶음 넷.

프록시가 있는 까닭은 인증키다 — 브라우저는 키를 모른 채 `/wms/` 를 부르고,
여기서 키를 붙여 상류로 넘긴다. CLAUDE.md 의 "인증키" 를 볼 것.
"""
import csv
import datetime
import functools
import hashlib
import io
import json
import logging
import math
import re
import sqlite3
import threading
import time
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.cache import patch_vary_headers
from django.shortcuts import get_object_or_404, render
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import require_GET, require_POST

from gsmweb.version import VERSION

from . import (coords, crs, datastatus, geo3al, geomap, geus, grportal, gsj, gsmma, i18n, ibcso, janmayen, kigam, kopri, npolar,
               patchnotes, elevation, moonmap, peninsula, phyloserver, pointsets, tilecache, tiles, trek, vworld, warp,
               marscraters, marsmap, mercurymap, zhurong)
from . import admap, arcpoints, caribmap, crust, glaciers, impacts, faults, minerals, stress, tectonics, seafloor, glim, heatflow, fossils, gvp, icemargins, kigam50k, macrostrat, mantle, metatile, naturalearth, neotoma, paleo, paleoeco, paleocoast, pbdb, quakes, recentquakes, verifylog, spamap, ocean, usgs, volcanoes, wind
from . import ags, austates, bas, basemaps, bcgs, bgr, bgs, brgm, calgs, cgs, dinamige, dmr, dov, egdi, emodnet, esdm, ga, georep, geosphere, gns, gsi, gsiindia, gtk, igme, iige, ineter, ingemmet, ispra, jmg, linked, lneg, mgb, mrdata, mris, natt, ngu, nrcan, nsgs, ogs, pig, segemar, sgb, sgc, sgm, sgs, sgu, sigeom, skgs, spw, stri, swisstopo, tno, twopen, usage, usgscarib, usstates, vmme, ygs
from . import earthpoints, pointvalues, profileband, static_tables, tilegrid
from .i18n import msg
from .models import Layer, LayerGroup, Point, PointSet, PointSetDeletion, Shape

log = logging.getLogger(__name__)

#: 레이어 하나가 팝업에 내놓는 속성 덩이의 최대 수. 겹친 폴리곤을 추린
#: 뒤에도 여럿 남을 수 있어 둔다 — 팝업이 길어지면 읽히지 않는다.
MAX_FEATURES = 3

#: 찍어 둔 점을 한 번에 목록으로 저장할 수 있는 수. 손으로 찍는 것이라
#: 이보다 많을 일이 드물고, 한계가 없으면 한 번의 요청이 얼마든 커진다.
MAX_SAVED_POINTS = 2000
#: 찍고 잰 것에서 한 번에 저장하는 모양(잡은 범위·잰 선) 수
MAX_SAVED_SHAPES = 200

_ANCHOR = re.compile(r"""<a\s[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")

#: 팝업에 올리지 않는 곁가지. 상류의 지질도는 레이어 하나가 아니라 **묶음**이라,
#: 하나를 물으면 밑에 깔린 것까지 함께 온다. 행정경계가 그렇다 —
#: `ufid`·`bjcd`·`divi`·`scls` 같은 코드뿐이고 읽을 수 있는 것은 `name` 하나인데,
#: 그 이름은 배경지도에 이미 글자로 적혀 있다. 지질을 물었는데 먼저 보이면
#: 방해가 된다. 도곽(`…_frame…`)은 **버리지 않는다** — 도폭명·제작연도·조사자가
#: 들어 있어 5만 지질도를 볼 때 쓸모가 있다.
NOISE_PREFIXES = ("admin_boundary",)


#: 5만 지질도 묶음이 같이 주는 자세 기호(층리·엽리·편리·절리). 받아 둔 자료가 있으면
#: 화면이 같은 점을 제 칸으로 올린다(경사 방향·주향으로 풀어 적은 것, jikhanjung 004) —
#: 그때는 상류의 날것(`심볼회전각` …)을 빼 같은 층리가 두 번 뜨지 않게 한다.
ATTITUDE_PREFIXES = tuple(f"l_50k_geology_{k}_latest" for k in kigam50k.KINDS)


def _is_noise(feature_id: str) -> bool:
    fid = str(feature_id).lower()
    if fid.startswith(NOISE_PREFIXES):
        return True
    return fid.startswith(ATTITUDE_PREFIXES) and kigam50k.available()


def _split_links(value):
    """속성값에 섞여 온 `<a>` 를 글자와 링크로 가른다.

    **5만 지질도의 `도폭` 이 그렇게 온다** — `유성[1977]` 뒤에 원도 PDF 와
    수치지질도 DOI 가 앵커로 붙어 있다. 쓸모 있는 링크라 버리기 아깝다.

    그대로 두면 팝업에 태그가 글자로 보이고, 브라우저에서 `innerHTML` 로
    넣으면 **상류가 준 HTML 을 그대로 믿는 것**이 된다. 그래서 여기서 갈라
    보낸다 — 글자는 글자대로, 링크는 주소와 이름표로. 주소는 http·https 만
    받는다(`javascript:` 를 막는다).

    앵커가 없으면 값을 그대로 돌려준다 — 대부분이 그 경우다.
    """
    if not isinstance(value, str) or "<a" not in value.lower():
        return value

    links = []

    def take(match):
        url = match.group(1).strip()
        label = _TAG.sub("", match.group(2)).strip()
        if not url.lower().startswith(("http://", "https://")):
            # 받지 않은 주소다. **글자는 남긴다** — 이름표가 뜻을 담고 있는데
            # 주소가 못 미덥다고 글자까지 지우면 사람이 읽을 것이 사라진다.
            return label
        links.append({"label": (label or "열기")[:40], "url": url})
        return ""              # 링크로 옮겼으니 글자에서는 뺀다

    text = _TAG.sub("", _ANCHOR.sub(take, value)).strip()
    if not links:
        return text or value
    return {"text": text, "links": links}


# ── 화면 ──────────────────────────────────────────────────────────────

#: 주소 끝에 붙여 캐시를 끊는 파일들.
STAMPED = ("viewer/map.css", "viewer/map.js", "viewer/emblem.svg", "viewer/map3d.js", "viewer/moon.js",
           "viewer/mars.js", "viewer/intro.css", "viewer/intro.js", "viewer/personal.js", "viewer/manage.js",
           "viewer/manage.css")


@functools.lru_cache(maxsize=1)
def asset_stamp():
    """CSS·JS 의 내용으로 만든 짧은 표. `?v=` 로 주소 끝에 붙인다.

    **nginx 가 정적 파일을 7 일간 `immutable` 로 내보낸다.** 파일 이름이
    그대로면 브라우저는 새로 배포한 것을 받지 않고 들고 있던 것을 쓴다 —
    v0.2.1 을 배포하고도 화면에 옛 판이 뜬 까닭이다. 판 번호가 아니라
    내용으로 만드는 것은, 같은 판을 다시 구워도 내용이 바뀌면 표가 바뀌게
    하려는 것이다. 프로세스가 뜰 때 한 번 센다.
    """
    digest = hashlib.sha256(VERSION.encode())
    for name in STAMPED:
        path = finders.find(name)
        if path:
            with open(path, "rb") as fh:
                digest.update(fh.read())
    return digest.hexdigest()[:10]


def _script_json(data) -> str:
    """`<script type="application/json">` 에 넣을 JSON. 점묶음 이름은 사람이 적은
    것이라 `</script>` 가 들어 있으면 문서가 끊긴다 — `<`·`>`·`&` 를 `\\u` 로 적는다."""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


#: 주간 백업이 이만큼 지나도록 새 기록이 없으면 degraded 다 — 매주 한 번에 하루를 얹었다 (koprifossillab 002)
BACKUP_MAX_AGE_DAYS = 8
#: 매시 받기 (koprifossillab 013) — 기록이 이만큼 멈추면 cron 이 서 있다고 본다
HOURLY_MAX_AGE_HOURS = 2
#: 받아 둔 것이 이만큼 낡으면 상류가 멈췄거나 받기가 따라가지 못한다고 본다 — 유효 시각이 아니라 받은 판·장의 시각으로 잰다.
#: GFS 는 판이 여섯 시간마다 서고 네 시간 남짓 늦으니 열두 시간, GMGSI 는 한 시간마다 서고 30 분 남짓 늦으니 세 시간
FRESH_HOURS = {"gfs": 12, "gmgsi": 3}


def _backup_notes() -> tuple:
    """주간 백업의 결과 파일을 읽어 (그 내용, 걸리는 것들) 을 낸다. 읽기만 한다."""
    path = Path(settings.BACKUP_STATUS_FILE)
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, ["백업 기록이 없다 — weekly_backup.sh 가 아직 돌지 않았다"]
    except (OSError, ValueError) as e:
        return None, [f"백업 기록을 읽지 못했다: {e}"]
    notes = []
    if status.get("result") != "ok":
        notes.append(f"백업이 {status.get('step', '?')} 에서 멈췄다: {status.get('note', '')}")
    try:
        at = datetime.datetime.fromisoformat(status["at"])
        age = (datetime.datetime.now(datetime.timezone.utc) - at).total_seconds() / 86400
        status["age_days"] = round(age, 1)
        if age > BACKUP_MAX_AGE_DAYS:
            notes.append(f"마지막 백업이 {age:.0f} 일 전이다")
    except (KeyError, TypeError, ValueError):
        notes.append("백업 기록에 시각이 없다")
    failed = [k for k in ("nas", "tiles", "sources") if status.get(k) == "fail"]
    if failed:
        notes.append(f"NAS 쪽이 실패했다: {', '.join(failed)}")
    return status, notes


def _age_hours(stamp: str) -> float:
    """`YYYYMMDDHH`(UTC)가 지금보다 몇 시간 앞인가."""
    then = datetime.datetime.strptime(stamp, "%Y%m%d%H").replace(tzinfo=datetime.timezone.utc)
    return (datetime.datetime.now(datetime.timezone.utc) - then).total_seconds() / 3600


def _hourly_notes() -> tuple:
    """매시 받기의 기록과 받아 둔 것의 나이를 읽어 (그 내용, 걸리는 것들) 을 낸다. 읽기만 한다."""
    notes, info = [], {}
    try:
        status = json.loads(Path(settings.HOURLY_STATUS_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        status = None
        notes.append("매시 받기의 기록이 없다 — hourly.sh 가 아직 돌지 않았다")
    except (OSError, ValueError) as e:
        status = None
        notes.append(f"매시 받기의 기록을 읽지 못했다: {e}")
    if status:
        info["at"], info["jobs"] = status.get("at"), status.get("jobs", {})
        try:
            age = (datetime.datetime.now(datetime.timezone.utc)
                   - datetime.datetime.fromisoformat(status["at"])).total_seconds() / 3600
            info["age_hours"] = round(age, 1)
            if age > HOURLY_MAX_AGE_HOURS:
                notes.append(f"매시 받기가 {age:.0f} 시간째 돌지 않았다 — cron 을 본다")
        except (KeyError, TypeError, ValueError):
            notes.append("매시 받기의 기록에 시각이 없다")
        for job, entry in sorted(info["jobs"].items()):
            if entry.get("result") != "ok":
                notes.append(f"{job} 가 실패했다: {entry.get('note', '')}")
    fresh = {}
    for source, limit in FRESH_HOURS.items():
        times = wind.read_index(source)["times"]
        if not times:
            notes.append(f"{source} 를 받은 것이 없다")
            continue
        newest = max(e.get("run", e["t"]) for e in times)
        age = _age_hours(newest)
        fresh[source] = {"t": newest, "age_hours": round(age, 1)}
        if age > limit:
            notes.append(f"{source} 의 가장 새 것이 {age:.0f} 시간 전이다 (넘지 말 것 {limit} 시간)")
    info["fresh"] = fresh
    return info, notes


@require_GET
def healthz(request):
    """판·DB·백업 상태를 한 번에 낸다 (ForGIA·DiaRUGA `/healthz` 와 같은 모양, koprifossillab 002).

    | 상태 | 코드 | 뜻 |
    |---|---|---|
    | `ok` | 200 | 정상 |
    | `degraded` | **200** | 화면은 도는데 백업이 멈췄거나 낡았다, 매시 받기가 멈췄거나 받아 둔 것이 낡았다 |
    | `unhealthy` | 503 | DB 를 못 열거나 레이어가 하나도 없다 |

    **`degraded` 를 503 으로 두지 않는다** — 백업이 멈췄다고 뷰어가 죽은 것은 아니다. 알리는 일은 `smoke.sh` 가 한다.
    **레이어가 0 이면 unhealthy 다** — DB 마운트가 어긋나 빈 DB 가 새로 생겨도 "열리는가" 는 통과하기 때문이다.
    가볍게 둔다 — `count(*)` 셋과 작은 파일 하나, 구운 자료는 `stat` 만. 상류는 타지 않는다.
    """
    info = {"status": "ok", "version": VERSION}
    notes = []
    try:
        info["db"] = {"layer": Layer.objects.count(), "layergroup": LayerGroup.objects.count(),
                      "pointset": PointSet.objects.count()}
    except Exception as e:                       # noqa: BLE001 — 무엇이 나오든 죽지 않는다
        info["status"] = "unhealthy"
        info["db"] = None
        notes.append(f"DB 를 읽지 못했다: {e}")
    else:
        if info["db"]["layer"] == 0:
            info["status"] = "unhealthy"
            notes.append("레이어가 0 이다 — DB 마운트가 어긋났거나 씨앗이 들지 않았다")

    info["backup"], backup_notes = _backup_notes()
    if backup_notes and info["status"] == "ok":
        info["status"] = "degraded"
    notes.extend(backup_notes)

    # 매시 받기 — 바람·구름·위성 구름·아라온호를 계속 잘 받아 오는가 (koprifossillab 013)
    info["hourly"], hourly_notes = _hourly_notes()
    if hourly_notes and info["status"] == "ok":
        info["status"] = "degraded"
    notes.extend(hourly_notes)

    # 구운 자료 (wetherilli 312) — 있어야 하는데 없는 파일의 수만. 상태는 바꾸지 않는다 — 없는 레이어는 그 자리에 안내가 뜰 뿐 뷰어는 돈다.
    # 무엇이 없는지는 `manage.py data_status` 와 관리 화면이 말한다
    try:
        info["data"] = {"items": len(datastatus.ITEMS), "missing": len(datastatus.missing())}
    except OSError:
        info["data"] = None

    info["notes"] = notes
    response = JsonResponse(info, status=503 if info["status"] == "unhealthy" else 200,
                            json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def intro_view(request):
    """소개 (wetherilli 113). 뿌리(`/GSM/`)는 늘 이 화면이고 지도는 `map/` 이다.

    스크롤로 장면을 넘기며 무엇을 할 수 있는지 보인다. 그림은 운영 화면을 찍어 둔 것
    (`static/viewer/intro/<언어>/`, `deploy/host/intro_shots.sh`)이라 상류를 타지 않는다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/intro.html", {
        "lang": lang,
        "base": request.path,
        "shots": f"viewer/intro/{lang}/",
        "version": VERSION,
        # AGPL 13조의 소스 길 — 공개용 저장소(GSM-open)의 판마다 사본 (wetherilli 149)
        "source_url": settings.SOURCE_URL,
        # 정적 판(wetherilli 167) — 서버 화면으로 가는 장면·문을 빼고, 실린 지역만 화면이 남긴다
        "static_site": _script_json(settings.STATIC_SITE) if settings.STATIC_SITE else "",
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def manage_view(request):
    """관리 화면 (wetherilli P08·118). 개인 레이어 반입, 이 브라우저의 저장 자료 관리, 상류 응답 시간(읽기만, wetherilli 295),
    구운 자료의 나이(읽기만, wetherilli 312).

    **서버는 화면만 내준다.** 개인 레이어는 브라우저가 읽어 브라우저(IndexedDB)에 둔다 — 서버로 오지 않는다.
    관리라는 이름이지만 지우고 고치는 것은 그 브라우저의 것뿐이라 계정을 묻지 않는다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/manage.html", {
        "lang": lang,
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        "base": request.path.rsplit("manage", 1)[0],
        "linked_proxy": not settings.PUBLIC,
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
        # 상류 응답 시간 (wetherilli 295) — `upstream_stats` 와 같은 값. 읽기만 하고 상류의 이름과 수뿐이다(주소·키는 남기지도 않는다)
        "upstream_rows": usage.summary(7),
        # 마지막 레이어 대조의 한 줄 (wetherilli 314) — 날짜와 수뿐이다
        "verify": verifylog.summary(),
        # 구운 자료 (wetherilli 312) — `data_status` 와 같은 표. 읽기만 하고 경로는 `<DB 옆>` 아래 이름뿐이다
        "data_rows": _data_rows(lang),
    })


def _data_rows(lang):
    out = []
    for r in datastatus.rows():
        out.append({**r, "what": i18n.t(r["what"], lang),
                    "size_text": datastatus.human_size(r["size"]) if r["size"] is not None
                    else (i18n.t(msg("{n} 칸", n=r["count"]), lang) if r["count"] is not None else ""),
                    "date": f"{r['modified']:%Y-%m-%d}" if r["modified"] else ""})
    return out


@require_POST
def linked_fetch(request):
    """연결 레이어를 서버가 대신 받는다 (wetherilli P09·122). 브라우저가 곧장 못 받을 때만 온다(CORS).

    몸은 JSON — `{"url": …, "auth": {"mode": none|bearer|header|query, "name": …, "key": …}}`. 받은 것을
    풀지 않고 그대로 돌려준다(읽는 것은 브라우저의 `personal.js`). 주소·키는 적지 않는다 — 문(`linked.py`)이
    사설망·포트·크기·시간을 거른다. **밖에 연 뷰어(`GSM_PUBLIC`)에서는 닫는다** — 아무 공인 주소나 대신 받아 주는
    중계가 되기 때문이다. 그때는 상대가 CORS 를 열어 브라우저가 곧장 받아야 한다."""
    if settings.PUBLIC:
        raise Http404
    if not linked.allow(_client(request)):
        return JsonResponse({"error": i18n.t(msg("너무 자주 부른다 — 1 분 뒤에 다시"), i18n.lang_of(request))}, status=429)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": i18n.t(msg("요청을 읽지 못했다"), i18n.lang_of(request))}, status=400)
    try:
        data, content_type = linked.fetch(body.get("url"), body.get("auth") or {})
    except linked.LinkedError as exc:
        return JsonResponse({"error": i18n.t(exc.args[0], i18n.lang_of(request))}, status=exc.status)
    response = HttpResponse(data, content_type="application/octet-stream")
    response["X-GSM-Content-Type"] = content_type[:200]
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def map_view(request):
    lang = i18n.lang_of(request)
    return render(request, "viewer/map.html", {
        "lang": lang,
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        "crs_options": [(code, i18n.t(spec[0], lang)) for code, spec in crs.SYSTEMS.items()],
        "catalog": json.dumps(_static_catalog(_catalog(lang)) if settings.STATIC_SITE else _catalog(lang),
                              ensure_ascii=False),
        # 정적 판(wetherilli P11·162) — 서버가 없으니 점묶음은 비우고, 화면이 쓸 약속을 싣는다
        "pointsets": "[]" if settings.STATIC_SITE else _script_json(_pointset_list()),
        "static_site": _script_json(settings.STATIC_SITE) if settings.STATIC_SITE else "",
        # 정적 판의 극지 상류 표(wetherilli 161) — 문의 명세·이름 표를 떠서 `static-kinds.js` 가 읽는다. 서버 판에는 싣지 않는다
        "static_tables": _script_json(static_tables.tables()) if settings.STATIC_SITE else "",
        # 화면이 주소를 짓는 우리 타일(IBCSO 배경)의 판 (wetherilli 183). 정적 판은 구운 파일이라 싣지 않는다
        "tile_versions": "{}" if settings.STATIC_SITE else _script_json(tile_versions("map")),
        "has_key": kigam.has_key(),
        "dev_direct": settings.DEV_DIRECT_WMS,
        # 브라우저가 직접 VWorld 를 부른다. 까닭은 settings.VWORLD_KEY.
        "vworld_key": settings.VWORLD_KEY,
        "base": request.path.rsplit("map", 1)[0],
        "linked_proxy": not settings.PUBLIC,
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


#: 3D 가 `wms/` 의 3857 타일로 얹는 상류 (`map3d.js` 의 `wmsTiles`)
MAP3D_WMS = ("kigam", "geus", "geusarc", "vworld", "ccop", "gsjows", "gsmma",
             "emodnet", "bgs", "bgsgi", "gsni", "brgm", "egdi", "bgr", "igme", "gsi",
             # 남미 SGC(wetherilli 188)·브라질 SGB(191)·아르헨티나 SEGEMAR·우루과이 DINAMIGE(196) — 3857 로 그린다
             "sgc", "sgb", "segemar", "dinamige",
             # 에콰도르 IIGE(wetherilli 198) — ArcGIS WMS 가 3857 로 그린다
             "iige",
             # 미국 USGS mrdata(wetherilli 205) — MapServer WMS 가 3857 로 그린다
             "mrdata",
             # 멕시코 SGM(wetherilli 206) — 문이 WMS 변수를 REST export 로 옮긴다
             "sgm",
             # 아프리카 CGMW–BRGM·BGS 지하수 지도책(wetherilli 207), 남아공 CGS·나미비아 GSN(209) — 서버 캐시에 담지 않는 둘도 3D 는 그때그때 받는다
             "cgmw", "aga", "cgs", "gsn",
             # 부르키나파소 BUMIGEB(wetherilli 246) — BGS 의 MapServer, 3857. 카메룬 IRGM 은 4326 만 그려 3D 에 없다
             "bumigeb",
             # 캐나다 NRCan·온타리오 OGS(wetherilli 204) — 2D 는 3978 이지만 3D 는 3857 로 묻는다(둘 다 그려 준다)
             "nrcan", "ogs",
             # 퀘벡 SIGÉOM·유콘 YGS(wetherilli 210) — 둘 다 3857 도 그린다
             "sigeom", "ygs",
             # 사스카치원·노바스코샤(wetherilli 235) — 3857 로도 그린다
             "skgs", "nsgs",
             # 호주 GA(wetherilli 212) — ArcGIS WMS 가 3857 로 그린다. 주 판 셋(225)도 3857 이다
             "ga", "gsq", "gsv", "gssa", "mrt", "gsnsw",
             # 이탈리아 ISPRA·포르투갈 LNEG·스위스 swisstopo(wetherilli 211) — 3857 로 그린다
             "ispra", "lneg", "swisstopo",
             # 스웨덴 SGU(wetherilli 213) — 2D 는 3413 이지만 GeoServer 가 3857 도 그린다
             "sgu",
             # 노르웨이 NGU·핀란드 GTK(wetherilli 335) — 2D 는 3575·3413 이지만 3857 도 그려 준다(2026-10-05 에 둘 다 재었다)
             "ngu", "gtk",
             # 아이슬란드 NÍ(wetherilli 216) — 2D 는 3413 이지만 GeoServer 라 3857 도 그린다
             "natt",
             # 뉴질랜드·남빅토리아랜드 GNS(wetherilli 218) — GeoServer 라 3857 도 그린다
             "gns",
             # 몽골 MonGeoCat(wetherilli 221) — ArcGIS WMS 가 3857 로 그린다
             "mris",
             # 인도 GSI(wetherilli 226) — BGS 의 MapServer WMS 가 3857 로 그린다
             "gsiindia",
             # 사우디 SGS(wetherilli 227) — 원본이 3857 이다
             "sgs",
             # 동남아(wetherilli 228) — 인도네시아·필리핀·태국은 ArcGIS WMS, 말레이시아는 문이 REST export 로 옮긴다. 다 3857 로 그린다
             "esdm", "jmg", "mgb", "dmr",
             # 브리티시컬럼비아 BCGS·캘리포니아 CGS(wetherilli 231) — 2D 는 3978 이지만 3D 는 3857 로 묻는다(둘 다 그려 준다)
             "bcgs", "calgs",
             # 네바다·워싱턴·오리건(wetherilli 291) — 캘리포니아처럼 문이 REST export 로, 3D 는 3857
             "nbmg", "wadnr", "dogami", "dggs",
             # 오스트리아·폴란드·네덜란드·벨기에(wetherilli 237) — 3857 로 그린다
             "geosphere", "pig", "tno", "dov", "spw",
             # 니카라과 INETER(wetherilli 242) — GeoServer 라 3857 로 그린다
             "ineter",
             # 누벨칼레도니 Géorep(wetherilli 260) — 3857 로 다시 그려 준다
             "georep")


@require_GET
def map3d_view(request):
    """3D (devlog 015, 059 에서 실험을 벗었다). MapLibre + 공개 표고 타일 + 서버 중계 지질도."""
    lang = i18n.lang_of(request)
    # 3D 는 3857 타일만 얹는다 — 대개 `wms/` 의 WMS(`map3d.js` 의 `wmsTiles`), 일본은 z/x/y. 모양·점 레이어와, 우리가
    # 굽거나(음영판) 극지 투영으로만 받는 것(phyloserver)은 뺀다. NGU·GTK 는 3857 도 그려 `MAP3D_WMS` 에 든다(wetherilli 335). SGU 는 3857 도 그려 얹는다 — 목록에 두면 골라도 빈 화면이다
    # NPI(스발바르·드로닝모드랜드)는 `export` 가 3857 로도 그려 준다 — 극지 3D 에 얹는다(032)
    # GeoMAP(남극)은 우리가 굽는 3031 타일을 서버가 3857 로 다시 펴 준다(`warp/geomap/`, 040)
    # 대만(GSMMA)은 상류가 4326 만 받아 문이 4326 으로 받아 3857 로 편다(`gsmma.mercator_map`, wetherilli 141)
    # 유럽 상류(wetherilli 187)도 2D 처럼 `wms/` 로 3857 을 받는다. IGME 1:100만은 2D 가 4326 으로 받지만 문(1.1.1)으로 3857 을
    # 물어도 그려 준다(2026-10-04 마드리드). EMODnet 의 GeoServer 는 어느 투영이든 그린다. 일본 GSJ·지리원 주제 타일은 3857 z/x/y 라
    # 카탈로그 행의 `tiles` 를 MapLibre 가 그대로 받는다
    catalog = _catalog(lang)          # 한 번만 짓는다 — 아래 둘이 같은 것을 훑는다 (wetherilli 271)
    groups = [dict(g, layers=[l for l in g["layers"] if l.get("kind") not in ("vector", "points")
                              and (l.get("upstream") in MAP3D_WMS
                                   or (l.get("upstream") == "npolar" and npolar.knows(l["name"]))
                                   or (l.get("upstream") == "geomap" and l["name"] in geomap.LAYERS)
                                   # IBCSO 자료 출처·ADMAP 자력 이상도 GeoMAP 처럼 서버가 3857 로 편다 (wetherilli 335)
                                   or l["name"] in ("ibcso:tid", admap.NAME)
                                   or (l.get("upstream") in ("gsj", "gsitile", "ingemmet", "ags", "sim3534", "gsjows") and l.get("tiles")))])
              for g in catalog]
    # 커스텀 지질도 — 한반도 지질도 셋은 서버가 3857 로 다시 펴 주고(`warp/`), 암맥은
    # 모양 한 덩이(`points/`)라 3D 가 그대로 그린다. 밖에 열면 `_catalog` 가 이미 뺐다
    custom = [{"name": l["name"], "title": l["title"], "kind": l.get("kind"), "group": g["name"]}
              for g in catalog for l in g["layers"] if l.get("upstream") in ("peninsula", "phyloserver")]
    return render(request, "viewer/map3d.html", {
        "lang": lang,
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        "catalog_groups": [dict(g, options=_options_3d(g["layers"])) for g in groups if g["layers"]],
        "custom_layers": _script_json(custom),
        # 점묶음 요약 — 2D 와 같은 것이다. 모양은 `pointsets/<번호>/geojson/` 으로 받는다 (P02)
        "pointsets": _script_json(_pointset_list()),
        "vworld_key": settings.VWORLD_KEY,
        "base": request.path.rsplit("3d", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def moon_view(request):
    """달 (devlog 036, P05). CesiumJS 의 둥근 달에 USGS 달 통합 지질도와 LOLA 지형을 얹는다.

    지역 탭이 아니라 대돌여지도 아이콘의 숨은 차림에서 들어온다. 지질도·표고·속성·범례는
    `moon/…` 이 `trek.py` 로 받고, 영상 배경만 브라우저가 Trek 을 곧장 부른다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/moon.html", {
        "lang": lang,
        "pointsets": _script_json(_pointset_list("moon")),
        "trek_catalog": _script_json(trek.client_catalog("moon")),   # Trek 판 목록 (060)
        # 가까이서 쓰는 고운 표고 판의 범위·줌 끝 — 화면이 그 자리에서만 깊은 줌을 묻는다 (wetherilli 107)
        "dem_parts": _script_json([[*part[1], part[2]] for part in trek.DEM_PARTS]),
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        # 화면이 주소를 짓는 우리 타일의 판 — `?v=` 로 붙여 길게 캐시한다 (wetherilli 183)
        "tile_versions": _script_json(tile_versions("moon")),
        "base": request.path.rsplit("moon", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


def browser_cached(view):
    """속성·범례 JSON 도 브라우저가 하루 들고 있게 한다 (wetherilli 158). 타일과 같은 하루(`TILE_CACHE_SECONDS`)이고,
    지나면 ETag 로 되묻는다(151). 한국어판·영어판이 같은 주소에서 다른 답을 주므로 `Vary` 로 언어(쿠키·Accept-Language)를
    가린다 — 안 가리면 언어를 바꿔도 옛 언어의 팝업이 뜬다. 200 만, 뷰가 스스로 적은 것은 건드리지 않는다"""
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if response.status_code == 200 and not response.has_header("Cache-Control") and settings.TILE_CACHE_SECONDS > 0:
            response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
        patch_vary_headers(response, ("Cookie", "Accept-Language"))
        return response
    return wrapped


# ── 달 (devlog 036, P05) ───────────────────────────────────────────────
#
# 문은 `trek.py` 다. 지질도·표고·속성·범례를 캐시에 담는다(007) — 영상 배경만 브라우저가
# 곧장 부른다. 격자는 경위도(줌 0 이 가로 2 장·세로 1 장)이고 y 는 북쪽부터 센다.

def moon_tile_key(layer, z, x, y):
    return tilecache.key_text("trek", f"{layer}/{z}/{x}/{y}")


def moon_dem_key(z, x, y):
    """달 표고 격자의 캐시 열쇠 — 판(고운 판·256 ppd)이 든다. `manage.py prewarm` 도 이것으로 담는다"""
    return tilecache.key_text("trek-dem", f"{trek.dem_source(z, x, y)[0]}/{z}/{x}/{y}")


def mars_tile_key(layer, z, x, y):
    return tilecache.key_text("trek-mars", f"{layer}/{z}/{x}/{y}")


def mars_dem_key(z, x, y):
    """화성 표고 격자의 캐시 열쇠. 고운 판(wetherilli 274)의 장만 판 이름이 든다 — 줌 9 까지의 열쇠는 예전 그대로다"""
    part = trek.mars_dem_part(z, x, y)
    return tilecache.key_text("trek-mars-dem", f"{part[0]}/{z}/{x}/{y}" if part else f"{z}/{x}/{y}")


@require_GET
def moon_tile(request, layer, z, x, y):
    """달 지질도 타일 — `moon/tiles/<units|contacts|linear>/<z>/<x>/<y>.png`.

    `orig-units`·`orig-lines` 는 원도 6 장이다 — Trek 이 아니라 우리 파일을 굽는다(`moonmap`, 039)."""
    z, x, y = int(z), int(x), int(y)
    if moonmap.knows(layer):
        return _moon_original_tile(request, layer, z, x, y)
    if layer not in trek.LAYERS or not trek.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = moon_tile_key(layer, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.get_tile(layer, z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("달 지질도 타일을 받지 못했다 (%s %s/%s/%s): %s", layer, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


def _moon_original_tile(request, layer, z, x, y):
    if not moonmap.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not moonmap.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MOON), store=False)
    # 그리는 법(`RENDERER`)과 파일의 판이 열쇠에 든다 — 올리거나 다시 구우면 옛 그림을 버리고 주소도 바뀐다 (wetherilli 183)
    version = moonmap_version()
    key = tilecache.key_text("moonmap", f"{version}/{layer}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    try:
        png = moonmap.render_tile(layer, z, x, y)
    except (moonmap.MoonMapError, OSError) as exc:
        log.warning("달 원도 타일을 굽지 못했다 (%s %s/%s/%s): %s", layer, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MOON), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def moon_polar_tile(request, pole, layer, z, x, y):
    """극 평면의 달 지질도 타일 — `moon/ptiles/<n|s>/<레이어>/<z>/<x>/<y>.png` (052).

    격자는 Trek 극 WMTS 의 것(`trek.polar_tile_bbox`)이다. 통합 지질도는 Trek 의 극지 판(`…_NP`·`…_SP`)이
    그리고, 원도는 우리가 극 평사도법으로 굽는다."""
    z, x, y = int(z), int(x), int(y)
    lang = i18n.lang_of(request)
    if not trek.polar_valid(z, x, y) or not (layer in trek.LAYERS or moonmap.knows(layer)):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), lang)}, status=404)
    if moonmap.knows(layer):
        if not moonmap.available():
            return _tile(tiles.notice_tile(256, 256, tiles.NO_MOON), store=False)
        version = moonmap_version()     # 원도만 판이 있다 — Trek 에서 받은 것은 판이 없어 길게 두지 않는다 (wetherilli 183)
        key = tilecache.key_text("moonmap", f"{version}/{pole}p/{layer}/{z}/{x}/{y}")
        fetch = lambda: moonmap.render_polar_tile(layer, pole, z, x, y)     # noqa: E731
        errors = (moonmap.MoonMapError, OSError)
    else:
        version = ""
        key = tilecache.key_text("trek", f"{pole}p/{layer}/{z}/{x}/{y}")
        fetch = lambda: trek.get_polar_tile(layer, pole, z, x, y)           # noqa: E731
        errors = (trek.TrekError,)
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    try:
        png = fetch()
    except errors as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("달 극 지질도 타일을 받지 못했다 (%s %s %s/%s/%s): %s", pole, layer, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def moon_dem(request, z, x, y):
    """달 표고 격자 — `moon/dem/<z>/<x>/<y>.png`, 65×65 Terrarium (LOLA).

    못 받으면 502 다. 화면은 그 자리를 평평하게 그린다 — 안내 타일을 표고로 읽으면
    엉뚱한 산이 솟는다."""
    z, x, y = int(z), int(x), int(y)
    # 줌 `DEM_MAX_ZOOM` 너머는 고운 판(극 5 m·NAC)이 걸친 장만 있다 (wetherilli 107)
    part = trek.dem_part(z, x, y) if trek.valid_tile(z, x, y, trek.DEM_FINE_MAX) else None
    if not trek.valid_tile(z, x, y, trek.DEM_MAX_ZOOM) and part is None:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = moon_dem_key(z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.dem_tile(z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("달 표고를 받지 못했다 (%s/%s/%s): %s", z, x, y, exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request))}, status=502)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def moon_profile(request):
    """`?line=경도,위도;경도,위도…&n=256` — 잰 선을 따라 고르게 찍은 점의 LOLA 표고 (wetherilli 100).

    `{"dist": [m…], "elev": [m 또는 null…], "lon", "lat", "source", "datum"}`. 같은 선은 캐시가 낸다."""
    return _body_profile(request, "moon")


@require_GET
def mars_profile(request):
    """화성의 높이 그래프 — MOLA–HRSC 200 m (wetherilli 148). 꼴은 `moon_profile` 과 같다."""
    return _body_profile(request, "mars")


@require_GET
def mercury_profile(request):
    """수성의 높이 그래프 — MESSENGER 665 m (wetherilli 148). 꼴은 `moon_profile` 과 같다."""
    return _body_profile(request, "mercury")


def _body_profile(request, body):
    lang = i18n.lang_of(request)
    vertices = []
    for part in (request.GET.get("line") or "").split(";"):
        lon, _, lat = part.partition(",")
        lon, lat = _float(lon), _float(lat)
        if lon is None or lat is None or not (-90 <= lat <= 90 and -540 <= lon <= 540):
            vertices = []
            break
        vertices.append((lon, lat))
    if not 2 <= len(vertices) <= trek.PROFILE_MAX_VERTICES:
        return JsonResponse({"error": i18n.t(msg("선이 없다"), lang)}, status=400)
    n = int(_float(request.GET.get("n")) or 256)
    text = ";".join(f"{lon:.5f},{lat:.5f}" for lon, lat in vertices)
    source = trek._profile_body(body)[2]
    key = tilecache.key_text("trek-profile", f"{source}/{n}/{text}")
    data = _cached_json(key)
    if data is None:
        try:
            data = trek.profile(vertices, n, body)
        except trek.TrekError as exc:
            log.warning("%s 높이 그래프를 받지 못했다: %s", body, exc)
            return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang)}, status=502)
        if any(v is not None for v in data["elev"]):
            tilecache.put(key, json.dumps(data).encode("utf-8"), ".json")
    return JsonResponse(data)


@require_GET
def elevation_profile(request):
    """`?line=경도,위도;경도,위도…&n=256` — 지구의 잰 선을 따라 고르게 찍은 점의 표고 (wetherilli 109, `elevation.profile`).
    달의 것(`moon_profile`)과 같은 꼴이다. 같은 선은 캐시가 낸다."""
    lang = i18n.lang_of(request)
    vertices = []
    for part in (request.GET.get("line") or "").split(";"):
        lon, _, lat = part.partition(",")
        lon, lat = _float(lon), _float(lat)
        if lon is None or lat is None or not (-90 <= lat <= 90 and -540 <= lon <= 540):
            vertices = []
            break
        vertices.append((lon, lat))
    if not 2 <= len(vertices) <= elevation.PROFILE_MAX_VERTICES:
        return JsonResponse({"error": i18n.t(msg("선이 없다"), lang)}, status=400)
    n = int(_float(request.GET.get("n")) or 256)
    text = ";".join(f"{lon:.5f},{lat:.5f}" for lon, lat in vertices)
    key = tilecache.key_text("elev-profile", f"{n}/{text}")
    data = _cached_json(key)
    if data is None:
        try:
            data = elevation.profile(vertices, n)
        except elevation.ElevationError as exc:
            log.warning("높이 그래프를 받지 못했다: %s", exc)
            return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang)}, status=502)
        if any(v is not None for v in data["elev"]):
            tilecache.put(key, json.dumps(data).encode("utf-8"), ".json")
    return JsonResponse(data)


@require_GET
def profile_band(request):
    """`?layer=geomap_simple_geology&line=경도,위도;…&n=256` — 높이 그래프 밑의 지질 띠 (wetherilli 180, `profileband.band`).
    점은 높이 그래프와 같은 셈으로 찍는다. 우리 파일로 그리는 레이어만 받는다 — 상류에 점마다 묻지 않는다."""
    lang = i18n.lang_of(request)
    layer = request.GET.get("layer") or ""
    if not profileband.knows(layer) or _lab_only(layer):
        return JsonResponse({"error": i18n.t(msg("띠를 그리지 않는 레이어다"), lang)}, status=404)
    vertices = []
    for part in (request.GET.get("line") or "").split(";"):
        lon, _, lat = part.partition(",")
        lon, lat = _float(lon), _float(lat)
        if lon is None or lat is None or not (-90 <= lat <= 90 and -540 <= lon <= 540):
            vertices = []
            break
        vertices.append((lon, lat))
    if not 2 <= len(vertices) <= profileband.MAX_VERTICES:
        return JsonResponse({"error": i18n.t(msg("선이 없다"), lang)}, status=400)
    if not profileband.available(layer):
        return JsonResponse({"error": i18n.t(msg("지질 띠를 그릴 자료가 서버에 없다"), lang)}, status=503)
    try:
        data = profileband.band(layer, vertices, int(_float(request.GET.get("n")) or 256), lang)
    except profileband.BandError as exc:
        log.warning("지질 띠를 읽지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": i18n.t(msg("지질 띠를 읽지 못했다"), lang)}, status=500)
    return JsonResponse(data)


@require_GET
def mars_values_at(request):
    """`?lon=&lat=&key=mars_elev` — 화성의 켠 Trek 판의 값 (wetherilli 192). 꼴은 `moon_values` 와 같다. 화성은 표고뿐이다."""
    return _trek_values(request, trek.MARS_VALUES, "화성")


@require_GET
def mercury_values_at(request):
    """`?lon=&lat=&key=mercury_elev` — 수성의 켠 Trek 판의 값 (wetherilli 194). 꼴은 `moon_values` 와 같다. 수성도 표고뿐이다."""
    return _trek_values(request, trek.MERCURY_VALUES, "수성")


@require_GET
def moon_values(request):
    """`?lon=&lat=&key=feo` — 켠 Trek 판의 값을 누른 자리 한 점에서 (wetherilli 103). `{"rows": [[이름, 값], …]}`.
    이름은 한국어판·영어판에 맞춘다. 값(숫자·단위)은 옮기지 않는다."""
    return _trek_values(request, trek.VALUES, "달")


def _trek_values(request, table, body):
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    key = request.GET.get("key") or ""
    known = trek.value_spec(key) if table is trek.VALUES else table.get(key)     # 달은 판이 여럿인 갈래도 안다 (wetherilli 236)
    if not known or lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "rows": []}, status=400)
    cache = tilecache.key_text("trek-value", f"{key}/{lon:.4f},{lat:.4f}")
    data = _cached_json(cache)
    if data is None:
        try:
            data = trek.value_at(key, lon, lat)
        except trek.TrekError as exc:
            log.warning("%s 값을 읽지 못했다 (%s): %s", body, key, exc)
            return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang), "rows": []}, status=502)
        tilecache.put(cache, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    rows = [[i18n.PROP_EN.get(name, name) if lang == "en" else name, value] for name, value in data["rows"]]
    return JsonResponse({"rows": rows})


@require_GET
@browser_cached
def moon_info(request):
    """`?lon=-15&lat=20` — 누른 자리의 지질 단위. `{"rows": [[이름, 값], …]}`.

    값은 옮기지 않는다. 시대만 한국어판에서 옮긴다(`trek.AGES_KO`)."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "rows": []}, status=400)
    if request.GET.get("layer") == "orig":
        return _moon_original_info(lang, lon, lat)
    if request.GET.get("layer") == "spa":
        return _moon_spa_info(lang, lon, lat)
    # 1e-3° 는 달에서 30 m 남짓이다 — 1:500만 지도에는 한 점이다
    key = tilecache.key_text("trek-info", f"{lon:.3f},{lat:.3f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"hit": trek.identify(lon, lat)}
        except trek.TrekError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("달 속성을 읽지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    hit = raw.get("hit")
    if not hit:
        return JsonResponse({"rows": []})
    rows = []
    for label, value in hit["rows"]:
        if label == "시대" and lang != "en":
            value = trek.AGES_KO.get(value, value)
        rows.append([i18n.PROP_EN.get(label, label) if lang == "en" else label, value])
    return JsonResponse({"unit": hit.get("unit", ""), "rows": rows})


def _moon_original_info(lang, lon, lat):
    """원도의 단위 — 원도·단위·이름·무리·시대·설명. 시대만 한국어판에서 옮긴다 (039)."""
    if not moonmap.available():
        return JsonResponse({"rows": [], "note": i18n.t(msg("원도 파일이 없다"), lang)})
    try:
        hit = moonmap.identify(lon, lat)
    except (moonmap.MoonMapError, OSError) as exc:
        log.warning("달 원도 속성을 읽지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("원도 파일이 없다"), lang), "rows": []}, status=502)
    if not hit:
        return JsonResponse({"rows": []})
    epoch = hit["epoch"] if lang == "en" else moonmap.epoch_ko(hit["epoch"])
    source = hit["citation"] if lang == "en" else f"{hit['citation']} — {hit['map_ko']}"
    rows = [("원도", source), ("단위", hit["unit"]), ("이름", hit["name"]), ("무리", hit["group"]),
            ("시대", epoch), ("설명", hit["description"])]
    rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
    return JsonResponse({"unit": hit["unit"], "color": hit["color"], "rows": rows})


def _spa_age(age: str, lang: str) -> str:
    """SPA 지질도의 시대 — 두 시대에 걸친 것("Nectarian–Pre-Nectarian")은 하나씩 옮긴다."""
    return age if lang == "en" else "–".join(trek.AGES_KO.get(a, a) for a in age.split("–"))


def _moon_spa_info(lang, lon, lat):
    """남극–에이트켄 분지 지질도(Iqbal 외 2026)의 단위 — 원본 GeoTIFF 에서 읽는다 (wetherilli 081)."""
    if not spamap.available():
        return JsonResponse({"rows": [], "note": i18n.t(msg("SPA 지질도 파일이 없다"), lang)})
    try:
        hit = spamap.identify(lon, lat)
    except (spamap.SpaMapError, OSError) as exc:
        log.warning("SPA 지질도 속성을 읽지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("SPA 지질도 파일이 없다"), lang), "rows": []}, status=502)
    if not hit:
        return JsonResponse({"rows": []})
    rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, _spa_age(v, lang) if k == "시대" else v]
            for k, v in hit["rows"]]
    return JsonResponse({"unit": hit["unit"], "color": hit["color"], "rows": rows})


@require_GET
@browser_cached
def moon_legend(request):
    """달 지질 단위 49 가지의 범례. 이름은 상류의 것 그대로다(값이라 옮기지 않는다).

    `?layer=orig` 면 원도의 29 갈래와 구조선 — 우리가 붙인 이름이라 한국어·영어가 따로 있다 (039)."""
    if request.GET.get("layer") == "orig":
        return JsonResponse(moonmap.legend(i18n.lang_of(request)))
    if request.GET.get("layer") == "spa":
        lang = i18n.lang_of(request)
        return JsonResponse({"items": [dict(item, age=_spa_age(item["age"], lang)) for item in spamap.legend()]})
    key = tilecache.key_text("trek-legend", "units")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"items": trek.legend()}
        except trek.TrekError as exc:
            data = _cached_json(key, stale=True)
            if data is None:
                log.warning("달 범례를 받지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request)),
                                     "items": []}, status=502)
        else:
            tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    # 시대 머리 — 한국어판만 옮긴다. 캐시에는 옮기기 전의 것을 둔다. 옛 캐시에 `age` 가 없으면 여기서 채운다
    ko = i18n.lang_of(request) != "en"
    items = []
    for item in data.get("items") or []:
        unit = item.get("unit") or trek._unit_of(item.get("label", ""))
        age = item.get("age") or trek.age_of_unit(unit)
        items.append(dict(item, unit=unit, age=trek.AGES_KO.get(age, age) if ko else age))
    return JsonResponse({"items": items})


# ── NASA Trek 의 MapServer 판 (060) — 달·화성이 함께 쓴다 ─────────────
#
# WMTS 가 없는 판(점·선·면 조사)은 지질도처럼 우리 문이 타일을 굽고 속성·범례를 읽는다. 씨앗(`data/<몸>_trek_layers.json`)에
# `kind: map` 으로 적힌 판만 부른다 — 아무 서비스나 중계하지 않는다. 받은 것은 캐시에 담는다(007).

def _trek_map(request, body, label):
    entry = trek.map_entry(body, label)
    if entry is None:
        return None, JsonResponse({"error": i18n.t(msg("그런 레이어는 없다"), i18n.lang_of(request))}, status=404)
    return entry, None


@require_GET
def trek_map_tile(request, body, label, z, x, y):
    """`trek/<moon|mars|mercury>/map/<판>/<z>/<x>/<y>.png` — MapServer 판의 타일."""
    z, x, y = int(z), int(x), int(y)
    entry, error = _trek_map(request, body, label)
    if error:
        return error
    if not trek.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = tilecache.key_text("trek-map", f"{body}/{label}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.map_tile(body, entry["ms"], z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("Trek 판 타일을 받지 못했다 (%s %s %s/%s/%s): %s", body, label, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def trek_map_polar_tile(request, body, label, pole, z, x, y):
    """`trek/<moon|mars>/map/<판>/p/<n|s>/<z>/<x>/<y>.png` — 극지 MapServer 짝의 극 격자 타일 (wetherilli 085).
    화성은 화성 극 격자(065)이고, 짝이 없는 MapServer 판도 Trek 이 화성 극 투영으로 옮겨 그린다 (wetherilli 192)."""
    z, x, y = int(z), int(x), int(y)
    ms = trek.polar_map(body, label, pole)
    if not ms:
        return JsonResponse({"error": i18n.t(msg("그런 레이어는 없다"), i18n.lang_of(request))}, status=404)
    if not trek.polar_valid(z, x, y) or (body == "mars" and z > trek.MARS_MAX_ZOOM):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = tilecache.key_text("trek-map-polar", f"{body}/{label}/{pole}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.map_polar_tile(body, ms, pole, z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("Trek 극지 판 타일을 받지 못했다 (%s %s %s %s/%s/%s): %s", body, label, pole, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
@browser_cached
def trek_map_info(request, body, label):
    """`?lon=&lat=&z=` — 누른 자리의 것. `{"hits": [{"layer", "rows": [[열, 값], …]}]}`. 옮기지 않는다."""
    lang = i18n.lang_of(request)
    entry, error = _trek_map(request, body, label)
    if error:
        return error
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    z = int(_float(request.GET.get("z")) or 0)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "hits": []}, status=400)
    z = max(0, min(z, trek.MAX_ZOOM))
    key = tilecache.key_text("trek-map-info", f"{body}/{label}/{z}/{lon:.4f},{lat:.4f}")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"hits": trek.map_identify(body, entry["ms"], lon, lat, z)}
        except trek.TrekError as exc:
            log.warning("Trek 판 속성을 읽지 못했다 (%s %s): %s", body, label, exc)
            return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang), "hits": []}, status=502)
        tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse(data)


@require_GET
@browser_cached
def trek_map_legend(request, body, label):
    """MapServer 판의 범례 — `{"items": [{"label", "image"}]}`. 이름은 상류의 것 그대로다."""
    entry, error = _trek_map(request, body, label)
    if error:
        return error
    key = tilecache.key_text("trek-map-legend", f"{body}/{label}")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"items": trek.map_legend(body, entry["ms"])}
        except trek.TrekError as exc:
            data = _cached_json(key, stale=True)
            if data is None:
                log.warning("Trek 판 범례를 받지 못했다 (%s %s): %s", body, label, exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request)),
                                     "items": []}, status=502)
        else:
            tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse(data)


@require_GET
def moon_landings(request):
    """달의 착륙·충돌 지점 — GeoJSON (046). Trek 에서 한 번 받아 캐시에 담는다(백 곳이 안 된다).

    갈래(`kind`)는 열쇠로 보낸다 — `impact`·`soft`·`crewed`·`rover`. 이름을 옮기는 것은 화면이다."""
    key = tilecache.key_text("trek-landings", "all")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"sites": trek.landing_sites()}
        except trek.TrekError as exc:
            data = _cached_json(key, stale=True)
            if data is None:
                log.warning("달 착륙 지점을 받지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request)),
                                     "type": "FeatureCollection", "features": []}, status=502)
        else:
            tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
        "properties": {"이름표": s["name"], "kind": s["kind"], "date": s["date"], "link": s["link"]},
    } for s in data.get("sites") or []]})


@functools.lru_cache(maxsize=1)
def _moon_eva():
    try:
        return json.loads((Path(settings.BASE_DIR).parent / "data" / "moon_apollo_eva.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"type": "FeatureCollection", "features": []}


@require_GET
def moon_eva(request):
    """아폴로 EVA 동선 — 저장소의 씨앗(`data/moon_apollo_eva.json`, Esri UK). 상류를 타지 않는다 (046)."""
    return JsonResponse(_moon_eva())


@functools.lru_cache(maxsize=1)
def _moon_places():
    return trek.load_places(settings.MOON_PLACES_FILE)


@require_GET
def moon_places(request):
    """`?q=tycho` — 달 지명·착륙지 찾기. 저장소의 `data/moon_places.json` 만 뒤진다."""
    return JsonResponse({"results": trek.search_places(_moon_places(), request.GET.get("q", "")[:80])})


# ── 화성 (devlog 058) ─────────────────────────────────────────────────
#
# 달을 그대로 옮겼다. 문은 같은 `trek.py`(의 `mars_*`), 격자도 같은 경위도 격자다. 캐시 열쇠는 `trek-mars…`.

@require_GET
def mars_view(request):
    """화성 (devlog 058). 달 화면의 틀에 USGS 화성 지질도(SIM 3292)와 MOLA–HRSC 지형을 얹는다.

    달처럼 대돌여지도 아이콘의 숨은 차림에서 들어온다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/mars.html", {
        "lang": lang,
        "pointsets": _script_json(_pointset_list("mars")),
        "trek_catalog": _script_json(trek.client_catalog("mars")),   # Trek 판 목록 (060)
        # 가까이서 쓰는 고운 표고 판의 범위·줌 끝 — 달처럼 그 자리에서만 깊은 줌을 묻는다 (wetherilli 274)
        "dem_parts": _script_json([[*part[1], part[2]] for part in trek.MARS_DEM_PARTS]),
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        # 화면이 주소를 짓는 우리 타일의 판 — `?v=` 로 붙여 길게 캐시한다 (wetherilli 183)
        "tile_versions": _script_json(tile_versions("mars")),
        "base": request.path.rsplit("mars", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def mars_tile(request, layer, z, x, y):
    """화성 지질도 타일 — `mars/tiles/units/<z>/<x>/<y>.png`. `craters` 는 우리가 굽는다 (067)."""
    z, x, y = int(z), int(x), int(y)
    if not (layer in ("units", "craters") or marsmap.knows(layer)) or not trek.valid_tile(z, x, y, trek.MARS_MAX_ZOOM):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if layer == "craters":
        return _mars_crater_tile(lambda: marscraters.render_tile(z, x, y))
    if marsmap.knows(layer):
        return _mars_original_tile(request, f"{layer}/{z}/{x}/{y}", lambda: marsmap.render_tile(layer, z, x, y))
    key = mars_tile_key(layer, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.mars_tile(z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("화성 지질도 타일을 받지 못했다 (%s/%s/%s): %s", z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def mars_polar_tile(request, pole, layer, z, x, y):
    """극 평면의 화성 지질도 타일 — `mars/ptiles/<n|s>/units/<z>/<x>/<y>.png` (065).

    격자는 Trek 화성 극 WMTS 의 것(`trek.mars_polar_tile_bbox`)이다. SIM 3292 는 극지 판이 없어 Trek 이
    극 평사도법으로 옮겨 그린다."""
    z, x, y = int(z), int(x), int(y)
    if not (layer in ("units", "craters") or marsmap.knows(layer)) or not trek.polar_valid(z, x, y) \
            or z > trek.MARS_MAX_ZOOM:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if layer == "craters":
        return _mars_crater_tile(lambda: marscraters.render_polar_tile(pole, z, x, y))
    if marsmap.knows(layer):
        return _mars_original_tile(request, f"{pole}p/{layer}/{z}/{x}/{y}",
                                   lambda: marsmap.render_polar_tile(layer, pole, z, x, y))
    key = tilecache.key_text("trek-mars", f"{pole}p/{layer}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.mars_polar_tile(pole, z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("화성 극 지질도 타일을 받지 못했다 (%s %s/%s/%s): %s", pole, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


def _mars_original_tile(request, path, render):
    """화성 옛 지질도 타일 (068) — 달 원도(039)처럼 구운 것을 캐시에 담는다. 파일이 없으면 안내."""
    if not marsmap.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MARS_ORIGINALS), store=False)
    version = marsmap_version()
    key = tilecache.key_text("marsmap", f"{version}/{path}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    try:
        png = render()
    except (marsmap.MarsMapError, sqlite3.Error, OSError) as exc:
        log.warning("화성 옛 지질도 타일을 굽지 못했다 (%s): %s", path, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MARS_ORIGINALS), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


def _mars_crater_tile(render):
    """크레이터 타일 (067) — 한 장에 10 ms 남짓이라 캐시에 담지 않고 그때그때 굽는다. 파일이 없으면 안내."""
    if not marscraters.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MARS_CRATERS), store=False)
    try:
        return _tile(render())
    except (marscraters.MarsCraterError, sqlite3.Error) as exc:
        log.warning("화성 크레이터 타일을 굽지 못했다: %s", exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MARS_CRATERS), store=False)


@require_GET
def mars_dem(request, z, x, y):
    """화성 표고 격자 — `mars/dem/<z>/<x>/<y>.png`, 65×65 Terrarium (MOLA–HRSC). 못 받으면 502 (달과 같다)."""
    z, x, y = int(z), int(x), int(y)
    # 줌 `MARS_DEM_MAX_ZOOM` 너머는 고운 판(탐사 착륙지의 HiRISE 따위)이 걸친 장만 있다 (wetherilli 274)
    part = trek.mars_dem_part(z, x, y) if trek.valid_tile(z, x, y, trek.MARS_DEM_FINE_MAX) else None
    if not trek.valid_tile(z, x, y, trek.MARS_DEM_MAX_ZOOM) and part is None:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = mars_dem_key(z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.mars_dem_tile(z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("화성 표고를 받지 못했다 (%s/%s/%s): %s", z, x, y, exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request))}, status=502)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
@browser_cached
def mars_info(request):
    """`?lon=137.4&lat=-4.6` — 누른 자리의 지질 단위. 값은 옮기지 않고 시대만 한국어판에서 옮긴다."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "rows": []}, status=400)
    if request.GET.get("layer") == "craters":
        return _mars_crater_info(lon, lat, lang)
    if request.GET.get("layer") == "orig":
        return _mars_original_info(lon, lat, lang)
    # 1e-3° 는 화성에서 60 m 남짓이다 — 1:2000만 지도에는 한 점이다
    key = tilecache.key_text("trek-mars-info", f"{lon:.3f},{lat:.3f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"hit": trek.mars_identify(lon, lat)}
        except trek.TrekError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("화성 속성을 읽지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    hit = raw.get("hit")
    if not hit:
        return JsonResponse({"rows": []})
    rows = [[i18n.PROP_EN.get(label, label) if lang == "en" else label, value] for label, value in hit["rows"]]
    if hit.get("age"):
        age = hit["age"] if lang == "en" else trek.mars_age_ko(hit["age"])
        rows.insert(1, [i18n.PROP_EN.get("시대", "시대") if lang == "en" else "시대", age])
    return JsonResponse({"unit": hit.get("unit", ""), "rows": rows})


def _mars_original_info(lon, lat, lang):
    """옛 지질도·지역도의 단위 — 판·단위·이름·시대·지형구·축척 (068, wetherilli 079). 시대만 한국어판에서 옮긴다."""
    if not marsmap.available():
        return JsonResponse({"rows": [], "note": i18n.t(msg("옛 지질도 파일이 서버에 없다"), lang)})
    try:
        hit = marsmap.identify(lon, lat)
    except (marsmap.MarsMapError, sqlite3.Error) as exc:
        log.warning("화성 옛 지질도 속성을 읽지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("속성을 받지 못했다"), lang), "rows": []}, status=500)
    if not hit:
        return JsonResponse({"rows": []})
    age = hit["age"] if lang == "en" else trek.mars_age_ko(hit["age"])
    # 판 — 한국어판은 "I-1802-A — 서쪽 적도", 영어판은 번호만. MTM 지역도는 사각형 이름이 곧 이름이다
    source = hit["map"] if lang == "en" or not hit["map_ko"] else f"{hit['map']} — {hit['map_ko']}"
    rows = [("원도", source), ("단위", hit["unit"]), ("이름", hit["name"]), ("시대", age), ("지형구", hit["note"]),
            ("축척", hit["scale"]), ("지은이", hit["citation"])]
    rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
    return JsonResponse({"unit": hit["unit"], "color": hit["color"], "rows": rows})


def _mars_crater_info(lon, lat, lang):
    """누른 자리를 품은 가장 작은 크레이터 (067). 값(이름·형태 기호)은 옮기지 않는다."""
    if not marscraters.available():
        return JsonResponse({"rows": [], "note": i18n.t(msg("크레이터 파일이 서버에 없다"), lang)})
    try:
        hit = marscraters.identify(lon, lat)
    except (marscraters.MarsCraterError, sqlite3.Error) as exc:
        log.warning("화성 크레이터를 읽지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("속성을 받지 못했다"), lang), "rows": []}, status=500)
    if not hit:
        return JsonResponse({"rows": [], "note": i18n.t(msg("여기에는 지름 1 km 넘는 크레이터가 없다"), lang)})
    state = marscraters.STATES.get(hit["state"], marscraters.STATES[""])
    rows = [("이름", hit["name"]), ("지름", f"{hit['d_km']:.2f} km"),
            ("깊이", f"{hit['depth_km']:.2f} km" if hit["depth_km"] is not None else ""),
            ("안쪽 형태", hit["morph"]), ("분출물 형태", hit["ejecta"]),
            ("보존 상태", state[2] if lang == "en" else state[1]),
            ("가운데", f"{hit['lat']:.3f}, {hit['lon']:.3f}"), ("번호", hit["id"])]
    return JsonResponse({"unit": "", "color": state[0], "rows": [
        [i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]})


@require_GET
@browser_cached
def mars_legend(request):
    """화성 지질 단위의 범례. 이름은 상류의 것 그대로, 묶는 머리(시대)만 한국어판에서 옮긴다."""
    if request.GET.get("layer") == "orig":
        # 옛 지질도(068) — 단위 95 가지와 구조선 갈래. 단위 이름은 원문 값이라 옮기지 않는다
        return JsonResponse(marsmap.legend(i18n.lang_of(request)))
    key = tilecache.key_text("trek-mars-legend", "units")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"items": trek.mars_legend()}
        except trek.TrekError as exc:
            data = _cached_json(key, stale=True)
            if data is None:
                log.warning("화성 범례를 받지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request)),
                                     "items": []}, status=502)
        else:
            tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    ko = i18n.lang_of(request) != "en"
    return JsonResponse({"items": [dict(item, age=trek.MARS_PERIODS_KO.get(item.get("age"), item.get("age")) if ko
                                        else item.get("age")) for item in data.get("items") or []]})


def _mars_cached(request, name, fetch, what):
    key = tilecache.key_text("trek-mars-" + name, "all")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"items": fetch()}
        except trek.TrekError as exc:
            data = _cached_json(key, stale=True)
            if data is None:
                log.warning("화성 %s 을 받지 못했다: %s", what, exc)
                return None
        else:
            tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    return data.get("items") or []


def _mars_failed(request):
    return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request)),
                         "type": "FeatureCollection", "features": []}, status=502)


@require_GET
def mars_landings(request):
    """화성 착륙선·로버의 이야기 지점 — GeoJSON. 갈래(`kind`)는 `lander`·`rover`."""
    sites = _mars_cached(request, "landings", trek.mars_landings, "착륙 지점")
    if sites is None:
        return _mars_failed(request)
    sites = sites + zhurong.landings()              # Trek 에 없는 주룽 — 저장소의 파일 (066)
    return JsonResponse({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
        "properties": {"이름표": s["name"], "임무": s["mission"], "kind": s["kind"]},
    } for s in sites]})


@require_GET
def mars_traverses(request):
    """로버가 달린 길 — GeoJSON MultiLineString, 임무마다 하나."""
    items = _mars_cached(request, "traverses", trek.mars_traverses, "로버 동선")
    if items is None:
        return _mars_failed(request)
    items = items + [t for t in [zhurong.traverse()] if t]    # 주룽 (066)
    return JsonResponse({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": t["paths"]},
        "properties": {"임무": t["mission"]},
    } for t in items if t.get("paths")]})


@functools.lru_cache(maxsize=1)
def _mars_places():
    return trek.load_places(settings.MARS_PLACES_FILE) + zhurong.place()


@require_GET
def mars_places(request):
    """`?q=gale` — 화성 지명·착륙지 찾기. 저장소의 `data/mars_places.json` 만 뒤진다."""
    return JsonResponse({"results": trek.search_places(_mars_places(), request.GET.get("q", "")[:80])})


# ── 수성 (wetherilli P10) ─────────────────────────────────────────────
#
# 화성 화면을 옮겼다. 문은 `trek.py` 의 `mercury_*` 다. 지질도는 우리가 굽는다 — USGS 1:500만 도폭 합본(`mercurymap.py`, wetherilli 144)

@require_GET
def mercury_view(request):
    """수성 (wetherilli P10). 화성 화면의 틀에 MESSENGER 영상과 표고를 얹는다.

    달·화성처럼 대돌여지도 아이콘의 숨은 차림에서 들어온다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/mercury.html", {
        "lang": lang,
        "pointsets": _script_json(_pointset_list("mercury")),
        "trek_catalog": _script_json(trek.client_catalog("mercury")),
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        # 화면이 주소를 짓는 우리 타일의 판 — `?v=` 로 붙여 길게 캐시한다 (wetherilli 183)
        "tile_versions": _script_json(tile_versions("mercury")),
        "base": request.path.rsplit("mercury", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def mercury_dem(request, z, x, y):
    """수성 표고 격자 — `mercury/dem/<z>/<x>/<y>.png`, 65×65 Terrarium. 못 받으면 502 (화성과 같다)."""
    z, x, y = int(z), int(x), int(y)
    if not trek.valid_tile(z, x, y, trek.MERCURY_DEM_MAX_ZOOM):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = tilecache.key_text("trek-mercury-dem", f"{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.mercury_dem_tile(z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("수성 표고를 받지 못했다 (%s/%s/%s): %s", z, x, y, exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request))}, status=502)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def mercury_tile(request, layer, z, x, y):
    """수성 지질도 타일 — `mercury/tiles/<units|lines>/<z>/<x>/<y>.png` (wetherilli 144). 우리가 굽는다.
    극 평면은 화면이 경위도 타일을 옮겨 그린다 — 극 타일을 따로 굽지 않는다."""
    z, x, y = int(z), int(x), int(y)
    if not mercurymap.knows(layer) or not trek.valid_tile(z, x, y, mercurymap.MAX_ZOOM):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not mercurymap.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MERCURY_GEOLOGY), store=False)
    version = mercurymap_version()
    key = tilecache.key_text("mercurymap", f"{version}/{layer}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    try:
        png = mercurymap.render_tile(layer, z, x, y)
    except (mercurymap.MercuryMapError, sqlite3.Error, OSError) as exc:
        log.warning("수성 지질도 타일을 굽지 못했다 (%s/%s/%s/%s): %s", layer, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MERCURY_GEOLOGY), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
@browser_cached
def mercury_info(request):
    """`?lon=-31.5&lat=-11.3` — 누른 자리의 지질 단위. 값(기호·무리·설명)은 원도의 것이라 옮기지 않는다."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "rows": []}, status=400)
    if not mercurymap.available():
        return JsonResponse({"rows": [], "note": i18n.t(msg("수성 지질도 파일이 서버에 없다"), lang)})
    try:
        hit = mercurymap.identify(lon, lat)
    except (mercurymap.MercuryMapError, sqlite3.Error) as exc:
        log.warning("수성 지질도 속성을 읽지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("속성을 받지 못했다"), lang), "rows": []}, status=500)
    if not hit:
        return JsonResponse({"rows": [], "note": i18n.t(msg("마리너 10 이 찍지 못해 지질도가 없는 곳이다"), lang)})
    grade = ""
    if hit["crater_class"]:
        grade = i18n.t(msg("c{n} — c1 가장 닳음, c5 가장 또렷함", n=hit["crater_class"]), lang)
    source = f"{hit['map']} ({hit['quad']}) · {hit['by']} {hit['year']}" if hit["map"] else hit["quad"]
    rows = [("단위", hit["unit"]), ("무리", hit["group"]), ("크레이터 등급", grade),
            ("설명", hit["description"]), ("원도", source), ("축척", "1:5,000,000"),
            ("지은이", mercurymap.CITATION)]
    return JsonResponse({"unit": hit["unit"], "color": hit["color"], "rows": [
        [i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]})


@require_GET
@browser_cached
def mercury_legend(request):
    """수성 지질 단위(갈래로 묶은 것)와 구조선 갈래."""
    return JsonResponse(mercurymap.legend(i18n.lang_of(request)))


@require_GET
def mercury_places(request):
    """`?q=caloris` — 수성 지명 찾기. 저장소의 `data/mercury_places.json` 만 뒤진다."""
    return JsonResponse({"results": trek.search_places(trek.load_places(settings.MERCURY_PLACES_FILE),
                                                       request.GET.get("q", "")[:80])})


# ── 온 지구 (wetherilli P06·086) ─────────────────────────────────────
#
# 달·화성 화면의 틀에 지구를 얹는다. 지질도는 Macrostrat(`macrostrat.py`) 하나이고, 배경(NASA GIBS)·표고(AWS
# Terrarium)는 브라우저가 곧장 부른다 — 지역 탭의 극지 배경·3D 가 이미 그렇게 쓴다

@require_GET
def earth_view(request):
    """온 지구 (wetherilli P06). 지역 탭과 따로, 달·화성처럼 둥근 지구로 본다.

    대돌여지도 아이콘의 숨은 차림에서 들어온다. 점묶음은 지역 화면과 같은 `earth` 의 것이다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/earth.html", {
        "lang": lang,
        "pointsets": _script_json(_pointset_list("earth")),
        # 그때의 지구에 얹는 것의 시점 — 막대 위의 띠와 캡션이 쓴다 (wetherilli 097). 파일이 없으면 빈다
        "then_data": _script_json({"coast": paleocoast.ages(), "fossils": fossils.available(),
                                   # 화석 산지 밀도 (wetherilli 286) — 같은 pbdb.sqlite 에서. 범례는 비율
                                   "fossildensity": fossils.density_legend(lang) if fossils.available() else [],
                                   # 홀로세 화산 (wetherilli 134) — 받아 둔 것이 있을 때만 목록에 선다. 범례도 함께
                                   "volcanoes": volcanoes.legend(lang) if volcanoes.available() else [],
                                   # 플라이스토세 화산 (wetherilli 194) — 따로 받은 것이 있을 때만 따로 레이어가 선다
                                   "pleistocene": (volcanoes.legend(lang, "pleistocene")
                                                   if volcanoes.available("pleistocene") else []),
                                   # 지진 (wetherilli 138) — 구운 것이 있을 때만. 규모 칸 셋이 레이어가 된다. 범례는 깊이의 색
                                   "quakes": quakes.legend(lang) if quakes.available() else [],
                                   # 최근 지진 (wetherilli 292) — 매시 받은 피드가 있을 때만. 범례는 지난 시간의 색
                                   "recentquakes": recentquakes.legend(lang) if recentquakes.available() else [],
                                   # 제4기 고생태 산지 (wetherilli 139) — 구운 것이 있을 때만. 자료형 칸 다섯이 레이어가 된다
                                   "neotoma": paleoeco.legend(lang) if paleoeco.available() else [],
                                   "crust": crust.legend() if crust.grid() else [],
                                   # 세계 빙하 RGI 7.0 (wetherilli 289) — 구운 것이 있을 때만 레이어가 선다
                                   "glaciers": glaciers.legend(lang) if glaciers.available() else [],
                                   # 충돌구·거대 화성암 지대 (wetherilli 283) — 파일이 있을 때만 레이어가 선다
                                   "impacts": ({"impacts": impacts.legend("impacts", lang), "lips": impacts.legend("lips", lang)}
                                               if impacts.available() else {}),
                                   # 세계 활성단층 GEM (wetherilli 279) — 구운 것이 있을 때만 레이어가 선다
                                   "faults": faults.legend(lang) if faults.available() else [],
                                   # 세계 광상 USGS (wetherilli 276) — 구운 것이 있을 때만. 광종 칸 여섯이 레이어가 된다
                                   "minerals": minerals.legend(lang) if minerals.available() else [],
                                   # 지각 응력 World Stress Map 2025 (wetherilli 273) — 구운 것이 있을 때만 레이어가 선다
                                   "stress": stress.legend(lang) if stress.available() else [],
                                   # 판 경계·세계 지질구 Hasterok 2022 (wetherilli 272) — 파일이 있을 때만 레이어가 선다
                                   "tectonics": ({"boundaries": tectonics.legend("boundaries", lang),
                                                  "provinces": tectonics.legend("provinces", lang)} if tectonics.available() else {}),
                                   # 세계 암상 GLiM·지열류 IHFC (wetherilli 267) — 구운 것이 있을 때만 레이어가 선다
                                   "glim": glim.legend(lang) if glim.grid() else [],
                                   "heatflow": heatflow.legend(lang) if heatflow.available() else [],
                                   # 해양 지각 연대·퇴적층 두께 (wetherilli 264) — 구운 것이 있을 때만 레이어가 선다. 범례도 함께
                                   "seafloor": {k: seafloor.legend(k) for k in seafloor.KINDS if seafloor.available(k)},
                                   "icemargins": icemargins.stops(),
                                   # 해류 (koprifossillab 014) — 구워 둔 날이 있을 때만 목록에 선다
                                   "ocean": bool(ocean.read_index("ecco2")["times"]),
                                   # 아라온호 항적 (koprifossillab 006) — 쌓은 것이 있고 연구실 안에서 열 때만
                                   "araon": kopri.araon_available() and not _lab_only("kopri:araon"),
                                   "araon_periods": list(kopri.ARAON_PERIODS),
                                   # 맨틀 — 시점마다 레이어의 점 수(받은 바이트를 점과 이음으로 가르는 데 쓴다)
                                   "mantle": {f["frame"]: {k: v["points"] for k, v in f["layers"].items()}
                                              for f in (mantle.catalogue() or {}).get("frames", [])}}),
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        # 화면이 주소를 짓는 우리 타일의 판 — `?v=` 로 붙여 길게 캐시한다 (wetherilli 183)
        "tile_versions": _script_json(tile_versions("earth")),
        "base": request.path.rsplit("earth", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def earth_tile(request, z, x, y):
    """온 지구의 지질도 타일 — `earth/tiles/geology/<z>/<x>/<y>.png`, 3857 z/x/y (Macrostrat carto)."""
    z, x, y = int(z), int(x), int(y)
    if not macrostrat.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    # 밑에 거친 대역을 깐 것(`macrostrat.fill`)을 따로 담는다. 까는 법을 고치면 `FILL_VERSION` 을 올린다
    key = tilecache.key_text("macrostrat", f"filled/{MACROSTRAT_FILL_VERSION}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = macrostrat.fill(z, x, y, _macrostrat_raw)
    except macrostrat.MacrostratError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("Macrostrat 타일을 받지 못했다 (%s/%s/%s): %s", z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)                   # 바다의 빈 타일도 담는다 — 다시 물을 까닭이 없다
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


MACROSTRAT_FILL_VERSION = "2"                  # 2 — 조상을 색마다 매끄럽게 늘린다 (wetherilli 105)


def _macrostrat_raw(z, x, y) -> bytes:
    """상류의 carto 타일 그대로 — 캐시를 거친다. 조상 타일(줌 5·9)은 여러 타일이 나눠 쓴다."""
    key = tilecache.key_text("macrostrat", f"carto/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return hit
    try:
        png = macrostrat.get_tile(z, x, y)
    except macrostrat.MacrostratError:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return old
        raise
    tilecache.put(key, png)
    return png


@require_GET
@browser_cached
def earth_info(request):
    """`?lon=126.98&lat=37.57&z=6` — 누른 자리의 지질 단위. 그 줌의 판으로 읽는다(`macrostrat.identify`).

    단위마다 `rows`(팝업의 표)와 밑·윗 연대(Ma)를 준다. 원도 인용은 `refs` 로 따로."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    z = max(0, min(macrostrat.MAX_ZOOM, _int(request.GET.get("z"), 6)))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang), "units": []}, status=400)
    # 1e-4° 는 10 m 남짓이다. 축척(줌의 갈래)이 같으면 같은 판이라 같은 답이다
    key = tilecache.key_text("macrostrat-info", f"{macrostrat.scale_of(z)}/{lang}/{lat:.4f},{lon:.4f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = macrostrat.identify(lon, lat, z, lang)
        except macrostrat.MacrostratError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("Macrostrat 속성을 읽지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang), "units": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    units = []
    for u in raw.get("units", []):
        rows = [("단위", u["name"]), ("지층", u["strat"]), ("시대", u["age"]),
                ("연대 (Ma)", _age_span(u["b_age"], u["t_age"])), ("암상", u["lith"]),
                ("설명", u["descrip"]), ("원도", raw.get("refs", {}).get(str(u["source_id"]), ""))]
        # 그때의 자리 (wetherilli 087) — 단위의 윗·밑 연대에서 한 줄씩. 젊은 쪽이 먼저다
        then, reached = _paleo_rows(lon, lat, [a for a in (u["t_age"], u["b_age"]) if a is not None], lang)
        # `then` 은 옮겨진 연대들 — 화면이 그 연대로 EarthThruTime3D 를 여는 링크를 단다 (wetherilli 088)
        units.append({"rows": [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v] + then,
                      "name": u["name"], "color": u["color"], "b_age": u["b_age"], "t_age": u["t_age"],
                      "scale": u["scale"], "then": reached})
    return JsonResponse({"units": units})


def _lonlat_text(lon: float, lat: float, lang: str) -> str:
    if lang == "en":
        return f"{abs(lat):.2f}° {'N' if lat >= 0 else 'S'} · {abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"
    return f"{'북위' if lat >= 0 else '남위'} {abs(lat):.2f}° · {'동경' if lon >= 0 else '서경'} {abs(lon):.2f}°"


def _paleo_text(got: dict, lang: str) -> str:
    """`paleo.Model.carry` 의 답 하나를 사람이 읽는 말로."""
    if "lon" in got:
        return _lonlat_text(got["lon"], got["lat"], lang)
    if got["reason"] == "ocean":
        return i18n.t(msg("바다 밑이다 — 대륙 다각형이 없어 옮기지 못한다"), lang)
    if got["reason"] == "future":
        return i18n.t(msg("앞날은 셈하지 않는다"), lang)
    return i18n.t(msg("이 판은 {reach} Ma 까지만 거슬러 옮긴다", reach=f"{got['reach']:g}"), lang)


def _paleo_rows(lon: float, lat: float, ages: list, lang: str) -> tuple:
    """`([[그때의 자리 (N Ma), 좌표]…], [옮겨진 연대…])`. 모델 파일이 없으면 둘 다 비었다 — 팝업은 그 줄 없이 돈다."""
    m = paleo.model()
    if m is None or not ages:
        return [], []
    plate = m.plate_at(lon, lat)
    if plate is None:                                   # 바다 밑 — 연대마다 같은 말을 되풀이하지 않는다
        return [[i18n.t(msg("그때의 자리"), lang), _paleo_text({"reason": "ocean"}, lang)]], []
    rows, reached = [], []
    for age in dict.fromkeys(float(a) for a in ages):
        got = m.carry(lon, lat, age, plate)
        rows.append([i18n.t(msg("그때의 자리 ({age} Ma)", age=f"{age:g}"), lang), _paleo_text(got, lang)])
        if "lon" in got:
            reached.append(age)
    return rows, reached


@require_GET
def earth_paleo(request):
    """`?lon=126.98&lat=37.57&age=250` — 오늘의 한 자리가 그 연대에 있던 곳 (PALEOMAP 2016, `paleo.py`).

    팝업의 "옛 위치" 칸과 점묶음이 부른다. 계산이지 관측이 아니다."""
    lang = i18n.lang_of(request)
    lat, lon, age = _float(request.GET.get("lat")), _float(request.GET.get("lon")), _float(request.GET.get("age"))
    if lat is None or lon is None or age is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon·age 가 없다"), lang)}, status=400)
    m = paleo.model()
    if m is None:
        return JsonResponse({"error": i18n.t(msg("판 회전 파일이 서버에 없다"), lang)}, status=503)
    got = m.carry(lon, lat, age)
    return JsonResponse({**got, "text": _paleo_text(got, lang), "model": m.meta.get("title", "")})


@require_GET
def earth_paleo_tile(request, style, age, z, x, y):
    """`earth/paleo/tiles/<land|edge|coast>/<Ma>/<z>/<x>/<y>.png` — 그 연대의 판 조각 (wetherilli 091, `paleo.render_tile`).

    경위도 격자(줌 0 이 180° 두 장)다. `land` 는 칠한 땅(옛 연대의 지구), `edge` 는 경계선만(오늘의 배경 위에),
    `coast` 는 가장 가까운 시점의 옛 해안선(wetherilli 097, `paleocoast.render_tile`)."""
    z, x, y, age = int(z), int(x), int(y), int(age)
    if style not in paleo.STYLES + ("coast",) or not paleo.valid_tile(z, x, y) or age > 1100:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if style == "coast":
        return _coast_tile(request, age, z, x, y)
    if paleo.model() is None:
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    version = paleo_version()
    key = tilecache.key_text("paleomap", f"{version}/{style}/{age}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = paleo.render_tile(float(age), style, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


def _coast_tile(request, age, z, x, y):
    """옛 해안선 한 장. 10 Myr 안에 시점이 없거나 파일이 없으면 빈 타일 — 판 조각만 보인다."""
    at = paleocoast.stop(age)
    if at is None:
        return _tile(tiles.blank_tile(), store=False)
    version = paleocoast_version()
    key = tilecache.key_text("paleocoast", f"{version}/{at:g}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = paleocoast.render_tile(at, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_paleo_at(request):
    """`?lon=105&lat=30.6&age=250` — **그때의 지구**를 눌렀을 때. 그 자리에 있던 판 조각과 그 자리의 오늘의 좌표
    (wetherilli 091). 화면은 그 오늘의 좌표로 지질 단위를 다시 묻는다."""
    lang = i18n.lang_of(request)
    lat, lon, age = _float(request.GET.get("lat")), _float(request.GET.get("lon")), _float(request.GET.get("age"))
    if lat is None or lon is None or age is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon·age 가 없다"), lang)}, status=400)
    m = paleo.model()
    if m is None:
        return JsonResponse({"error": i18n.t(msg("판 회전 파일이 서버에 없다"), lang)}, status=503)
    hit = m.plate_then(lon, lat, age)
    if hit is None:
        return JsonResponse({"age": age, "text": i18n.t(msg("판 조각 밖이다 — 그때 바다였거나, 섭입으로 사라진 곳이다"), lang)})
    rows = [[i18n.t(msg("판"), lang), str(hit["pid"])],
            [i18n.t(msg("오늘의 자리"), lang), _lonlat_text(hit["today_lon"], hit["today_lat"], lang)],
            [i18n.t(msg("거슬러 옮기는 끝"), lang), f"{hit['reach']:g} Ma"]]
    if hit["gone"]:
        rows.append([i18n.t(msg("오늘"), lang), i18n.t(msg("이 조각은 오늘까지 남지 않았다 — 오늘의 자리는 그 판이 가 있을 곳이다"), lang)])
    return JsonResponse({**hit, "age": age, "rows": rows, "model": m.meta.get("title", "")})


@require_GET
def earth_paleo_set(request, pk):
    """`pointsets/<id>/paleo/?age=250` — 점묶음의 점을 그 연대의 자리로 옮긴 GeoJSON (wetherilli 091).

    점만 옮긴다 — 선·면의 꼭짓점은 서로 다른 판에 걸칠 수 있다. 점마다 `_today`(오늘의 좌표)를 싣고, 못 옮긴 점은
    오늘의 자리에 두고 `_paleo` 에 까닭을 적는다."""
    lang = i18n.lang_of(request)
    pointset = get_object_or_404(PointSet, pk=pk)
    age = _float(request.GET.get("age"))
    m = paleo.model()
    if age is None or m is None:
        return JsonResponse({"error": i18n.t(msg("판 회전 파일이 서버에 없다"), lang)}, status=400 if age is None else 503)
    out = []
    for f in _pointset_features(pointset)["features"]:
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        got = m.carry(lon, lat, age, m.plate_at_cached(lon, lat))
        props = dict(f.get("properties") or {}, _today=[lon, lat])
        if "lon" in got:
            g = {"type": "Point", "coordinates": [got["lon"], got["lat"]]}
        else:
            props["_paleo"] = _paleo_text(got, lang)
        out.append({"type": "Feature", "geometry": g, "properties": props})
    return JsonResponse({"type": "FeatureCollection", "features": out}, json_dumps_params={"ensure_ascii": False})


# ── 지명·강·호수·빙하 (wetherilli 102) ─────────────────────────────

@require_GET
def earth_ne_tile(request, style, z, x, y):
    """`earth/ne/tiles/<water|ice>/<z>/<x>/<y>.png` — Natural Earth 의 강·호수, 빙하·빙붕 (`naturalearth.render_tile`)."""
    z, x, y = int(z), int(x), int(y)
    if style not in naturalearth.STYLES or not naturalearth.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    version = ne_version()
    key = tilecache.key_text("naturalearth", f"{version}/{style}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = naturalearth.render_tile(style, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_wind_index(request):
    """`earth/wind/` — 구워 둔 바람의 목록 (koprifossillab P02). 지금의 바람(GFS)과 지난 바람(ERA5), 시각마다 u·v 를 되돌릴 값.

    지금의 바람은 여섯 시간마다 새 판이 서므로 오래 캐시하지 않는다.
    """
    response = JsonResponse({source: wind.read_index(source) for source in wind.SOURCES},
                            json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "public, max-age=600"
    return response


@require_GET
def earth_wind_png(request, source, stamp, level):
    """`earth/wind/<출처>/<시각>/<높이>.png` — R=u·G=v 를 그 장의 최솟값·최댓값으로 담은 1440×721 (`wind.encode`)."""
    if not wind.valid(source, stamp, level):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    try:
        png = wind.png_path(source, stamp, level).read_bytes()
    except OSError:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    response = HttpResponse(png, content_type="image/png")
    # 시각이 주소에 있다 — 한 번 구운 것은 바뀌지 않는다. 다시 굽는 일이 드물어 하루로 둔다
    response["Cache-Control"] = "public, max-age=86400"
    response["Access-Control-Allow-Origin"] = "*"
    return response


@require_GET
def earth_ocean_index(request):
    """`earth/ocean/` — 구워 둔 해류의 목록 (koprifossillab 014). 날마다 u·v 를 되돌릴 값. 사람이 구울 때만 바뀐다."""
    response = JsonResponse({source: ocean.read_index(source) for source in ocean.SOURCES},
                            json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def earth_ocean_png(request, source, stamp):
    """`earth/ocean/<출처>/<날>/surface.png` — R=u·G=v·B=바다 가리개, 1440×720 (`ocean.encode`)."""
    if not ocean.valid(source, stamp):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    try:
        png = ocean.png_path(source, stamp).read_bytes()
    except OSError:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    response = HttpResponse(png, content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    response["Access-Control-Allow-Origin"] = "*"
    return response


@require_GET
def earth_places(request):
    """`?q=바이칼` — 온 지구의 찾기. 지명(Natural Earth 의 도시·산맥·바다·호수·강)에 더해 화석 산지·지층(PBDB)과 화산(GVP)의
    이름도 찾는다(wetherilli 187). 모두 모아 둔 파일이라 상류를 타지 않는다.

    결과마다 `group`(place·volcano·formation·fossil)이 붙고, `kind` 는 화면의 딱지 글이다 — 지명은 그 갈래(도시·강 …),
    나머지는 "화산"·"지층"·"화석". 같은 이름 → 앞이 같은 것 → 들어 있는 것 차례로 섞고, 같은 차례면 지명·화산·지층·화석 순이다"""
    lang = i18n.lang_of(request)
    q = request.GET.get("q", "")[:80]
    hits = [dict(h, group="place") for h in naturalearth.search(q, lang, limit=10)]
    for v in volcanoes.search(q):
        last = volcanoes.year_text(v["last"])
        sub = " · ".join(x for x in (v["country"], i18n.t(msg("마지막 분화 {year}", year=i18n.t(last, lang)), lang)
                                     if last else "") if x)
        hits.append({"group": "volcano", "kind": i18n.t(msg("화산"), lang), "title": v["name"], "sub": sub,
                     "lat": v["lat"], "lon": v["lon"]})
    sites, forms = fossils.search(q)
    for f in forms:
        hits.append({"group": "formation", "kind": i18n.t(msg("지층"), lang), "title": f["formation"],
                     "sub": " · ".join(x for x in (i18n.t(msg("화석 산지 {n} 곳", n=f["n"]), lang),
                                                   _fossil_span(f["early"], f["late"], lang)) if x),
                     "lat": f["lat"], "lon": f["lon"]})
    for r in sites:
        hits.append({"group": "fossil", "kind": i18n.t(msg("화석"), lang), "title": r["name"],
                     "sub": " · ".join(x for x in (r["formation"], _fossil_span(r["early"], r["late"], lang)) if x),
                     "lat": r["lat"], "lon": r["lon"]})
    order = {"place": 0, "volcano": 1, "formation": 2, "fossil": 3}
    folded = arcpoints.fold(q)

    def rank(hit):
        name = arcpoints.fold(hit["title"].split(" (")[0])
        return (0 if name == folded else 1 if name.startswith(folded) else 2, order[hit["group"]])
    hits = sorted(hits, key=rank)[:25]                    # 같은 차례 안에서는 갈래마다 받은 차례 그대로다(정렬이 안정하다)
    sources = ["Natural Earth 10 m"] + (["GVP"] if any(h["group"] == "volcano" for h in hits) else []) + \
        (["PBDB"] if any(h["group"] in ("formation", "fossil") for h in hits) else [])
    return JsonResponse({"results": hits, "sources": sources}, json_dumps_params={"ensure_ascii": False})


def _fossil_span(early, late, lang):
    """PBDB 의 시대 칸 — `early – late`, 같으면 하나. 한국어판은 ICS 한글판 이름으로"""
    span = (early or "") + (f" – {late}" if late and late != early else "")
    return i18n.age_ko(span) if lang == "ko" and span else span


@require_GET
@gzip_page
def earth_labels(request):
    """산맥·고원·사막·바다 따위의 이름표 — `[이름, 경도, 위도, 순위]`, 큰 것부터."""
    return JsonResponse({"labels": naturalearth.labels(i18n.lang_of(request)), "credit": naturalearth.CREDIT},
                        json_dumps_params={"ensure_ascii": False})


# ── 최근 빙기의 빙상 가장자리 (wetherilli 104) ────────────────────────

@require_GET
def earth_icemargin_tile(request, ka, z, x, y):
    """`earth/icemargins/tiles/<ka>/<z>/<x>/<y>.png` — 그 연대(천 년 단위)의 빙상 가장자리 (`icemargins.render_tile`)."""
    z, x, y, ka = int(z), int(x), int(y), int(ka)
    if not paleo.valid_tile(z, x, y) or ka > 1000:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    picked = icemargins.pick(float(ka))
    if not picked:
        return _tile(tiles.blank_tile(), store=False)
    tag = "-".join(f"{k}{v:g}" for k, v in sorted(picked.items()))
    version = icemargins_version()
    key = tilecache.key_text("icemargins", f"{version}/{tag}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = icemargins.render_tile(float(ka), z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


# ── 맨틀 슬랩 (wetherilli 106) ───────────────────────────────────────

@require_GET
def earth_mantle(request, frame, layer):
    """`earth/mantle/<시점>/<slabs|piles|boundaries>.bin` — OPT1 의 한 시점 한 레이어(float32 xyz + uint32 이음).
    구운 목록에 있는 파일만 낸다. gzip 을 받는 브라우저에는 구울 때 만든 `.gz` 를 그대로 — 몇 MB 라 줄이는 값이 크다."""
    path = mantle.file_for(int(frame), layer)
    if path is None or not path.exists():
        return JsonResponse({"error": i18n.t(msg("맨틀 파일이 서버에 없다"), i18n.lang_of(request))}, status=404)
    gz = path.with_name(path.name + ".gz")
    if "gzip" in request.META.get("HTTP_ACCEPT_ENCODING", "") and gz.exists():
        response = HttpResponse(gz.read_bytes(), content_type="application/octet-stream")
        response["Content-Encoding"] = "gzip"
    else:
        response = HttpResponse(path.read_bytes(), content_type="application/octet-stream")
    response["Vary"] = "Accept-Encoding"
    response["Cache-Control"] = "public, max-age=86400"     # 주소에 확인값이 없다 — 다시 구우면 하루 안에 따라온다
    return response


# ── 지각 두께 (wetherilli 101) ───────────────────────────────────────

@require_GET
def earth_crust_tile(request, z, x, y):
    """`earth/crust/tiles/<z>/<x>/<y>.png` — CRUST 2.0 지각 두께, 경위도 격자 (`crust.render_tile`)."""
    z, x, y = int(z), int(x), int(y)
    if not crust.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if crust.grid() is None:
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    version = crust_version()
    key = tilecache.key_text("crust", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = crust.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


#: 온 지구 화면의 레이어 이름 → 판 (wetherilli 264)
SEAFLOOR_LAYERS = {"seaage": "age", "sediment": "sediment"}


@require_GET
def earth_seafloor_tile(request, layer, z, x, y):
    """`earth/seafloor/<seaage|sediment>/<z>/<x>/<y>.png` — 해양 지각 연대·퇴적층 두께, 경위도 격자 (`seafloor.render_tile`)"""
    kind, z, x, y = SEAFLOOR_LAYERS.get(layer), int(z), int(x), int(y)
    if kind is None or not seafloor.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not seafloor.available(kind):
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    version = seafloor_version(kind)
    key = tilecache.key_text("seafloor", f"{kind}/{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = seafloor.render_tile(kind, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_seafloor_at(request):
    """`?layer=seaage|sediment&lon=&lat=` — 누른 자리의 해양 지각 연대(Ma)·퇴적층 두께(m)"""
    lang = i18n.lang_of(request)
    kind = SEAFLOOR_LAYERS.get(request.GET.get("layer", ""))
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if kind is None or lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang)}, status=400)
    value = seafloor.at(kind, lon, lat)
    if value is None:
        text = i18n.t(msg("여기는 바다 지각이 아니거나 값이 없다"), lang)
    elif kind == "age":
        text = i18n.t(msg("약 {ma} Ma — Seton 외 2020, 해령에서 굳은 때", ma=f"{value:.1f}"), lang)
    else:
        text = i18n.t(msg("약 {m} m — GlobSed v3, 해저면에서 음향 기반암까지", m=f"{value:,.0f}"), lang)
    return JsonResponse({"value": value, "text": text, "credit": seafloor.KINDS[kind][4]})


#: 온 지구 화면의 레이어 이름 → 판 (wetherilli 272). `plates` 는 판 회전의 조각 경계라 이름을 갈랐다
TECTONIC_LAYERS = {"tbound": "boundaries", "tprov": "provinces"}


@require_GET
def earth_tectonics_tile(request, layer, z, x, y):
    """`earth/tectonics/<tbound|tprov>/<z>/<x>/<y>.png` — Hasterok 2022 판 경계·세계 지질구, 경위도 격자 (`tectonics.render_tile`)"""
    kind, z, x, y = TECTONIC_LAYERS.get(layer), int(z), int(x), int(y)
    if kind is None or not tectonics.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not tectonics.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    version = tectonics_version()
    key = tilecache.key_text("tectonics", f"{kind}/{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = tectonics.render_tile(kind, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_tectonics_at(request):
    """`?lon=&lat=` — 누른 자리의 세계 지질구(Hasterok 2022)"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    got = tectonics.province_at(lon, lat, lang)
    text = "" if got else i18n.t(msg("여기에는 지질구가 없다"), lang)
    return JsonResponse({"province": got, "text": text, "credit": tectonics.CITE})


@require_GET
def earth_glim_tile(request, z, x, y):
    """`earth/glim/tiles/<z>/<x>/<y>.png` — GLiM 세계 암상 0.5° 격자, 경위도 격자 (`glim.render_tile`, wetherilli 267)"""
    z, x, y = int(z), int(x), int(y)
    if not glim.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if glim.grid() is None:
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    version = glim_version()
    key = tilecache.key_text("glim", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = glim.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_glim_at(request):
    """`?lon=&lat=` — 누른 자리 0.5° 칸의 가장 넓은 암상"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    code = glim.at(lon, lat)
    text = (i18n.t(msg("{name} — GLiM, 0.5° 칸에서 가장 넓은 암상", name=glim.name(code, lang)), lang) if code is not None
            else i18n.t(msg("이 칸에는 값이 없다"), lang))
    return JsonResponse({"code": code, "text": text, "credit": glim.CITE})


@require_GET
def earth_heatflow_tile(request, z, x, y):
    """`earth/heatflow/tiles/<z>/<x>/<y>.png` — IHFC 지열류 점 (`heatflow.render_tile`, wetherilli 267). 오늘의 레이어다"""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not heatflow.available():
        return _tile(tiles.blank_tile(), store=False)
    version = heatflow_version()
    key = tilecache.key_text("heatflow", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = heatflow.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_heatflow_at(request):
    """`?lon=&lat=&r=` — 누른 자리 둘레(`r`°)의 지열류 측정, 가까운 것부터 다섯"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    out = []
    for h in heatflow.near(lon, lat, r):
        q = f"{h['q']:g}" + (f" ± {h['q_unc']:g}" if h["q_unc"] is not None else "")
        rows = [("지열류 (mW/m²)", q), ("이름", h["name"]), ("환경", h["environment"]), ("측정법", h["method"]),
                ("표고 (m)", f"{h['elevation']:g}" if h["elevation"] is not None else ""), ("연도", h["year"]),
                ("품질", h["quality"]), ("참고 문헌", h["reference"])]
        rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
        out.append({"id": h["id"], "name": i18n.t(msg("지열류 {q} mW/m²", q=f"{h['q']:g}"), lang), "rows": rows,
                    "at": [h["lon"], h["lat"]]})
    return JsonResponse({"hits": out, "credit": heatflow.CREDIT, "link": heatflow.DOI})


@require_GET
def earth_stress_tile(request, z, x, y):
    """`earth/stress/tiles/<z>/<x>/<y>.png` — World Stress Map 2025 의 S_Hmax 막대 (`stress.render_tile`, wetherilli 273)"""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not stress.available():
        return _tile(tiles.blank_tile(), store=False)
    version = stress_version()
    key = tilecache.key_text("stress", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = stress.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_stress_at(request):
    """`?lon=&lat=&r=` — 누른 자리 둘레(`r`°)의 응력 측정, 가까운 것부터 다섯"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    out = []
    for s in stress.near(lon, lat, r):
        regime = stress.REGIMES.get(s["regime"], stress.REGIMES["U"])[1]
        kind = stress.TYPES.get(s["type"])
        rows = [("최대 수평 응력 방향", f"N{s['azi']:.0f}°E"), ("응력 체제", i18n.t(regime, lang)), ("품질", s["quality"]),
                ("측정법", i18n.t(kind, lang) if kind else s["type"]), ("깊이 (km)", f"{s['depth']:g}" if s["depth"] is not None else ""),
                ("곳", " · ".join(x for x in (s["locality"], s["country"]) if x)), ("규모", s["mag"]), ("일시", s["date"]),
                ("참고 문헌", s["ref"])]
        rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
        out.append({"id": s["id"], "name": i18n.t(msg("응력 N{azi}°E", azi=f"{s['azi']:.0f}"), lang), "rows": rows,
                    "at": [s["lon"], s["lat"]], "color": "#%02x%02x%02x" % stress.colour(s["regime"])})
    return JsonResponse({"hits": out, "credit": stress.CREDIT, "link": stress.DOI})


@require_GET
def earth_minerals_tile(request, band, z, x, y):
    """`earth/minerals/tiles/<칸>/<z>/<x>/<y>.png` — USGS 세계 광상, 광종 칸 하나(`minerals.BANDS`) (wetherilli 276)"""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y) or band not in minerals.BANDS:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not minerals.available():
        return _tile(tiles.blank_tile(), store=False)
    version = minerals_version()
    key = tilecache.key_text("minerals", f"{version}/{band}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = minerals.render_tile(band, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_minerals_at(request):
    """`?lon=&lat=&r=&bands=min_cu,min_au` — 누른 자리 둘레(`r`°)의 광상, 켠 칸에서 무겁고 가까운 것부터 다섯"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    bands = [b for b in (request.GET.get("bands") or "").split(",") if b in minerals.BANDS]
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    out = []
    for d in minerals.near(bands, lon, lat, r):
        rows = []
        for key, value in json.loads(d["rows"]):
            if key in minerals.TRANSLATED:
                value = i18n.t(msg(value), lang)
            rows.append([i18n.PROP_EN.get(key, key) if lang == "en" else key, value])
        out.append({"name": d["name"] or i18n.t(msg("이름 없는 곳"), lang), "rows": rows, "at": [d["lon"], d["lat"]],
                    "color": minerals.BANDS[d["band"]][0], "link": d["url"], "table": d["src"] != "mrds"})
    return JsonResponse({"hits": out, "credit": minerals.CREDIT})


@require_GET
def earth_faults_tile(request, z, x, y):
    """`earth/faults/tiles/<z>/<x>/<y>.png` — GEM 세계 활성단층, 경위도 격자 (`faults.render_tile`, wetherilli 279)"""
    z, x, y = int(z), int(x), int(y)
    if not faults.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not faults.available():
        return _tile(tiles.blank_tile(), store=False)
    version = faults_version()
    key = tilecache.key_text("faults", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = faults.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_faults_at(request):
    """`?lon=&lat=&z=` — 누른 자리 둘레(그 줌의 8 화소)의 가장 가까운 활성단층"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    z = _float(request.GET.get("z"))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    r = min(2.0, max(0.002, 180.0 / 2 ** max(0, min(18, z if z is not None else 3)) / 256 * 8))
    got = faults.near(lon, lat, r, lang)
    return JsonResponse({"fault": got, "text": "" if got else i18n.t(msg("여기에는 활성단층이 없다"), lang), "credit": faults.CITE})


@require_GET
def earth_impacts_tile(request, layer, ma, z, x, y):
    """`earth/impacts/<impacts|lips>/<Ma>/<z>/<x>/<y>.png` — 충돌구(오늘만)·거대 화성암 지대(그 연대의 자리로) (wetherilli 283)"""
    ma, z, x, y = int(ma), int(z), int(x), int(y)
    if layer not in ("impacts", "lips") or not impacts.valid_tile(z, x, y) or ma > 1100 or (layer == "impacts" and ma):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not impacts.available():
        return _tile(tiles.blank_tile(), store=False)
    version = impacts_version()
    key = tilecache.key_text("impacts", f"{version}/{layer}/{ma}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = impacts.render_tile(layer, float(ma), z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_impacts_at(request):
    """`?lon=&lat=&z=&layer=impacts|lips` — 누른 자리의 충돌구(그 줌의 8 화소 또는 충돌구 둘레 안)·거대 화성암 지대(오늘의 자리)"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    z = _float(request.GET.get("z"))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    rows, name = [], ""
    if request.GET.get("layer") == "lips":
        lip = impacts.lip_at(lon, lat)
        if lip:
            name = lip["name"] or i18n.t(msg("이름 없는 화성암 지대"), lang)
            rows = [("생긴 때 (Ma)", f"{lip['ma']:g}"), ("지질시대", i18n.t(impacts.period_of(lip["ma"])[2], lang)),
                    ("그때의 지구", i18n.t(msg("판 회전으로 옮긴다"), lang) if lip["pid"] is not None else i18n.t(msg("바다 밑이라 옮기지 않는다"), lang))]
        credit = impacts.CITE_LIPS
    else:
        r = min(2.0, max(0.002, 180.0 / 2 ** max(0, min(18, z if z is not None else 3)) / 256 * 8))
        hit = impacts.impact_near(lon, lat, r)
        if hit:
            name = hit["name"] or hit["id"]
            rows = [("지름 (km)", f"{hit['km']:g}" if hit["km"] else ""), ("생긴 때 (Ma)", f"{hit['ma']:g}" if hit["ma"] else ""),
                    ("나라", hit["country"]), ("Wikidata", hit["id"])]
        credit = impacts.CITE_IMPACTS
    rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
    text = "" if name else i18n.t(msg("여기에는 없다"), lang)
    return JsonResponse({"name": name, "rows": rows, "text": text, "credit": credit})


@require_GET
def earth_glaciers_tile(request, z, x, y):
    """`earth/glaciers/tiles/<z>/<x>/<y>.png` — RGI 7.0 빙하, 넓이만 한 점 (`glaciers.render_tile`, wetherilli 289). 줌 3 밑은 빈 타일"""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not glaciers.available():
        return _tile(tiles.blank_tile(), store=False)
    version = glaciers_version()
    key = tilecache.key_text("glaciers", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = glaciers.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_glaciers_at(request):
    """`?lon=&lat=&z=` — 누른 자리의 빙하(넓이의 원 안, 또는 그 줌의 8 화소 안)"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    z = _float(request.GET.get("z"))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    r = min(1.0, max(0.002, 180.0 / 2 ** max(0, min(18, z if z is not None else 3)) / 256 * 8))
    out = []
    for g in glaciers.near(lon, lat, r):
        span = f"{g['zmin']:.0f}–{g['zmax']:.0f}" if g["zmin"] is not None and g["zmax"] is not None else ""
        rows = [("넓이 (km²)", f"{g['area']:,.2f}"), ("높이 (m)", span), ("가운데 높이 (m)", f"{g['zmed']:.0f}" if g["zmed"] is not None else ""),
                ("경사 (°)", f"{g['slope']:.1f}" if g["slope"] is not None else ""),
                ("끝", i18n.t(glaciers.TERMINUS[1][1], lang) if g["term"] == 1 else ""),
                ("서지", i18n.t(glaciers.SURGE[g["surge"]], lang) if g["surge"] in glaciers.SURGE else ""),
                ("윤곽의 날", g["date"]), ("RGI", g["id"])]
        out.append({"name": g["name"].rstrip(",") or i18n.t(msg("이름 없는 빙하"), lang),
                    "rows": [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]})
    return JsonResponse({"hits": out, "text": "" if out else i18n.t(msg("여기에는 빙하가 없다"), lang), "credit": glaciers.CREDIT})


@require_GET
def earth_crust_at(request):
    """`?lon=&lat=` — 누른 자리의 지각 두께. 모형이지 관측이 아니다."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    km = crust.at(lon, lat)
    text = (i18n.t(msg("약 {km} km — CRUST 2.0, 2° 칸의 모형이다", km=f"{km:.0f}"), lang) if km is not None
            else i18n.t(msg("이 칸에는 값이 없다"), lang))
    return JsonResponse({"km": km, "text": text, "credit": crust.CITE})


# ── 화석 산지 (wetherilli 098) ───────────────────────────────────────

@require_GET
def earth_fossil_density_tile(request, ka, z, x, y):
    """`earth/fossils/density/<ka>/<z>/<x>/<y>.png` — 그 연대의 화석 산지 밀도(1° 칸, 로그) (wetherilli 286). 연대는 점 레이어와 같은 ka.
    고르기도 점 레이어와 같다 — 1 Ma 부터는 그때의 자리로 옮긴 산지를 센다"""
    z, x, y, ka = int(z), int(x), int(y), int(ka)
    if not fossils.density_valid(z, x, y) or ka > 1100000:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if fossils.db() is None:
        return _tile(tiles.blank_tile(), store=False)
    age = ka / 1000.0
    if age >= fossils.PALEO_FROM:
        age = float(round(age))
    version = fossils_version() + fossils.DENSITY_RENDERER
    key = tilecache.key_text("pbdb-density", f"{version}/{age:g}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = fossils.render_density(age, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_fossil_tile(request, ka, z, x, y):
    """`earth/fossils/tiles/<ka>/<z>/<x>/<y>.png` — 그 연대의 화석 산지(PBDB). 연대는 천 년(ka) 단위의 정수다 —
    0 은 오늘(모든 산지), 1 Ma 안쪽은 그 연대를 품은 산지를 오늘의 자리에, 1 Ma 부터는 그때의 자리에(`fossils.py`)."""
    z, x, y, ka = int(z), int(x), int(y), int(ka)
    if not paleo.valid_tile(z, x, y) or ka > 1100000:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    conn = fossils.db()
    if conn is None:
        return _tile(tiles.blank_tile(), store=False)
    age = ka / 1000.0
    if age >= fossils.PALEO_FROM:
        age = float(round(age))
    # 다시 구운 날과 파일의 판이 열쇠에 든다 — 산지가 늘면 새로 그리고 주소도 바뀐다 (wetherilli 183)
    version = fossils_version()
    key = tilecache.key_text("pbdb", f"{version}/{age:g}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = fossils.render_tile(age, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_fossil_at(request):
    """`?lon=&lat=&age=&r=` — 누른 자리 둘레(`r`°)의 화석 산지, 가까운 것부터 다섯. `lon`·`lat` 은 화면에 찍힌 자리다 —
    1 Ma 부터는 그때의 자리."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    age, r = _float(request.GET.get("age")) or 0.0, min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    if age >= fossils.PALEO_FROM:
        age = float(round(age))
    m = paleo.model()
    out = []
    for row, (plon, plat) in fossils.near(age, lon, lat, r):
        span = row["early"] + (f" – {row['late']}" if row["late"] and row["late"] != row["early"] else "")
        mid = (row["max_ma"] + row["min_ma"]) / 2
        rows = [("산지", row["name"]), ("지층", row["formation"]),
                ("시대", i18n.age_ko(span) if lang == "ko" else span),
                ("연대 (Ma)", _age_span(row["max_ma"], row["min_ma"])), ("퇴적 환경", row["env"]),
                ("화석 수", str(row["n_occs"]) if row["n_occs"] else ""), ("나라", row["cc"])]
        # 옛 자리 — 우리 셈(판 조각과 같다)과 PBDB 의 셈, 둘 다 산지 연대의 가운데에서
        then = []
        if m is not None and row["pid"] is not None:
            got = m.carry(row["lon"], row["lat"], mid, {"pid": row["pid"], "lon": row["flon"], "lat": row["flat"],
                                                          "reach": row["reach"]})
            then.append([i18n.t(msg("그때의 자리 ({age} Ma)", age=f"{mid:g}"), lang), _paleo_text(got, lang)])
        if row["pb_lon"] is not None:
            then.append([i18n.t(msg("PBDB 의 옛 자리"), lang), _lonlat_text(row["pb_lon"], row["pb_lat"], lang)])
        rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v] + then
        if row["ref"]:
            rows.append([i18n.PROP_EN.get("첫 문헌", "첫 문헌") if lang == "en" else "첫 문헌", row["ref"]])
        out.append({"no": row["no"], "name": row["name"], "rows": rows, "link": pbdb.collection_url(row["no"]),
                    "today": [row["lon"], row["lat"]], "at": [plon, plat], "mid": mid})
    return JsonResponse({"hits": out, "credit": pbdb.CREDIT})


# ── 홀로세 화산 (wetherilli 134) ─────────────────────────────────────

@require_GET
def earth_volcano_tile(request, z, x, y, kind="holocene"):
    """`earth/volcanoes/tiles/<z>/<x>/<y>.png` — GVP 의 홀로세 화산. 오늘의 레이어라 연대가 없다(`volcanoes.py`).
    `earth/volcanoes/pleistocene/tiles/…` 는 플라이스토세 화산이다 (wetherilli 194)."""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not volcanoes.available(kind):
        return _tile(tiles.blank_tile(), store=False)
    # 다시 받은 날과 파일의 판이 열쇠에 든다 — 판이 오르면 새로 그리고 주소도 바뀐다
    version = volcanoes_version(kind)
    key = tilecache.key_text("gvp", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = volcanoes.render_tile(z, x, y, kind)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_volcano_at(request):
    """`?lon=&lat=&r=&kinds=holocene,pleistocene` — 누른 자리 둘레(`r`°)의 화산, 켠 갈래에서 가까운 것부터 다섯."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    kinds = [k for k in (request.GET.get("kinds") or "holocene").split(",") if k in volcanoes.FILES]
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    out = []
    for v in volcanoes.near(lon, lat, r, kinds=kinds):
        last = volcanoes.year_text(v.get("last"))
        epoch = i18n.t(msg("플라이스토세"), lang) if v["kind"] == "pleistocene" else ""
        rows = [("화산", v["name"]), ("시대", epoch), ("화산 종류", v["type"]),
                ("마지막 분화", i18n.t(last, lang) if last else ""),
                ("근거", v.get("evidence")), ("나라", v["country"]), ("지역", v["subregion"]),
                ("표고 (m)", f"{v['elev']:,}" if v.get("elev") is not None else ""), ("지구조 환경", v.get("tectonic")),
                ("주 암석", v.get("rock")), ("지질 개요", v["summary"])]
        rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, str(val)] for k, val in rows if val]
        out.append({"no": v["no"], "name": v["name"], "rows": rows, "link": gvp.volcano_url(v["no"]),
                    "at": [v["lon"], v["lat"]]})
    return JsonResponse({"hits": out, "credit": gvp.CREDIT})


# ── 지진 (wetherilli 138) ───────────────────────────────────────────

@require_GET
def earth_quake_tile(request, band, z, x, y):
    """`earth/quakes/tiles/<칸>/<z>/<x>/<y>.png` — USGS 의 지진, 규모 칸 하나(`quakes.BANDS`). 오늘의 레이어다."""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y) or band not in quakes.BANDS:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not quakes.available():
        return _tile(tiles.blank_tile(), store=False)
    # 다시 구운 날과 파일의 판이 열쇠에 든다 — 새 지진이 쌓이면 새로 그리고 주소도 바뀐다
    version = quakes_version()
    key = tilecache.key_text("usgs", f"{version}/{band}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = quakes.render_tile(band, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_quake_at(request):
    """`?lon=&lat=&r=&bands=quake6,quake55` — 누른 자리 둘레(`r`°)의 지진, 켠 규모 칸에서 가까운 것부터 다섯."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    bands = [b for b in (request.GET.get("bands") or "").split(",") if b in quakes.BANDS]
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    out = []
    for q in quakes.near(bands, lon, lat, r):
        when = q["time"].replace("T", " ")[:16]
        rows = [("규모", f"{q['mag']:g} {q['mag_type']}".strip()), ("일시 (UTC)", when),
                ("깊이 (km)", f"{q['depth']:g}" if q["depth"] is not None else ""), ("곳", q["place"])]
        rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
        out.append({"id": q["id"], "name": i18n.t(msg("M{mag} 지진", mag=f"{q['mag']:g}"), lang), "rows": rows,
                    "link": usgs.event_url(q["id"]), "at": [q["lon"], q["lat"]]})
    return JsonResponse({"hits": out, "credit": usgs.CREDIT})


# ── 최근 지진 (wetherilli 292) ─────────────────────────────────────

@require_GET
def earth_recent_quake_tile(request, z, x, y):
    """`earth/recentquakes/tiles/<z>/<x>/<y>.png` — USGS 실시간 피드의 지난 7 일 M2.5 이상. 속이 빈 고리, 지난 시간의 색"""
    z, x, y = int(z), int(x), int(y)
    if not paleo.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not recentquakes.available():
        return _tile(tiles.blank_tile(), store=False)
    version = recentquakes_version()
    key = tilecache.key_text("usgs-recent", f"{version}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = recentquakes.render_tile(z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_recent_quake_at(request):
    """`?lon=&lat=&r=` — 누른 자리 둘레의 최근 지진, 가까운 것부터 다섯. 꼴은 `earth_quake_at` 과 같다"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    out = []
    for q in recentquakes.near(lon, lat, r):
        rows = [("규모", f"{q['mag']:g} {q['mag_type']}".strip()), ("일시 (UTC)", recentquakes.when(q["ms"])),
                ("깊이 (km)", f"{q['depth']:g}" if q["depth"] is not None else ""), ("곳", q["place"])]
        rows = [[i18n.PROP_EN.get(k, k) if lang == "en" else k, v] for k, v in rows if v]
        out.append({"id": q["id"], "name": i18n.t(msg("M{mag} 최근 지진", mag=f"{q['mag']:g}"), lang), "rows": rows,
                    "link": usgs.event_url(q["id"]), "at": [q["lon"], q["lat"]]})
    return JsonResponse({"hits": out, "credit": usgs.CREDIT})


# ── 제4기 고생태 산지 (wetherilli 139) ───────────────────────────────

@require_GET
def earth_neotoma_tile(request, band, ka, z, x, y):
    """`earth/neotoma/tiles/<칸>/<ka>/<z>/<x>/<y>.png` — Neotoma 의 산지, 자료형 칸 하나(`paleoeco.BANDS`). 0 은 모든 산지,
    1 Ma 안쪽은 그 연대를 품은 자료가 있는 산지만. 1 Ma 부터는 화면이 끈다."""
    z, x, y, ka = int(z), int(x), int(y), int(ka)
    if not paleo.valid_tile(z, x, y) or band not in paleoeco.BANDS or ka >= 1000:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not paleoeco.available():
        return _tile(tiles.blank_tile(), store=False)
    version = neotoma_version()
    key = tilecache.key_text("neotoma", f"{version}/{band}/{ka}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), version)
    png = paleoeco.render_tile(band, ka / 1000.0, z, x, y)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return _immutable(request, response, version)


@require_GET
def earth_neotoma_at(request):
    """`?lon=&lat=&age=&r=&bands=neo_pollen,…` — 누른 자리 둘레(`r`°)의 산지, 켠 칸에서 가까운 것부터 다섯.
    산지마다 그 연대·칸의 자료를 자료형과 연대 범위로 적는다."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    age = max(0.0, min(0.999, _float(request.GET.get("age")) or 0.0))
    r = min(5.0, max(0.001, _float(request.GET.get("r")) or 0.1))
    bands = [b for b in (request.GET.get("bands") or "").split(",") if b in paleoeco.BANDS]
    if lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)

    def label(k):
        return i18n.PROP_EN.get(k, k) if lang == "en" else k
    out = []
    for site, datasets in paleoeco.near(bands, age, lon, lat, r):
        rows = [[label(k), str(v)] for k, v in (("산지", site["name"]), ("설명", site["desc"]),
                                                ("표고 (m)", f"{site['alt']:g}" if site["alt"] is not None else "")) if v]
        # 자료마다 한 줄 — 자료형(속성 값이라 옮기지 않는다)과 연대 범위·구성 DB
        shown = datasets[:8]
        for d in shown:
            rows.append([d["type"], " · ".join(v for v in (paleoeco.span_text(d["old"], d["young"]), d["db"]) if v)])
        if len(datasets) > len(shown):
            rows.append(["…", i18n.t(msg("자료 {n} 건 더", n=len(datasets) - len(shown)), lang)])
        pis = []
        for d in datasets:
            for name in (d["pi"] or "").split("; "):
                if name and name not in pis:
                    pis.append(name)
        if pis:
            rows.append([label("연구자"), "; ".join(pis[:6])])
        doi = next((d["doi"] for d in datasets if d["doi"]), "")
        if doi:
            rows.append([label("DOI"), doi])
        out.append({"site": site["site"], "name": site["name"], "rows": rows, "link": neotoma.site_url(site["site"]),
                    "at": [site["lon"], site["lat"]]})
    return JsonResponse({"hits": out, "credit": neotoma.CREDIT})


def _age_span(oldest, youngest) -> str:
    if oldest is None:
        return ""
    if youngest is None or youngest == oldest:
        return f"{oldest:g}"
    return f"{oldest:g} – {youngest:g}"


@require_GET
@browser_cached
def earth_legend(request):
    """온 지구 지질도의 범례 — 기(period)의 색 (`macrostrat.legend`). 한 번 받아 담는다."""
    lang = i18n.lang_of(request)
    key = tilecache.key_text("macrostrat-legend", f"periods/{lang}")
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = macrostrat.legend(lang)
        except macrostrat.MacrostratError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("Macrostrat 범례를 받지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse({"rows": rows})


# ── 카탈로그 ──────────────────────────────────────────────────────────

#: 연구실 안에서만 보는 상류. 밖에 열면(`settings.PUBLIC`) 목록에서 빠지고 길도
#: 닫힌다. 레이어 이름이 `<상류>:…` 꼴이라 이름만 보고 가른다.
#: 극지연구소(`kopri`)는 KPDC 공개 자료라 싣는다 — 사용자가 정했다(2026-10-02, wetherilli P11)
LAB_ONLY = ("geo3al", "phyloserver", "peninsula")


def _lab_only(name: str) -> bool:
    return settings.PUBLIC and str(name).split(":", 1)[0] in LAB_ONLY


def _options_3d(layers: list):
    """3D 의 레이어 고르개 `<option>` 들(wetherilli 271). 템플릿 루프와 한 글자까지 같은 것을 파이썬이 짓는다 — 레이어가 오백을 넘어
    템플릿이 `{% if %}` 를 오천 번 남짓 돌리는 데 이 화면 시간의 절반이 들었다. 이스케이프는 템플릿과 같은 `conditional_escape`"""
    from django.utils.html import conditional_escape as esc
    from django.utils.safestring import mark_safe
    out = []
    for l in layers:
        attrs = f' data-upstream="{esc(l.get("upstream"))}"'
        for key, data in (("attribution", "attribution"), ("tiles", "tiles"), ("minZoom", "min"), ("maxZoom", "max"),
                          ("lastZoom", "last")):
            if l.get(key):
                attrs += f' data-{data}="{esc(l[key])}"'
        if l.get("bbox"):
            attrs += f' data-bbox="{esc(",".join(str(v) for v in l["bbox"]))}"'
        out.append(f'<option value="{esc(l["name"])}"{attrs}>{esc(l["title"])}</option>')
    return mark_safe("".join(out))


_HANGUL = re.compile(r"[가-힣]")


def _abstract_en(layer) -> str:
    """영어판의 레이어 설명 — `i18n.ABSTRACT_EN` 의 것, 없으면 한국어가 들지 않은 설명만 그대로(원어 제목뿐인 설명). 한국어가 든 설명은 숨긴다 (wetherilli 333)"""
    text = i18n.ABSTRACT_EN.get(layer.name)
    if text:
        return text
    return "" if not layer.abstract or _HANGUL.search(layer.abstract) else layer.abstract


def _catalog(lang="ko"):
    """레이어 패널의 목록. 영어판이면 제목만 `i18n.LAYER_EN` 으로 바꾼다."""
    en = lang == "en"
    groups = []
    # 켠 레이어만 한 번에 받아 둔다(wetherilli 271) — 예전에는 `prefetch_related("layers")` 뒤에 레이어군마다 `.filter(enabled=True)` 를
    # 다시 불러 미리 받은 것을 버리고 레이어군 수(160)만큼 물었다. 차례는 Layer 의 기본 차례(레이어군 안에서 order·title) 그대로다
    enabled = Prefetch("layers", queryset=Layer.objects.filter(enabled=True), to_attr="enabled_layers")
    for group in LayerGroup.objects.prefetch_related(enabled).all():
        layers = [{
            "name": l.name,
            "title": i18n.LAYER_EN.get(l.name, l.title) if en else l.title,
            # 다른 말의 제목 — 레이어 찾기 칸이 한국어로도 영어로도 찾게 (wetherilli 332)
            **({"alt": alt} if (alt := (l.title if en else i18n.LAYER_EN.get(l.name, ""))) and alt != (
                i18n.LAYER_EN.get(l.name, l.title) if en else l.title) else {}),
            "bbox": l.bbox,
            "queryable": l.queryable,
            # 대조할 상류가 없는 것(우리가 그리는 GeoMAP)은 "대조 안 함" 표를 달지 않는다
            "verified": bool(l.verified_at) or l.upstream in ("geomap", "janmayen", "geo3al", "peninsula", "kopri", "usgscarib", "stri", "sim3534", "vmme")
                        or twopen.knows(l.name),
            # 영어판은 설명의 영어(`i18n.ABSTRACT_EN`, wetherilli 333) — 없으면 한국어가 든 설명을 숨긴다
            "abstract": _abstract_en(l) if en else l.abstract,
            # 어느 상류인지 — 화면이 출처(`attributions`)를 붙인다. vector 면
            # 타일이 아니라 모양을 받아 그린다 (`map.js` 의 `vectorLayerFor`)
            "upstream": l.upstream,
            "kind": l.kind,
            **({"cell": vector_grid(l.name)["cell"],
                **({"minZoom": vector_grid(l.name)["minZoom"]} if vector_grid(l.name)["minZoom"] else {})}
               if l.kind == "vector" else {}),
            **_point_fields(l),
            **_layer_extra(l, lang),
        } for l in group.enabled_layers
            # VWorld 열쇠가 없으면 "지질 참고" 는 그릴 길이 없다 — 목록에서 뺀다
            if (l.upstream != "vworld" or vworld.enabled()) and not _lab_only(l.name)]
        if layers:
            name = i18n.GROUP_EN.get(group.name, group.name) if en else group.name
            groups.append({"name": name, "region": group.region, "layers": layers})
    return groups


def _point_fields(layer) -> dict:
    """점을 통째로 받아 브라우저가 그리는 레이어(`grportal`·`npolar` 의 점)에만 붙는 것.

    타일이 아니므로 `/wms/`·`/featureinfo/`·`/legend/` 를 부르지 않는다 —
    `queryable` 을 끄고, 받을 곳과 출처를 따로 적는다 (devlog 019·021).
    """
    if layer.upstream == "janmayen" and janmayen.knows(layer.name):
        # 얀마옌 지질도(022) — 점 말고 선·면도 이 길로 간다. 색은 자료가 준다
        return {"kind": "points", "queryable": False, "style": janmayen.LAYERS[layer.name]["style"],
                "source": janmayen.SOURCE_URL, "attribution": janmayen.ATTRIBUTION,
                "opacity": 0.75 if janmayen.LAYERS[layer.name]["style"] == "unit" else 1}
    if layer.upstream == "gsmma" and twopen.knows(layer.name):
        # 대만 지질운 열린자료(wetherilli 305) — 받아 둔 파일을 한 덩이로. 낙석·암체 등급은 면이 수천이라 구워 그린다
        style = twopen.LAYERS[layer.name]["style"]
        return {"kind": "points", "queryable": False, "style": style, "render": "image",
                "source": twopen.SOURCE_URL, "attribution": twopen.ATTRIBUTION, "opacity": 0.75 if style == "unit" else 1}
    if layer.upstream == "stri" and stri.knows(layer.name):
        # 파나마 STRI(wetherilli 253) — 카리브와 같은 꼴, 면과 단층을 한 덩이씩
        return {"kind": "points", "queryable": False, "style": "unit" if layer.name == stri.GEOLOGY else "line",
                "render": "image", "source": stri.SOURCE_URL, "attribution": stri.ATTRIBUTION,
                "opacity": 0.75 if layer.name == stri.GEOLOGY else 1}
    if layer.upstream == "usgscarib" and usgscarib.knows(layer.name):
        # USGS 카리브 지질도(wetherilli 248) — 피처 서비스라 면(6 343)을 한 덩이로 받아 화면이 구워 그린다(geo3al 과 같은 꼴)
        sa = layer.name == usgscarib.SA_NAME                  # 남미(wetherilli 256)도 같은 문
        return {"kind": "points", "queryable": False, "style": "unit", "render": "image",
                "source": usgscarib.SA_SOURCE_URL if sa else usgscarib.SOURCE_URL,
                "attribution": usgscarib.SA_ATTRIBUTION if sa else usgscarib.ATTRIBUTION, "opacity": 0.75}
    if layer.upstream == "ags" and ags.knows_points(layer.name):
        # 앨버타 광물 산지(wetherilli 321) — 피처 서비스 5 454 점을 한 덩이로, 갈래(금속·산업 광물·리튬·규사·생산자·코어)마다 색
        return {"kind": "points", "queryable": False, "style": "class",
                "source": ags.OCC_SOURCE_URL, "attribution": ags.OCC_ATTRIBUTION}
    if layer.upstream == "vmme" and vmme.knows(layer.name):
        # 파라과이 VMME(wetherilli 256) — 카리브와 같은 꼴, 면 61 을 한 덩이로
        return {"kind": "points", "queryable": False, "style": "unit", "render": "image",
                "source": vmme.SOURCE_URL, "attribution": vmme.ATTRIBUTION, "opacity": 0.75}
    if layer.upstream == "geo3al" and geo3al.knows(layer.name):
        # 중국 지질도(USGS geo3al, 025) — 얀마옌처럼 면을 한 덩이로. 면이 1 만 2 천이라
        # 화면이 한 장으로 구워 그린다(`render: image`). 이용 조건은 범례 칸이 적는다
        spec = geo3al.LAYERS[layer.name]
        return {"kind": "points", "queryable": False, "style": spec["style"], "render": "image",
                "source": geo3al.SOURCE_URL, "attribution": geo3al.ATTRIBUTION,
                "opacity": spec["opacity"], "band": True}
    if layer.upstream == "grportal" and grportal.knows(layer.name):
        spec = {"kind": "points", "queryable": False, "style": grportal.LAYERS[layer.name]["style"],
                "source": grportal.source_url(layer.name), "portal": grportal.WEBMAP,
                # 고른 원소만 받는 레이어 — 전암 화학 (wetherilli 163)
                **({"slice": True} if grportal.LAYERS[layer.name].get("slice") else {})}
        if grportal.license_of(layer.name):
            # 다이아몬드 탐사 자료(DED)는 항목에 CC BY 4.0 이 적혀 있다 (wetherilli 157)
            spec["license"] = grportal.license_of(layer.name)
        return spec
    if layer.upstream == "phyloserver" and phyloserver.knows(layer.name):
        # 연구실의 암맥 기록(026) — 같은 서버의 phyloserver 에서 통째로 받는다
        return {"kind": "points", "queryable": False, "style": phyloserver.LAYERS[layer.name]["style"],
                "source": phyloserver.source_url(layer.name), "attribution": phyloserver.ATTRIBUTION}
    if layer.upstream == "kopri" and kopri.knows(layer.name):
        # 극지연구소(053–056) — 암석 시료·운석·KPDC 자료는 모아 둔 파일에서, 기지는 WFS 에서.
        # 색과 범례는 서버가 한 표(`legend`)로 준다
        spec = {"kind": "points", "queryable": False, "style": "class",
                "source": kopri.source_url(layer.name), "attribution": kopri.ATTRIBUTION}
        if kopri.file_of(layer.name) == "araon":
            # 아라온호 항적 — 고를 기간(날수, 앞의 것이 기본). 화면이 이 안의 조각만 옅어지게 그린다 (koprifossillab 017)
            spec["periods"] = list(kopri.ARAON_PERIODS)
        return spec
    if layer.upstream == "kigam50k" and kigam50k.knows_file(layer.name):
        # 5만 지질도의 화석산지·시료·광산·도폭 틀(wetherilli 199) — 받아 둔 WFS 파일. 색은 서버의 표
        return {"kind": "points", "queryable": False, "style": "class", "source": "https://data.kigam.re.kr/",
                "sourceLabel": str(msg("원본 자료 — KIGAM 5만 수치지질도, CC BY-NC")), "attribution": kigam50k.ATTRIBUTION,
                # 단층 8 263·습곡 — 화면이 한 장으로 굽는다(끌 때 다시 칠하지 않는다, wetherilli 202)
                **({"render": "image"} if layer.name in kigam50k.IMAGE else {})}
    if layer.upstream == "earth" and earthpoints.knows(layer.name):
        # 지구 자료 점(wetherilli 185) — 온 지구 화면의 화석 산지·화산·지진·고생태 산지를 지역의 네모만큼. 색은 서버의 표
        src = earthpoints.source_of(layer.name)
        return {"kind": "points", "queryable": False, "style": "class",
                "source": earthpoints.SOURCE_URLS[src], "sourceLabel": str(earthpoints.SOURCE_LABELS[src]),
                "attribution": earthpoints.CREDITS[src], "version": earthpoints.version(layer.name)}
    if layer.upstream == "npolar" and npolar.knows_points(layer.name):
        return {"kind": "points", "queryable": False, "style": npolar.POINTS[layer.name]["style"],
                "source": npolar.source_url(layer.name), "portal": npolar.DATA_URL,
                "attribution": npolar.ATTRIBUTION, "license": "CC BY 4.0"}
    return {}


def _static_catalog(groups: list) -> list:
    """정적 판(wetherilli P11·162)의 카탈로그 — 정적 판이 실을 지역·상류만. 엮은 KIGAM 레이어(`kigam.COMPOSED`)는
    문서에 없는 GeoServer 를 타므로 뺀다. 무엇을 싣는지는 `settings.STATIC_SITE` 가 정한다(`deploy/static_site.py`)."""
    spec = settings.STATIC_SITE or {}
    regions, upstreams = set(spec.get("regions") or ()), set(spec.get("upstreams") or ())
    # 구워 실은 점 레이어(`bake_static`)는 이름으로 싣는다 — 같은 상류(NPI·극지연구소)에 서버를 타는 지도 레이어가 섞여 있어
    # 상류 하나를 통째로 켤 수 없다 (wetherilli 165)
    baked = set((spec.get("baked") or {}).get("points") or ())
    out = []
    for group in groups:
        if group.get("region") not in regions:
            continue
        layers = [l for l in group["layers"] if (l.get("upstream") in upstreams or l["name"] in baked)
                  and not (l.get("upstream") == "kigam" and l["name"] in kigam.COMPOSED)
                  # VWorld 의 벡터(단층 따위)는 WFS 라 CORS 가 없어 정적 판에서 받을 수 없다 (wetherilli 164)
                  and not (l.get("upstream") == "vworld" and l.get("kind") == "vector")
                  # 극지연구소는 지도 서버(KPDC WMS)만 곧장 부른다 — 모아 둔 파일의 점(시료·운석·KPDC 목록)은 구운 것이 있어야 (wetherilli 161)
                  and not (l.get("upstream") == "kopri" and l["name"] not in kopri.WMS and l["name"] not in baked)
                  # SGC 는 조건이 열린 콜롬비아 1:50만만 — 남미 1:500만(CGMW)은 싣지 않는다 (wetherilli 201)
                  and not (l.get("upstream") == "sgc" and not sgc.static_ok(l["name"]))
                  # `arcwms.Door` 상류(wetherilli 257)는 WMS 로 도는 레이어만 — 지오스피어 1:5만처럼 REST 로 옮기는 것은 곧장 부를 길이 없다
                  and not (l.get("upstream") in static_tables.ARC and l["name"] not in static_tables.arc_layers(l["upstream"]))]
        if layers:
            out.append(dict(group, layers=layers))
    return out


#: 국토지리원 주제 타일 — 레이어 → 지리원 타일의 이름과 줌(2026-10-02 에 줌마다 받아 본 것, wetherilli 172).
#: 그 위 줌은 화면이 늘려 그린다(`maxZoom`), 그 밑은 묻지 않는다(`minZoom`)
GSI_TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/{path}/{{z}}/{{x}}/{{y}}.png"
GSI_TILES = {
    "gsitile:afm": {"path": "afm", "min": 3, "max": 16},
    "gsitile:vlcd": {"path": "vlcd", "min": 5, "max": 16},
}
GSI_ATTRIBUTION = ('<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">'
                   '地理院タイル</a> (国土地理院)')


#: 상류가 축척으로 끄는 레이어의 처음 화면 줌 (wetherilli 310) — 운영 대조(`verify_layers`)에서 넓게 보면 빈 그림이던 것을 Capabilities 의
#: `MaxScaleDenominator` 로 셈했다. 512 px 격자 줌 z 의 축척은 279 541 132 / 2^z(0.28 mm 화소, 지도 단위 그대로)이고 화면 줌은 격자 줌 + 1 이다.
#: 문의 표에 줌이 있으면 거기도 같은 값을 두었다 — 이 표는 문의 값보다 작아지지 않게 하는 바닥이다
SCALE_FLOOR = {
    "bgr:kor250:0+1": 9, "bgr:kor250:2+3+4": 9,                                     # KOR250 1:141만까지(3·4 는 1:71만)
    "bgr:igme5000:43+44": 6, "bgr:igme5000:46+47+48": 5, "bgr:igme5000:51+53+55+57": 6,  # IGME5000 축척별 레이어의 가장 넓은 끝
    "brgm:GITES_PT": 9, "brgm:MINES_PT": 9,                                          # BD Gîtes·광산 1:200만까지
    "ga:faults": 7,                                                                  # 1:250만 단층 1:600만까지
    "gns:NZL_GNS_1M_faults": 9, "gns:NZL_GNS_250K_faults": 10, "gns:NZL_GNS_250K_folds": 12,   # 1:200만·1:100만·1:25만까지
    "lneg:500k:1": 10, "lneg:500k:3": 10, "lneg:500k:4": 10,                        # 구조선·대륙붕 1:94만까지
    "ygs:57": 11,                                                                    # 유콘 MINFILE 1:30만까지
    "bcgs:minfile": 10,                                                              # BC MINFILE 1:100만까지
    "ogs:4": 9, "ogs:5": 9, "ogs:6": 9,                                              # 온타리오 암맥·철층·단층 1:141만까지
    "nsgs:9": 9, "sigeom:failles": 9,                                                # 노바스코샤 단층 1:200만까지, 퀘벡 단층은 재어 정했다
    "mrdata:sgmc2:sgmc2structure": 9,                                                # MapCache 가 격자 줌 8 밑에서 404
    "gsmma:sensitive_landslide": 13,                                                 # 대만 산사태 민감구역 — 가까이서만(축척을 알리지 않는다, 재어 정했다)
}


#: 넓게 보면 한 칸이 10 초를 넘는 레이어의 처음 화면 줌 (wetherilli 313) — 넓이에 따라 느려져 메타타일로 풀리지 않는다.
#: 운영의 걸린 시간(`upstream_stats`, 사흘치)으로 상류를 추리고(p95 8 초 넘는 열넷), 그 레이어 106 개를 범위 한가운데에서 격자 줌을 올려 가며
#: 한 장씩 쟀다(2026-10-05, 1 초 간격·30 초까지). 10 초 안에 온 첫 격자 줌 + 1 이다. 줌마다 잰 초는 devlog 313 의 표
SLOW_FLOOR = {
    "egdi:GeologicUnitView_Age": 5, "egdi:GeologicUnitView_Lithology": 5,          # 격자 3 에서 11–12 초
    "emodnet:cp_wp3_seabed_substrate_folk_7": 4,                                   # 격자 2 에서 30 초 넘게
    "esdm:geology": 6,                                                             # 격자 4 에서 15 초
    "geusarc:g100k_karrat": 7, "geusarc:g100k_ssw": 7,                             # 격자 5 에서 11–14 초
    "gsmma:attitude_50k": 10, "gsmma:discontinuity_50k": 9, "gsmma:landslide_inventory": 8,   # 격자 8·7·6 에서 12–30 초
    "mrdata:sim3340:faults": 5, "mrdata:sim3340:units": 6,                         # 격자 3·4 에서 16–30 초
    "nrcan:lithium": 4, "nrcan:ree": 4,                                            # 격자 2 에서 13–15 초
    "skgs:smdi": 7,                                                                # 격자 5 에서 10.2 초
}


def _layer_extra(layer, lang: str = "ko") -> dict:
    extra = _layer_extra_base(layer, lang)
    floor = max(SCALE_FLOOR.get(layer.name) or 0, SLOW_FLOOR.get(layer.name) or 0) or None
    if floor and (extra.get("minZoom") or 0) < floor:
        extra = dict(extra, minZoom=floor)
    return extra


def _layer_extra_base(layer, lang: str = "ko") -> dict:
    """상류마다 화면에 더 알려야 하는 것. 남극(GeoMAP)은 타일 주소와 출처,
    NPI 는 타일을 받을 투영과 출처 (devlog 021)."""
    if layer.upstream == "geusarc" and geus.arc_knows(layer.name):
        # 그린란드 GEUS ArcGIS(wetherilli 259) — 화면의 투영(3413)으로 REST export. 지질도는 목록 범례(wetherilli 301), 지구물리는 범례가 없다
        legend = ({"legend": "list", "legendUrl": "list/legend/"} if layer.name in geus.LEGEND_LAYERS else {"noLegend": True})
        return {"attribution": geus.ARC_ATTRIBUTION.get(layer.name, geus.GEUS_ATTRIBUTION), "projection": "EPSG:3413", **legend,
                **({} if geus.ARC_LAYERS[layer.name][2] else {"queryable": False})}
    if layer.upstream == "vworld" and layer.name in vworld.MIN_ZOOM:
        # 가까이서만 그려 주는 VWorld 레이어(토양·산림·국가유산, wetherilli 084·193) — 멀리서는 묻지 않는다
        return {"minZoom": vworld.MIN_ZOOM[layer.name]}
    if layer.upstream == "geomap":
        return {"attribution": geomap.ATTRIBUTION,
                # 판을 주소에 넣는다 — 브라우저가 오래 들고 있어도 판이 바뀌면 새 주소다 (wetherilli 151)
                "tiles": _versioned_url(f"geomap/{layer.name}/{{z}}/{{x}}/{{y}}.png", geomap_version()),
                "projection": "EPSG:3031",
                # 높이 그래프 밑에 지질 띠를 그릴 수 있다 (wetherilli 180)
                **({"band": True} if layer.name in geomap.BAND_LAYERS else {})}
    if layer.upstream == "npolar" and npolar.knows(layer.name):
        spec = npolar.TILES[layer.name]
        return {"attribution": npolar.ATTRIBUTION, "projection": spec["projection"],
                **({} if spec["info"] else {"queryable": False})}
    if layer.upstream == "pgc" and elevation.knows_layer(layer.name):
        # PGC 경사·등고선(wetherilli 099) — 지역의 투영으로 곧장 받는다. 범례는 늘인 값뿐이라 싣지 않는다
        spec = elevation.PGC_LAYERS[layer.name]
        return {"attribution": elevation.PGC_ATTRIBUTION, "projection": spec["srs"], "noLegend": True,
                **({"minZoom": spec["min"]} if spec.get("min") else {})}
    if layer.upstream == "kopri" and kopri.knows_wms(layer.name):
        # KPDC 지도 서버(057) — 남극은 3031 을, 북극은 3413 을 그대로 받는다(NPI 와 같다, wetherilli 095)
        return {"attribution": kopri.ATTRIBUTION, "projection": kopri.wms_projection(layer.name)}
    if layer.upstream == "emodnet":
        # EMODnet 해저 지질(wetherilli 135) — GeoServer 가 3413 도 그려 준다. 북극해·스발바르 탭이 그대로 받는다.
        # 유럽 바다의 것(영국에 둔 것, wetherilli 176)은 유럽 탭들의 투영(3857)으로
        projection = "EPSG:3413" if layer.group.region == "arctic_ocean" else "EPSG:3857"
        return {"attribution": emodnet.ATTRIBUTION, "projection": projection}
    if layer.upstream == "ngu":
        # 노르웨이 NGU(wetherilli 140) — 3413 을 그려 주지 않아 북극 람베르트(3575)로 받고 화면이 옮겨 그린다.
        # 광물 서비스는 3575 도 받지 않아 3857 로(wetherilli 326), 지구물리 격자는 누르지 않는다
        return {"attribution": ngu.ATTRIBUTION, "projection": ngu.projection(layer.name),
                **({} if ngu.queryable(layer.name) else {"queryable": False})}
    if layer.upstream in ("esdm", "jmg", "mgb", "dmr"):
        # 동남아(wetherilli 228) — 3857 로 그린다. 인도네시아는 상류가 줌 10 너머를 그리지 않아(`maxZoom` — 그 위는 화면이 늘린다)
        # 범례는 1 403 칸이라 보는 범위의 것이다(wetherilli 243).
        # 말레이시아 암상·태국은 REST 범례를 목록으로(`list/legend/`), 말레이시아 연대는 범례가 없다. 필리핀은 WMS 그림 그대로
        mod = {"esdm": esdm, "jmg": jmg, "mgb": mgb, "dmr": dmr}[layer.upstream]
        if mod.knows(layer.name):
            extra = {"attribution": mod.ATTRIBUTION, "projection": "EPSG:3857"}
            if layer.name in getattr(mod, "LEGEND_LAYERS", ()):
                extra.update({"legend": "list", "legendUrl": "list/legend/"})
            elif mod is jmg:
                extra["noLegend"] = True
            elif mod is esdm and layer.name in esdm.RESOURCES:
                # 인도네시아 광물 잠재력(wetherilli 280) — REST export·identify. 광종이 수십 가지라 범례는 두지 않고 누르면 뜬다
                extra["noLegend"] = True
            elif mod is esdm:
                # 인도네시아 — 보는 범위의 범례(`esdm/legend/`, wetherilli 243). 전체 범례는 1 403 칸이다
                extra.update(legend="extent", legendUrl="esdm/legend/")
            if mod is esdm and layer.name not in esdm.RESOURCES:
                extra["maxZoom"] = esdm.LAST_ZOOM
            return extra
    if layer.upstream == "sgs" and sgs.knows(layer.name):
        # 사우디 SGS(wetherilli 227) — ArcGIS WMS(원본 3857). 범례는 1 337 칸이라 보는 범위의 것(`sgs/legend/`).
        # 광물 산지 MODS·광화대(wetherilli 280)는 다른 서비스의 WMS 이고 범례도 그 그림이다
        if layer.name in sgs.RESOURCES:
            return {"attribution": sgs.ATTRIBUTION, "projection": "EPSG:3857"}
        return {"attribution": sgs.ATTRIBUTION, "projection": "EPSG:3857", "legend": "extent", "legendUrl": "sgs/legend/"}
    if layer.upstream == "gsiindia" and gsiindia.knows(layer.name):
        # 인도 GSI(wetherilli 226) — 그림은 BGS WMS 를 3857 로, 속성은 GSI 피처 서비스(문이 바꾼다). BGS 범례는 번호뿐이라 두지 않는다
        return {"attribution": gsiindia.ATTRIBUTION, "projection": "EPSG:3857", "noLegend": True,
                **({} if layer.name in gsiindia.QUERYABLE else {"queryable": False})}
    if layer.upstream == "mris" and mris.knows(layer.name):
        # 몽골 MonGeoCat(wetherilli 221) — ArcGIS WMS 를 3857 로. 그림 범례는 칸이 255 라 REST 범례를 목록으로(`mris/legend/`)
        legend = ({"legend": "list", "legendUrl": "mris/legend/"} if layer.name in mris.LEGEND_LAYERS
                  else {"noLegend": True})
        return {"attribution": mris.ATTRIBUTION, "projection": "EPSG:3857", **legend,
                **({} if layer.name in mris.QUERYABLE else {"queryable": False})}
    if layer.upstream == "gns" and gns.knows(layer.name):
        # 뉴질랜드·남빅토리아랜드 GNS(wetherilli 218) — 뉴질랜드는 3857, 남극은 3031 로 곧장. QMAP 합본은 넓게 보면 느려 줌 7 부터
        spec = gns.LAYERS[layer.name]
        return {"attribution": gns.ATTRIBUTION, "projection": spec["crs"],
                **({"minZoom": spec["min"]} if spec.get("min") else {}),
                **({} if gns.queryable(layer.name) else {"queryable": False}),
                **({"noLegend": True} if layer.name in gns.NO_LEGEND else {})}
    if layer.upstream == "sgu" and sgu.knows(layer.name):
        # 스웨덴 SGU(wetherilli 213) — GeoServer 가 3413 도 그려 준다. 레이어 하나가 1:100만·5만 판을 함께 부른다
        return {"attribution": sgu.ATTRIBUTION, "projection": "EPSG:3413",
                **({"minZoom": sgu.MIN_ZOOM[layer.name]} if layer.name in sgu.MIN_ZOOM else {}),
                **({} if layer.name in sgu.QUERYABLE else {"queryable": False})}
    if layer.upstream == "natt" and natt.knows(layer.name):
        # 아이슬란드 NÍ(wetherilli 216) — GeoServer 가 3413 으로 다시 그려 준다. 선·점 레이어는 속성이 부호뿐이라 누르지 않는다
        return {"attribution": natt.ATTRIBUTION, "projection": "EPSG:3413",
                **({} if natt.queryable(layer.name) else {"queryable": False})}
    if layer.upstream == "gtk":
        # 핀란드 GTK(wetherilli 140) — ArcGIS 가 3413 도 그려 준다
        return {"attribution": gtk.ATTRIBUTION, "projection": "EPSG:3413",
                **({"queryable": False} if layer.name in gtk.NOT_QUERYABLE else {})}
    if layer.upstream == "bgsgi" and bgs.geoindex_knows(layer.name):
        # 영국 GeoIndex(wetherilli 258) — 3857 로. 지구물리는 줌 9 까지(상류 1:62만 5천), 광산은 줌 10 부터. 범례는 상류 그림
        first, last = bgs.GEOINDEX_ZOOMS.get(layer.name, (None, None))
        return {"attribution": bgs.GEOINDEX_ATTRIBUTION, "projection": "EPSG:3857",
                **({"minZoom": first} if first else {}), **({"lastZoom": last} if last else {}),
                # 지구물리의 범례 그림은 "RGB 밴드" 세 줄뿐이라 두지 않는다. CMIC 원소 지도(wetherilli 324)는 REST 범례를 목록으로
                **({"legend": "list", "legendUrl": "list/legend/"} if layer.name in bgs.LEGEND_LAYERS else {}),
                **({} if bgs.geoindex_queryable(layer.name) else {"queryable": False, "noLegend": True})}
    if layer.upstream == "bgs":
        # 영국 BGS(wetherilli 143) — 1:5만은 줌 13 부터만 그린다. 그보다 멀면 화면이 묻지 않는다
        return {"attribution": bgs.ATTRIBUTION, "projection": "EPSG:3857", "minZoom": bgs.MIN_ZOOM}
    if layer.upstream == "brgm":
        # 프랑스 BRGM(wetherilli 143) — 판마다 그리는 줌이 좁다. 스캔은 누를 것이 없다
        first, last = brgm.ZOOMS.get(brgm.upstream_name(layer.name), (None, None))
        return {"attribution": brgm.ATTRIBUTION, "projection": "EPSG:3857",
                **({"minZoom": first} if first else {}), **({"lastZoom": last} if last else {}),
                **({"queryable": False} if brgm.upstream_name(layer.name) in brgm.SCANS else {})}
    if layer.upstream in ("bgr", "igme", "gsi", "sgc"):
        # 독일·스페인·아일랜드(wetherilli 147)·남미(188) — 판마다 받는 투영과 그리는 줌이 다르다
        door = {"bgr": bgr, "igme": igme, "gsi": gsi, "sgc": sgc}[layer.upstream]
        try:
            sheet = door.split(layer.name)[0]
        except RuntimeError:
            return {}
        first, last = door.ZOOMS.get(sheet, (None, None))
        return {"attribution": getattr(door, "ATTRIBUTIONS", {}).get(sheet, door.ATTRIBUTION),
                "projection": getattr(door, "PROJECTION", {}).get(sheet, "EPSG:3857"),
                **({"minZoom": first} if first else {}), **({"lastZoom": last} if last else {}),
                # 범례 그림이 너무 큰 판(도미니카공화국, wetherilli 242)
                **({"noLegend": True} if sheet in getattr(door, "NO_LEGEND", ()) else {}),
                # IGME5000 의 단층·연대 기호(wetherilli 217)는 누를 것이 없다
                **({} if getattr(door, "queryable", lambda n: True)(layer.name) else {"queryable": False})}
    if layer.upstream == "georep" and georep.knows(layer.name):
        # 누벨칼레도니 Géorep(wetherilli 260) — 축척마다 상류가 판을 바꿔 그린다. 속성은 REST identify(문이 WMS 꼴을 바꾼다)
        return {"attribution": georep.ATTRIBUTION, "projection": "EPSG:3857", "legend": "list", "legendUrl": "list/legend/"}
    if layer.upstream == "ineter" and ineter.knows(layer.name):
        # 니카라과 INETER(wetherilli 242) — GeoServer 를 3857 로. 단층은 값의 글자가 깨져 누르지 않는다
        return {"attribution": ineter.ATTRIBUTION, "projection": "EPSG:3857",
                **({} if layer.name in ineter.DOOR.queryable else {"queryable": False})}
    if layer.upstream == "skgs" and skgs.knows(layer.name):
        # 사스카치원(wetherilli 235) — ArcGIS WMS 를 3978 로 곧장(Capabilities 에 없지만 그린다)
        return {"attribution": skgs.ATTRIBUTION, "projection": "EPSG:3978",
                # 광물 산지 SMDI·광산(wetherilli 288) — 다른 서비스의 REST, 범례를 두지 않는다. 넓게 보면 한 장에 10 초라 줌 6 부터
                **({"noLegend": True, "minZoom": 6} if layer.name in skgs.RESOURCES else {}),
                **({} if skgs.queryable(layer.name) else {"queryable": False})}
    if layer.upstream == "nsgs" and nsgs.knows(layer.name):
        # 노바스코샤(wetherilli 235) — WMS 가 없어 문이 REST export 로 옮긴다. 화면의 투영을 그대로 넘긴다
        first, _ = nsgs.zooms(layer.name)
        return {"attribution": nsgs.ATTRIBUTION, "projection": "EPSG:3978", "noLegend": True,
                **({"minZoom": first} if first else {}), **({} if nsgs.queryable(layer.name) else {"queryable": False})}
    if layer.upstream == "bas" and bas.knows(layer.name):
        # 남극 Bedmap3(wetherilli 261) — BAS 의 ArcGIS Online 타일을 화면이 곧장. Esri 극 격자라 원점·해상도를 행에 싣는다. 누르기는 없다
        return {"attribution": bas.ATTRIBUTION, "tiles": bas.tile_url(layer.name), "grid": bas.grid(layer.name),
                "queryable": False, "legend": "list", "legendUrl": "list/legend/"}
    if layer.upstream == "ags" and ags.knows(layer.name):
        # 앨버타(wetherilli 235) — 타일은 ArcGIS Online 의 3857 z/x/y 를 화면이 곧장(지리원 주제 타일과 같은 길), 누른 자리만 문이
        url, last = ags.LAYERS[layer.name]
        return {"attribution": ags.ATTRIBUTION, "tiles": url, "maxZoom": last, "noLegend": True}
    if layer.upstream in ("geosphere", "pig", "tno", "dov", "spw"):
        # 유럽(wetherilli 237) — 3857 로 그린다. 오스트리아·폴란드는 상류가 가까이서 그리지 않아 그 줌 위는 화면이 늘리고(`maxZoom`),
        # 폴란드 단층은 줌 10·왈로니아는 줌 9(단층 13)부터. 왈로니아 범례는 395 칸 약호뿐이라 두지 않는다
        mod = {"geosphere": geosphere, "pig": pig, "tno": tno, "dov": dov, "spw": spw}[layer.upstream]
        if mod.knows(layer.name):
            extra = {"attribution": mod.ATTRIBUTION, "projection": "EPSG:3857"}
            spec = {"geosphere:geology": {"maxZoom": geosphere.MAX_ZOOM}, "geosphere:faults": {"maxZoom": geosphere.MAX_ZOOM},
                    "pig:mgp500k": {"maxZoom": pig.MAX_ZOOM}, "pig:faults": {"minZoom": pig.FAULTS_MIN_ZOOM},
                    # 1:5만 둘 — 가까이서만 그린다(wetherilli 239)
                    "geosphere:units50k": {"minZoom": geosphere.UNITS50_MIN_ZOOM, "noLegend": True},
                    "pig:smgp50k": {"minZoom": pig.SMGP_MIN_ZOOM}, "pig:smgp50k_lines": {"minZoom": pig.SMGP_MIN_ZOOM},
                    "spw:geology": {"minZoom": spw.MIN_ZOOM, "noLegend": True},
                    "spw:faults": {"minZoom": spw.FAULTS_MIN_ZOOM, "noLegend": True}}.get(layer.name, {})
            extra.update(spec)
            if layer.name in ("geosphere:faults", "pig:faults", "spw:faults", "pig:smgp50k_lines"):
                extra["queryable"] = False
            return extra
    if layer.upstream == "bcgs" and bcgs.knows(layer.name):
        # 브리티시컬럼비아(wetherilli 231) — GeoServer 가 3978 로 그린다. 1:50만 너머는 우리 스타일을 POST 로 보내 줌 5 부터(wetherilli 317)
        if layer.name == "bcgs:minfile":
            # MINFILE 광물 산지(wetherilli 288) — 같은 openmaps 의 점 레이어, 넓게 봐도 그린다
            return {"attribution": bcgs.ATTRIBUTION, "projection": "EPSG:3978"}
        return {"attribution": bcgs.ATTRIBUTION, "projection": "EPSG:3978", "minZoom": bcgs.MIN_ZOOM}
    if layer.upstream in usstates.DOORS and usstates.knows(layer.upstream, layer.name):
        # 네바다·워싱턴·오리건(wetherilli 291) — 캘리포니아처럼 문이 REST export 를 3978 로. 주 밖 칸은 묻지 않는다(`clip`).
        # 넓게 보면 느린 판은 처음 줌을 둔다. 범례는 REST 를 목록으로
        first = usstates.first_zoom(layer.name)
        legend = {"legend": "list", "legendUrl": "list/legend/"} if layer.name in usstates.LEGEND_LAYERS else {"noLegend": True}
        return {"attribution": usstates.UPSTREAMS[layer.upstream][0], "projection": "EPSG:3978", "clip": True,
                **legend, **({"minZoom": first} if first else {})}
    if layer.upstream == "calgs" and calgs.knows(layer.name):
        # 캘리포니아(wetherilli 231) — 문이 REST export 를 3978 로 받는다. 줌 12 너머는 상류가 그리지 않아 화면이 늘린다. 범례는 목록
        return {"attribution": calgs.ATTRIBUTION, "projection": "EPSG:3978", "maxZoom": calgs.MAX_ZOOM,
                "legend": "list", "legendUrl": "list/legend/"}
    if layer.upstream in ("sigeom", "ygs"):
        # 퀘벡·유콘(wetherilli 210) — 캐나다 탭처럼 3978 로 곧장(Capabilities 에 없지만 그린다). 가까이서만 그린다 — 퀘벡은 상류가
        # 축척으로 판을 끄고, 유콘은 넓게 보면 한 장이 13 초다. 범례는 없다(퀘벡 28×18 한 칸), 유콘은 그림 범례
        door = {"sigeom": sigeom, "ygs": ygs}[layer.upstream]
        if not door.knows(layer.name):
            return {}
        first, _ = door.zooms(layer.name)
        return {"attribution": door.ATTRIBUTION, "projection": "EPSG:3978", **({"minZoom": first} if first else {}),
                **({} if door.queryable(layer.name) else {"queryable": False}),
                # 퀘벡 일반·지역 지질은 보는 범위의 범례(`sigeom/legend/`, wetherilli 337), 나머지는 없다
                **({"legend": "extent", "legendUrl": "sigeom/legend/"} if layer.name in sigeom.LEGEND
                   else {"noLegend": True} if layer.upstream == "sigeom" else {})}
    if layer.upstream in ("ispra", "lneg") and {"ispra": ispra, "lneg": lneg}[layer.upstream].knows(layer.name):
        # 이탈리아 ISPRA·포르투갈 LNEG(wetherilli 211) — ArcGIS WMS 를 3857 로. 가까이서만 그려 주는 판(1:10만·구조선)은 그 줌부터
        mod = {"ispra": ispra, "lneg": lneg}[layer.upstream]
        first, last = mod.ZOOMS.get(layer.name, (None, None))
        return {"attribution": mod.ATTRIBUTION, "projection": "EPSG:3857",
                **({"minZoom": first} if first else {}), **({"lastZoom": last} if last else {})}
    if layer.upstream == "swisstopo" and swisstopo.knows(layer.name):
        # 스위스 swisstopo(wetherilli 211) — geo.admin.ch WMS 를 3857 로. 속성은 문이 REST identify 로 바꾼다
        return {"attribution": swisstopo.ATTRIBUTION, "projection": "EPSG:3857"}
    if layer.upstream == "ga" and ga.knows(layer.name):
        # 호주 GA(wetherilli 212) — ArcGIS WMS 를 3857 로(3577 은 그리지 않는다). 레이어 하나가 1:250만·1:100만을 함께 부르고 상류가
        # 축척에 맞는 판을 그린다. 범례는 보는 범위의 것(`ga/legend/`), 단층은 범례·누르기가 없다
        if layer.name in ga.OTHER:
            # 지질구·핵심 광물·지구물리 격자(wetherilli 241) — 범례는 상류 그림, 격자는 범례·누르기가 없다
            grid = ga.OTHER[layer.name][3]
            return {"attribution": ga.OTHER_ATTRIBUTION, "projection": "EPSG:3857",
                    **({"noLegend": True} if grid else {}), **({} if ga.queryable(layer.name) else {"queryable": False})}
        unit = layer.name in ga.legend_layers()
        return {"attribution": ga.ATTRIBUTION, "projection": "EPSG:3857",
                **({"legend": "extent", "legendUrl": "ga/legend/"} if unit else {"noLegend": True, "queryable": False})}
    if austates.knows(layer.upstream, layer.name):
        # 호주의 주 판(wetherilli 225) — 퀸즐랜드는 REST export, 빅토리아·남호주는 GeoServer. 모두 3857. 넓게 보면 비거나 느려
        # 처음 줌을 둔다. 단위 면은 보는 범위의 범례(`austates/legend/`, 232), 구조선은 범례·누르기가 없다
        first = austates.first_zoom(layer.upstream, layer.name)
        legend = ({"legend": "extent", "legendUrl": "austates/legend/"} if austates.is_unit(layer.upstream, layer.name)
                  # 광산·광물 산지(wetherilli 269)는 누르기만, 지구물리 영상·구조선은 범례·누르기가 없다
                  else {"noLegend": True} if austates.queryable(layer.upstream, layer.name) else {"noLegend": True, "queryable": False})
        return {"attribution": austates.UPSTREAMS[layer.upstream][2], "projection": "EPSG:3857", **legend,
                **({"minZoom": first} if first else {})}
    if layer.upstream == "nrcan" and nrcan.knows(layer.name):
        # 캐나다 NRCan 1:500만(wetherilli 204) — 캐나다 탭의 투영(3978, 캐나다 람베르트)으로 곧장 받는다. 범례는 상류의 그림
        if layer.name in nrcan.SERVICES:
            # 같은 서버의 다른 서비스(wetherilli 250) — 편찬 지질도·유망도는 래스터라 누르지 않고 범례 그림만
            return {"attribution": nrcan.OTHER_ATTRIBUTION, "projection": "EPSG:3978",
                    **({} if nrcan.queryable(layer.name) else {"queryable": False})}
        return {"attribution": nrcan.ATTRIBUTION, "projection": "EPSG:3978"}
    if layer.upstream == "ogs" and ogs.knows(layer.name):
        # 온타리오 OGS(wetherilli 204) — 3978 로 다시 그려 준다. 속성은 REST identify(문이 WMS 꼴을 바꾼다)
        return {"attribution": ogs.ATTRIBUTION, "projection": "EPSG:3978"}
    if layer.upstream == "sgm" and sgm.knows(layer.name):
        # 멕시코 SGM(wetherilli 206) — WMS 가 막혀 문이 REST export 로 옮긴다. 화면에는 3857 WMS 와 같다. 1:5만은 가까이서만.
        # 범례는 보는 범위의 것(`sgm/legend/`, 페루와 같은 꼴), 구조선은 범례·누르기가 없다. 같은 서버의 지질 연대·고생물·광상(wetherilli 219)은
        # 누를 수 있고, 시대 색인 지질 연대 점만 범례가 있다
        first, last = sgm.zooms(layer.name)
        unit = layer.name in sgm.legend_layers()
        return {"attribution": sgm.ATTRIBUTION, "projection": "EPSG:3857",
                **({"legend": "extent", "legendUrl": "sgm/legend/"} if unit else {"noLegend": True}),
                **({} if sgm.queryable(layer.name) else {"queryable": False}),
                **({"minZoom": first} if first else {})}
    if layer.upstream == "mrdata" and mrdata.knows(layer.name):
        # 미국 USGS(wetherilli 205) — MapServer WMS 를 3857 로. 범례는 없다(단위가 주마다 수천, GetLegendGraphic 501) — 팝업의 단위
        # 설명 링크가 갈음한다. 구조선·단층은 누르지 않는다
        return {"attribution": mrdata.ATTRIBUTION, "projection": "EPSG:3857", "noLegend": True,
                **({} if layer.name in mrdata.QUERYABLE else {"queryable": False}),
                # 하와이·푸에르토리코(wetherilli 238)는 미국 탭(3978)에서 제 범위 밖 타일을 묻지 않는다
                **({"clip": True} if layer.name in mrdata.ISLANDS else {}),
                # 광물 자원·광산 기호(wetherilli 247)는 넓게 보면 점이 땅을 덮어 가까이서부터
                **({"minZoom": mrdata.MIN_ZOOM[layer.name]} if layer.name in mrdata.MIN_ZOOM else {})}
    if layer.upstream == "iige" and iige.knows(layer.name):
        # 에콰도르 IIGE(wetherilli 198) — ArcGIS WMS 를 3857 로. 범례는 보는 범위의 것(`iige/legend/`, 페루와 같은 꼴)
        return {"attribution": iige.ATTRIBUTION, "projection": "EPSG:3857", "legend": "extent", "legendUrl": "iige/legend/"}
    if layer.upstream == "ingemmet" and layer.name in ingemmet.STRUCTURES:
        # 페루 단층·습곡(wetherilli 222) — 지질도와 같은 z/x/y 길이지만 상류가 그때그때 그린다. 선이라 누르지 않고 범례가 없다
        first = ingemmet.STRUCTURES[layer.name]["min"]
        return {"attribution": ingemmet.ATTRIBUTION, "tiles": f"ingemmet/{ingemmet.sheet_of(layer.name)}/{{z}}/{{x}}/{{y}}.png",
                "maxZoom": ingemmet.STRUCTURES_MAX, "noLegend": True, "queryable": False,
                **({"minZoom": first} if first else {})}
    if layer.upstream == "sim3534" and caribmap.knows(layer.name):
        # 대앤틸리스(wetherilli 254) — 우리가 구운 3857 z/x/y. 누른 자리는 위경도로(`sim3534/info/`), 범례는 보는 범위의 것. 단층은 누르지 않는다
        unit = layer.name == "sim3534:units"
        return {"attribution": caribmap.ATTRIBUTION, "maxZoom": caribmap.MAX_ZOOM,
                "tiles": _versioned_url(f"sim3534/{caribmap.sheet_of(layer.name)}/{{z}}/{{x}}/{{y}}.png", sim3534_version()),
                "legend": "extent", "legendUrl": "sim3534/legend/", **({} if unit else {"queryable": False})}
    if layer.upstream == "ingemmet" and layer.name in ingemmet.RESOURCES:
        # 페루 광물·지구물리(wetherilli 277) — 단층·습곡처럼 다른 서비스의 export 를 타일 칸으로. 산지·광상·광화대는 위경도로 누른다
        first = ingemmet.first_zoom(layer.name)
        return {"attribution": ingemmet.ATTRIBUTION, "tiles": f"ingemmet/{ingemmet.sheet_of(layer.name)}/{{z}}/{{x}}/{{y}}.png",
                "maxZoom": ingemmet.STRUCTURES_MAX, "noLegend": True, **({"minZoom": first} if first else {}),
                **({} if ingemmet.knows_resource(layer.name) else {"queryable": False})}
    if layer.upstream == "ingemmet" and layer.name in ingemmet.UNITS:
        # 페루 1:5만 지질 단위만(wetherilli 234) — 암상 레이어만 export 로. 느려 줌 9 부터. 누른 자리·범례는 1:5만 통합판의 것
        return {"attribution": ingemmet.ATTRIBUTION, "tiles": f"ingemmet/{ingemmet.sheet_of(layer.name)}/{{z}}/{{x}}/{{y}}.png",
                "maxZoom": ingemmet.STRUCTURES_MAX, "minZoom": ingemmet.first_zoom(layer.name),
                "legend": "extent", "legendUrl": "ingemmet/legend/"}
    if layer.upstream == "ingemmet" and ingemmet.knows(layer.name):
        # 페루 INGEMMET(wetherilli 195) — WMS 는 넓게 물으면 30 초를 넘겨 REST 타일 캐시(3857 z/x/y)를 우리 서버가 중계한다(일본과 같다).
        # 누른 자리는 위경도로(`ingemmet/info/`), 범례는 보는 범위의 것(`ingemmet/legend/`)
        return {"attribution": ingemmet.ATTRIBUTION,
                "tiles": f"ingemmet/{ingemmet.sheet_of(layer.name)}/{{z}}/{{x}}/{{y}}.png",
                "maxZoom": ingemmet.LAYERS[layer.name]["max"], "legend": "extent", "legendUrl": "ingemmet/legend/"}
    if layer.upstream == "sgb" and sgb.knows(layer.name):
        # 브라질 SGB(wetherilli 191) — GeoServer 라 3857 을 그대로. 1:100만·1:25만은 가까이서만 그린다. 범례 그림이 225×46 700 이라
        # 보는 범위의 범례를 뜬다(`sgb/legend/`) — 대만과 같은 꼴이다. 구조선은 범례가 없다
        first, last = sgb.zooms(layer.name)
        legend = ({"legend": "extent", "legendUrl": "sgb/legend/"} if layer.name in sgb.legend_layers()
                  else {} if layer.name in sgb.IMAGE_LEGENDS            # 구조선 1:250만은 상류의 그림 범례 (wetherilli 337)
                  else {"noLegend": True})
        return {"attribution": sgb.ATTRIBUTION, "projection": "EPSG:3857", **legend,
                **({"minZoom": first} if first else {}), **({"lastZoom": last} if last else {})}
    if layer.upstream == "segemar" and segemar.knows(layer.name):
        # 아르헨티나 SEGEMAR(wetherilli 196) — GeoServer 라 3857 을 그대로. 1:25만은 간행 도폭만 덮어 가까이서만 그린다.
        # 범례는 상류의 그림 한 장이다(JSON 범례를 이 GeoServer 가 받지 못한다)
        # 여럿을 묶은 레이어(주별 1:75만 구조선, wetherilli 220)는 범례가 없다
        first, last = segemar.ZOOMS.get(segemar.upstream_name(layer.name), (None, None))
        return {"attribution": segemar.ATTRIBUTION, "projection": "EPSG:3857",
                **({"noLegend": True} if segemar.upstream_name(layer.name) in segemar.COMBINED else {}),
                **({"minZoom": first} if first else {}), **({"lastZoom": last} if last else {})}
    if layer.upstream == "dinamige" and dinamige.knows(layer.name):
        # 우루과이 DINAMIGE(wetherilli 196) — 3857 로 그린다. 그림 범례가 비어 REST 범례를 목록으로 낸다(`dinamige/legend/`)
        legend = ({"legend": "list", "legendUrl": "dinamige/legend/"} if layer.name in dinamige.LEGEND_LAYERS
                  else {"noLegend": True})
        return {"attribution": dinamige.ATTRIBUTION, "projection": "EPSG:3857", **legend}
    if layer.upstream == "cgmw":
        # 아프리카 1:1000만(wetherilli 207) — BRGM 의 mapsref 서버, 3857 그대로. 범례는 Capabilities 의 정적 PNG(`brgm.cgmw_get_legend`)
        return {"attribution": brgm.CGMW_ATTRIBUTION, "projection": "EPSG:3857"}
    if layer.upstream == "cgs" and cgs.knows(layer.name):
        # 남아공 CGS 1:100만(wetherilli 209) — 문이 WMS 변수를 ArcGIS REST export·identify 로 옮긴다. 범례는 REST 를 목록으로(`cgs/legend/`)
        if layer.name != "cgs:geology_1m":
            # 광업·석탄·우라늄 지역(wetherilli 285)도 같은 서비스다. 한 색이라 범례 칸 이름이 비어 범례를 두지 않는다. 석탄 지역은 누르지 않는다
            return {"attribution": cgs.ATTRIBUTION, "projection": "EPSG:3857", "noLegend": True,
                    **({"queryable": False} if layer.name in cgs.NOT_QUERYABLE else {})}
        return {"attribution": cgs.ATTRIBUTION, "projection": "EPSG:3857", "legend": "list", "legendUrl": "cgs/legend/"}
    if layer.upstream == "gsn":
        # 나미비아 GSN 1:100만(wetherilli 209) — BGS 의 MapServer, 3857 그대로
        return {"attribution": bgs.GSN_ATTRIBUTION, "projection": "EPSG:3857"}
    if layer.upstream == "bumigeb":
        # 부르키나파소 BUMIGEB 1:100만(wetherilli 246) — BGS 의 MapServer, 3857. 구조선은 누를 것이 없다
        return {"attribution": bgs.BUMIGEB_ATTRIBUTION, "projection": "EPSG:3857",
                **({} if layer.name.endswith("_BLS") else {"queryable": False})}
    if layer.upstream == "irgm":
        # 카메룬 IRGM 1:100만(wetherilli 246) — BRGM 의 MapServer 가 4326 만 그린다(IGME 1:100만처럼 화면이 옮겨 그린다). 속성 열이 없다.
        # 단층은 범례 그림이 예외라 범례가 없다
        unit = layer.name.split(":", 1)[1] in brgm.IRGM_LEGEND_LAYERS
        return {"attribution": brgm.IRGM_ATTRIBUTION, "projection": "EPSG:4326", "queryable": False,
                **({} if unit else {"noLegend": True})}
    if layer.upstream == "aga":
        # 아프리카 지하수 지도책의 나라별 지질(wetherilli 207) — 38 나라 레이어를 문이 이어 묻는다. 3857 그대로
        return {"attribution": bgs.AGA_ATTRIBUTION, "projection": "EPSG:3857"}
    if layer.upstream == "gsni":
        return {"attribution": bgs.GSNI_ATTRIBUTION, "projection": "EPSG:3857"}
    if layer.upstream == "egdi":
        # 범유럽 1:100만(wetherilli 143) — 속성 서버가 오류를 내서 누르지 않는다
        return {"attribution": egdi.ATTRIBUTION, "projection": "EPSG:3857",
                **({} if egdi.QUERYABLE else {"queryable": False})}
    if layer.upstream == "gsjows" and gsj.gsjows_tiles(layer.name):
        # 공중 자력 편집도(wetherilli 266) — 지질도Navi 판을 카탈로그에 올린 것. 타일은 브라우저가 tiles.gsj.jp 를 곧장(Navi 칸과 같은 길),
        # 범례는 문이 받아 준 범례 그림
        return {"attribution": gsj.GEONAVI_ATTRIBUTION, "tiles": gsj.gsjows_tiles(layer.name),
                "maxZoom": gsj.GSJOWS_NAVI[layer.name][1], "queryable": False}
    if layer.upstream == "gsjows" and gsj.gsjows_knows(layer.name):
        # GSJ 의 다른 WMS(wetherilli 255) — 3857 로. 1:200만 지질도·중력은 누른다(wetherilli 316), 지구화학도는 범례 그림으로
        return {"attribution": gsj.GSJOWS_ATTRIBUTION, "projection": "EPSG:3857",
                **({} if layer.name in gsj.GSJOWS_INFO else {"queryable": False})}
    if layer.upstream == "gsitile" and layer.name in GSI_TILES:
        # 국토지리원 주제 타일(wetherilli 172) — 서버를 거치지 않고 브라우저가 곧장 부르는 카탈로그 레이어의 첫 선례다.
        # 지리원 타일은 열쇠가 없고 CORS 가 열려 있어 배경(BASEMAPS gsi_*)과 같은 길이다. 속성이 없고 범례는 그림이 아니다
        spec = GSI_TILES[layer.name]
        return {"attribution": GSI_ATTRIBUTION, "tiles": GSI_TILE_URL.format(path=spec["path"]),
                "minZoom": spec["min"], "maxZoom": spec["max"], "queryable": False, "noLegend": True}
    if layer.upstream == "gsj" and gsj.knows(layer.name):
        # 일본(024) — z/x/y 타일을 우리 서버가 중계한다. 경계·단층·기호는 줌 10·11
        # 부터 그려져서 그보다 멀면 화면이 레이어를 숨긴다(`minZoom`)
        spec = gsj.LAYERS[layer.name]
        return {"attribution": gsj.ATTRIBUTION,
                "tiles": f"gsj/{layer.name.split(':', 1)[1]}/{{z}}/{{x}}/{{y}}.png",
                "minZoom": spec["min"], "maxZoom": spec["max"],
                "legend": spec["legend"] or "none", "viewer": gsj.VIEWER_URL,
                **({} if spec["info"] else {"queryable": False})}
    if layer.upstream == "gsmma" and gsmma.knows(layer.name):
        # 대만(wetherilli 136) — 상류가 4326 만 받아 그 격자로 받는다(`map.js` 의 `taiwanSource`). 범례는 주지 않는다
        # 5만·25만 지질도는 보는 범위의 범례를 그림에서 떠 온다(`gsmma/legend/`, wetherilli 142)
        legend = ({"legend": "extent", "legendUrl": "gsmma/legend/"} if layer.name in gsmma.LEGENDS
                  else {"noLegend": True})
        return {"attribution": gsmma.ATTRIBUTION, "projection": "EPSG:4326", **legend,
                **({} if gsmma.queryable(layer.name) else {"queryable": False})}
    if layer.upstream == "phyloserver" and phyloserver.knows_scan(layer.name):
        # 한반도 지질도(026) — phyloserver 의 카카오 격자 타일. 5181 격자를 화면이 옮겨 그린다
        return {"attribution": phyloserver.ATTRIBUTION, "queryable": False, "noLegend": True,
                "tiles": f"phyloserver/{layer.name.split(':', 1)[1]}/{{z}}/{{x}}_{{y}}.png"}
    if layer.upstream == "admap" and layer.name == admap.NAME:
        # 남극 자력 이상 ADMAP-2(wetherilli 262) — 우리가 칠해 잘라 둔 3031 타일(GeoMAP 격자, 줌 4 까지). 범례는 갈래 표
        return {"attribution": admap.ATTRIBUTION, "projection": "EPSG:3031", "maxZoom": admap.MAX_ZOOM,
                "tiles": _versioned_url("admap/{z}/{x}/{y}.webp", _dir_version(admap.tiles_dir())),
                "classLegend": admap.legend(lang)}
    if layer.upstream == "ibcso" and layer.name == ibcso.TID_LAYER:
        # IBCSO 자료 출처(071) — 우리가 잘라 둔 3031 타일. 격자는 GeoMAP 의 것이고 줌 6 까지다.
        # 범례는 갈래 표를 그대로 보낸다(그림이 아니라 — 컨테이너에 한글 글꼴이 없다)
        return {"attribution": ibcso.ATTRIBUTION, "projection": "EPSG:3031", "maxZoom": ibcso.MAX_ZOOM,
                "tiles": _versioned_url("ibcso/tid/{z}/{x}/{y}.png", _dir_version(ibcso.tid_tiles_dir())),
                "classLegend": ibcso.tid_legend(lang)}
    if layer.upstream == "peninsula" and layer.name in peninsula.SHEETS:
        # 한반도 지질도 음영판·민판(027·028) — 우리가 잘라 둔 5179 타일. 격자를 화면에 알린다
        sheet = peninsula.SHEETS[layer.name]
        return {"attribution": sheet.attribution, "queryable": False, "noLegend": True,
                "projection": "EPSG:5179", "grid": sheet.grid(),
                "tiles": _versioned_url(f"peninsula/{layer.name.split(':', 1)[1]}/{{z}}/{{x}}/{{y}}.{peninsula.FORMAT}",
                                        _dir_version(sheet.tiles_dir()))}
    return {}


@require_GET
def patch_notes(request):
    """판 이력. 설정 창이 펼쳐 보인다.

    `CHANGELOG.md` 를 **그때그때 읽는다.** 이미지에 구워 넣은 파일이라
    바뀌지 않고, 파일 하나 읽는 값이 캐시를 두는 값보다 싸다.
    """
    path = settings.REPO_DIR / "CHANGELOG.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return JsonResponse({"version": VERSION, "notes": []})
    return JsonResponse({"version": VERSION, "notes": patchnotes.parse(text)})


@require_GET
def catalog_json(request):
    return JsonResponse({"groups": _catalog(i18n.lang_of(request))})


# ── 상류 프록시 ───────────────────────────────────────────────────────
#
# 레이어마다 나가는 문이 다르다 — 한국은 KIGAM(`kigam.py`)과 "지질 참고"의
# VWorld(`vworld.py`), 그린란드는 GEUS(`geus.py`). 캐시·옛것 내주기·안내
# 타일은 셋이 같이 쓴다.

UPSTREAM_ERRORS = (kigam.UpstreamError, geus.GeusError, vworld.VWorldError, geomap.GeomapError,
                   npolar.NpolarError, kopri.KopriError, elevation.ElevationError, gsj.GsjError,
                   gsmma.GsmmaError, emodnet.EmodnetError, ngu.NguError, gtk.GtkError, sgu.SguError,
                   bgs.BgsError, brgm.BrgmError, egdi.EgdiError,
                   bgr.BgrError, igme.IgmeError, gsi.GsiError, sgc.SgcError, sgb.SgbError, cgs.CgsError, ingemmet.IngemmetError,
                   segemar.SegemarError, dinamige.DinamigeError, iige.IigeError, mrdata.MrdataError, sgm.SgmError, nrcan.NrcanError, ogs.OgsError, sigeom.SigeomError, ygs.YgsError, skgs.SkgsError, nsgs.NsgsError, ags.AgsError, ga.GaError, austates.AuStatesError,
                   ispra.IspraError, lneg.LnegError, swisstopo.SwisstopoError, natt.NattError, gns.GnsError, mris.MrisError, gsiindia.GsiIndiaError, sgs.SgsError,
                   esdm.EsdmError, jmg.JmgError, mgb.MgbError, dmr.DmrError, bcgs.BcgsError, calgs.CalgsError, usstates.UsStatesError, bas.BasError,
                   geosphere.GeosphereError, pig.PigError, tno.TnoError, dov.DovError, spw.SpwError, ineter.IneterError, georep.GeorepError,
                   basemaps.BasemapError)


def _upstream_of(layers: str) -> str:
    """레이어명(여럿이면 첫째)의 상류. 카탈로그에 없으면 kigam 이다."""
    name = (layers or "").split(",")[0].strip()
    # 도폭 하나(`npolar:svalbard_sheets@A4G`)는 카탈로그에 없다 — 밑 레이어의 상류를 따른다
    name = name.split("@", 1)[0]
    try:
        row = Layer.objects.filter(name=name).values_list("upstream", flat=True).first()
    except Exception:                  # 카탈로그를 못 읽어도 한국 지도는 돌아야 한다
        row = None
    return row or "kigam"


#: 받은 것을 서버 캐시에 담지 않는 상류 — 자료를 파는 곳이라 다시 내주지 않는다. 남아공 CGS(정부 사본)·나미비아 GSN (wetherilli 209)
NO_STORE = ("cgs", "gsn")


class _Door:
    """상류 하나의 get_map·get_feature_info·get_legend 와, 지금 쓸 수 있는지.

    geomap 은 상류가 아니라 **우리 디스크의 파일**이다(`local`). 받아온 것이
    아니므로 속성·범례를 캐시에 담지 않는다 — 파일에서 읽는 편이 빠르고,
    판을 갈면 곧바로 새 것이 보인다.
    """

    MODULES = {"kigam": kigam, "geus": geus, "geusarc": geus.ARC, "vworld": vworld, "geomap": geomap, "npolar": npolar, "kopri": kopri,
               # PGC 경사·등고선(wetherilli 099) — 문은 표고와 같은 elevation.py 다
               "pgc": elevation,
               # CCOP 200만 지질도(wetherilli 108) — GSJ 새 호스트의 WMS. 문은 gsj.py 다
               "ccop": gsj.CCOP,
               # GSJ 의 다른 WMS — 1:200만·중력·지구화학도(wetherilli 255)
               "gsjows": gsj.OWS,
               # 대만 지질도(wetherilli 136) — 그림은 4326 WMS, 속성은 지질운 GeoJSON. 문은 gsmma.py 다
               "gsmma": gsmma.DOOR,
               # EMODnet 해저 지질(wetherilli 135) — 북극해. NPI 처럼 3413 으로 곧장 받는다
               "emodnet": emodnet,
               # 노르웨이·핀란드 기반암(wetherilli 140)
               "ngu": ngu, "gtk": gtk, "sgu": sgu,
               # 영국·프랑스·범유럽(wetherilli 143)
               "bgs": bgs, "brgm": brgm, "egdi": egdi,
               # 영국 GeoIndex — 자력·중력·광산·광물 산지(wetherilli 258)
               "bgsgi": bgs.GEOINDEX,
               # 독일·스페인·아일랜드(wetherilli 147). GSNI 는 BGS 서버가 내주어 문이 bgs.py 다
               "bgr": bgr, "igme": igme, "gsi": gsi, "gsni": bgs.GSNI,
               # 남미·콜롬비아(wetherilli 188)·브라질(191)
               "sgc": sgc, "sgb": sgb,
               # 페루(wetherilli 195) — 그림은 타일 캐시라 이 문의 WMS 길은 오류를 낸다. 눌러 묻는 것도 따로다(`ingemmet_info`)
               "ingemmet": ingemmet,
               # 아르헨티나·우루과이(wetherilli 196)
               "segemar": segemar, "dinamige": dinamige,
               # 에콰도르(wetherilli 198)
               "iige": iige,
               # 미국(wetherilli 205)
               "mrdata": mrdata,
               # 멕시코(wetherilli 206)
               "sgm": sgm,
               # 아프리카(wetherilli 207) — CGMW–BRGM 은 brgm.py, 지하수 지도책은 bgs.py 안에 따로 둔 상류다(GSNI 와 같은 꼴)
               "cgmw": brgm.CGMW, "aga": bgs.AGA,
               # 아프리카 나라 판(wetherilli 209) — 남아공은 새 문, 나미비아는 BGS 가 내주어 bgs.py 안에
               "cgs": cgs, "gsn": bgs.GSN,
               # 부르키나파소·카메룬 1:100만(wetherilli 246) — BGS·BRGM 이 대신 내준다
               "bumigeb": bgs.BUMIGEB, "irgm": brgm.IRGM,
               # 캐나다(wetherilli 204)
               "nrcan": nrcan, "ogs": ogs,
               # 퀘벡·유콘(wetherilli 210)
               "sigeom": sigeom, "ygs": ygs,
               # 사스카치원·노바스코샤·앨버타(wetherilli 235)
               "skgs": skgs, "nsgs": nsgs, "ags": ags,
               # 호주(wetherilli 212)
               "ga": ga,
               # 호주의 주 판(wetherilli 225) — 한 파일(`austates.py`)에 문 셋
               "gsq": austates.GSQ, "gsv": austates.GSV, "gssa": austates.GSSA,
               # 태즈메이니아·뉴사우스웨일스 (wetherilli 318)
               "mrt": austates.TAS, "gsnsw": austates.GSNSW,
               # 이탈리아·포르투갈·스위스(wetherilli 211)
               "ispra": ispra, "lneg": lneg, "swisstopo": swisstopo,
               # 아이슬란드(wetherilli 216)
               "natt": natt,
               # 뉴질랜드·남빅토리아랜드(wetherilli 218)
               "gns": gns,
               # 몽골(wetherilli 221)
               "mris": mris,
               # 인도(wetherilli 226)
               "gsiindia": gsiindia,
               # 사우디아라비아(wetherilli 227)
               "sgs": sgs,
               # 동남아(wetherilli 228)
               "esdm": esdm, "jmg": jmg, "mgb": mgb, "dmr": dmr,
               # 브리티시컬럼비아·캘리포니아(wetherilli 231)
               "bcgs": bcgs, "calgs": calgs,
               # 네바다·워싱턴·오리건(wetherilli 291) — 한 파일(`usstates.py`)에 문 셋
               **usstates.DOORS,
               # 오스트리아·폴란드·네덜란드·벨기에(wetherilli 237)
               "geosphere": geosphere, "pig": pig, "tno": tno, "dov": dov, "spw": spw,
               # 니카라과(wetherilli 242)
               "ineter": ineter, "georep": georep}

    def __init__(self, upstream):
        self.name = upstream if upstream in self.MODULES else "kigam"
        mod = self.MODULES[self.name]
        self.get_map, self.get_feature_info, self.get_legend = mod.get_map, mod.get_feature_info, mod.get_legend
        self.local = self.name == "geomap"
        #: 받은 것을 서버 캐시에 담지 않는다 — 우리가 그리는 것(GeoMAP)과, 자료를 파는 상류(`NO_STORE`, wetherilli 209)
        self.nostore = self.local or self.name in NO_STORE
        if self.name in ("geus", "geusarc", "npolar", "kopri", "pgc", "ccop", "gsjows", "gsmma", "emodnet", "ngu", "gtk", "bgs", "bgsgi", "brgm", "egdi", "bgr", "igme", "gsi", "gsni", "sgc", "sgb", "ingemmet", "segemar", "dinamige", "iige", "mrdata", "sgm", "cgmw", "aga", "cgs", "gsn", "bumigeb", "irgm", "nrcan", "ogs", "sigeom", "ygs", "skgs", "nsgs", "ags", "ga", "gsq", "gsv", "gssa", "mrt", "gsnsw", "ispra", "lneg", "swisstopo", "sgu", "natt", "gns", "mris", "gsiindia", "sgs", "esdm", "jmg", "mgb", "dmr", "bcgs", "calgs", "nbmg", "wadnr", "dogami", "dggs", "geosphere", "pig", "tno", "dov", "spw", "ineter", "georep"):    # 열쇠가 없는 공개 서비스다
            self.ready = True
        elif self.name == "vworld":
            self.ready = vworld.enabled()
        elif self.local:
            self.ready = geomap.available()
        else:
            self.ready = kigam.has_key()

    def not_ready_message(self):
        if self.local:
            return msg("남극 지질도 자료(GeoMAP)가 서버에 없다")
        return msg("인증키가 없다")


#: 메타타일로 받는 레이어 — 문마다의 표를 모은다(이름 또는 `:` 로 끝나는 앞머리 → 가장 깊은 격자 줌, None 은 모든 줌) (wetherilli 282·284)
METATILE = {**sgm.METATILE, **sgc.METATILE, **egdi.METATILE, **geus.METATILE,   # 그린란드 GEUS ArcGIS 는 3413 격자 (wetherilli 307)
            # 느린 상류를 재어 더한 것 (wetherilli 287)
            **austates.METATILE, **iige.METATILE, **ispra.METATILE, **mris.METATILE, **pig.METATILE, **sgs.METATILE,
            **dinamige.METATILE, **lneg.METATILE, **tno.METATILE, **swisstopo.METATILE, **segemar.METATILE, **gsi.METATILE}


def map_cache_key(params: dict) -> str:
    """타일의 캐시 열쇠. 받은 그림을 문이 고쳐 내는 레이어(알래스카의 물 면, wetherilli 224)는 고침의 판이 든다 — 미리 데우기도 이것을 쓴다"""
    key = tilecache.key_for("map", params)
    tag = mrdata.redraw_tag(params.get("layers"))
    return tilecache.key_text("map", f"{key}/r{tag}") if tag else key


@require_GET
def wms(request):
    """`GetMap` 중계. 브라우저가 부르는 타일 주소다.

    키가 없으면 500 을 내지 않고 **안내 타일을 200 으로 돌려준다.** 지도
    라이브러리는 타일 하나가 깨지면 그 자리를 비워둘 뿐 까닭을 말해주지
    않는다. 까닭은 타일에 적어 보내는 편이 사람에게 낫다.
    """
    params = kigam.clean_params(request.GET)
    width = _int(params.get("width"), 256)
    height = _int(params.get("height"), 256)

    params.setdefault("format", "image/png")
    params.setdefault("transparent", "true")

    # 남극(GeoMAP)은 우리가 그린다. 이름으로 가른다 — 한국 타일마다 DB 를 묻지 않으려고
    if (params.get("layers") or "").split(",")[0].strip() in geomap.LAYERS:
        return _geomap_wms(params, width, height)

    # 들고 있으면 상류에 묻지 않는다. **인증키가 없어도 캐시는 내준다** —
    # 이미 받아둔 그림이고, 다시 받을 일이 없으니 막을 까닭이 없다.
    cache_key = map_cache_key(params)
    hit = tilecache.get(cache_key)
    if hit is not None:
        return _tile(hit, cached=True)

    door = _Door(_upstream_of(params.get("layers")))
    if not door.ready:
        old = tilecache.get(cache_key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        return _tile(tiles.notice_tile(width, height, tiles.NO_KEY), store=False)

    # 느린 상류는 큰 장을 받아 잘라 담는다(메타타일, wetherilli 282) — 격자에 맞지 않는 칸이면 하던 대로 한 칸
    first = (params.get("layers") or "").split(",")[0].strip()
    last = metatile.limit(METATILE, first) if settings.METATILE else False      # 끄는 스위치(wetherilli 299)
    try:
        piece = (metatile.serve(first, params, lambda bbox, w, h: door.get_map(dict(params, bbox=bbox, width=w, height=h)),
                                max_zoom=last, errors=UPSTREAM_ERRORS)
                 if last is not False else None)
        if piece is not None:
            content, ctype = piece, "image/png"
        else:
            content, ctype = door.get_map(params)
    except (*UPSTREAM_ERRORS, metatile.Busy) as exc:
        # 늙어서 다시 물었는데 상류가 못 준다 — 빈 자리보다 옛것이 낫다. 메타타일 레이어는 조각에도 옛것이 있다
        old = tilecache.get(cache_key, stale=True)
        if old is None and last is not False:
            old = metatile.stale(first, params)
        if old is not None:
            log.info("타일을 못 받아 옛것을 낸다: %s", exc)
            return _tile(old, cached=True)
        log.warning("타일을 받지 못했다: %s", exc)
        # 늦은 것(문 한계·잠금 기다림)은 "느리다" 로 가른다 — 다시 보면 나올 수 있다 (wetherilli 300)
        return _tile(tiles.notice_tile(width, height, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)

    # 안내 타일은 캐시에 넣지 않는다 — 위에서 store=False 로 갈라 둔 까닭이다.
    # 자료를 파는 상류(`NO_STORE`)도 담지 않는다 — 그때그때 받아 보여 주기만 한다 (wetherilli 209)
    # 메타타일 조각으로 낸 칸도 다시 담지 않는다 — 조각 열쇠에 이미 있다(두 벌이 되지 않게, wetherilli 297)
    if not door.nostore and piece is None:
        tilecache.put(cache_key, content)

    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    response["X-GSM-Cache"] = "miss"
    return response


def _geomap_wms(params, width, height):
    """GeoMAP 을 WMS `GetMap` 꼴로 (3031 만). 화면은 보통 `geomap_tile` 을 부른다."""
    if not geomap.available():
        return _tile(tiles.notice_tile(width, height, tiles.NO_DATA), store=False)
    try:
        content, _ = geomap.get_map(params)
    except geomap.GeomapError as exc:
        log.info("GeoMAP 을 그리지 못했다: %s", exc)
        return _tile(tiles.notice_tile(width, height, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    return _tile(content)


def geomap_tile_key(layer, z, x, y, size):
    """GeoMAP 타일의 캐시 열쇠. `manage.py prewarm` 도 이것으로 담는다."""
    return tilecache.key_text("geomap", f"{layer}/{geomap.data_version()}/r{geomap.RENDERER}"
                                        f"/{z}/{x}/{y}/{size}")


@require_GET
def geomap_tile(request, layer, z, x, y, retina=None):
    """남극 지질도 타일 — `geomap/<레이어>/<z>/<x>/<y>.png` (`@2x` 면 512 px).

    격자는 EPSG:3031 고정이다 (`geomap.py` 머리글). 그린 것은 캐시에 담고 스스로
    지우지 않는다 — 다른 타일과 같다. 열쇠에 자료의 판과 `geomap.RENDERER` 가
    들어 있어, 판을 갈거나 그리는 법을 고치면 새로 그린다.
    """
    z, x, y = int(z), int(x), int(y)
    size = geomap.TILE * (2 if retina else 1)
    if layer not in geomap.LAYERS or not geomap.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    if not geomap.available():
        return _tile(tiles.notice_tile(size, size, tiles.NO_DATA), store=False)
    try:
        png, cached = _geomap_png(layer, z, x, y, size)
    except (geomap.GeomapError, OSError, ValueError) as exc:
        log.warning("GeoMAP 타일을 그리지 못했다 (%s %s/%s/%s): %s", layer, z, x, y, exc)
        return _tile(tiles.notice_tile(size, size, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    response = _immutable(request, _tile(png, cached=cached), geomap_version())
    if not cached:
        response["X-GSM-Cache"] = "miss"
    return response


def _geomap_png(layer, z, x, y, size=geomap.TILE):
    """GeoMAP 타일 한 장과 캐시에서 왔는지. 캐시에 없으면 그려 담는다 — 2D 의 타일과
    3D 가 다시 펴는 원본(`warp/geomap/`)이 같은 것을 쓴다. 못 그리면 옛것을, 그것도 없으면
    그리지 못한 까닭을 그대로 올린다."""
    key = geomap_tile_key(layer, z, x, y, size)
    hit = tilecache.get(key)
    if hit is not None:
        return hit, True
    try:
        png = geomap.render(layer, geomap.tile_bbox(z, x, y), size, size)
    except (geomap.GeomapError, OSError, ValueError):
        old = tilecache.get(key, stale=True)
        if old is not None:
            return old, True
        raise
    tilecache.put(key, png)
    return png, False


# ── 일본 — GSJ 심리스 지질도 (gsj.py, devlog 024) ─────────────────────
#
# WMS 가 아니라 z/x/y 타일과 `point=` 범례라서 `/wms/`·`/featureinfo/`·`/legend/` 를
# 타지 않고 따로 받는다. 캐시·옛것 내주기·안내 타일은 다른 상류와 같다.

def gsj_tile_key(name, z, x, y):
    """GSJ 타일의 캐시 열쇠. `manage.py prewarm` 도 이것으로 담는다."""
    return tilecache.key_text("gsj", f"{name}/{z}/{x}/{y}")


@require_GET
def gsj_tile(request, layer, z, x, y):
    """일본 지질도 타일 — `gsj/<레이어>/<z>/<x>/<y>.png`. 레이어는 `gsj:` 를 뗀 이름이다."""
    name, z, x, y = f"gsj:{layer}", int(z), int(x), int(y)
    if not gsj.valid_tile(name, z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    key = gsj_tile_key(name, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = gsj.get_tile(name, z, x, y)
    except gsj.GsjError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("GSJ 타일을 받지 못했다 (%s %s/%s/%s): %s", name, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    # 빈 타일도 담는다 — 바다 한가운데를 다시 물을 까닭이 없다
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def vworld_tile(request, layer, z, y, x):
    """VWorld 배경지도 타일 — `vworld/<레이어>/<z>/<y>/<x>`. 자리 차례는 WMTS 대로 z/y/x.

    **브라우저가 `api.vworld.kr` 에 곧장 닿지 못할 때만 온다** — 사내 VPN 이
    그 연결을 끊는다 (033). 캐시에 담지 않는다. 자료 밖은 투명한 빈 타일이다."""
    if not vworld.knows_wmts(layer):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    try:
        got = vworld.get_wmts_tile(layer, int(z), int(y), int(x))
    except vworld.VWorldError as exc:
        log.warning("VWorld 배경지도를 받지 못했다: %s", exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    if got is None:
        return _tile(tiles.blank_tile(256, 256))
    return _tile(got[0], content_type=got[1])


# ── 조건이 열린 배경 — NASA GIBS·GEBCO (wetherilli 184) ──
#
# 브라우저가 곧장 부르던 것을 서버가 받아 담는다(`basemaps.py`). 받는 것은 브라우저가 부르던 주소와 같다 — WMTS 는 같은 경로,
# WMS 는 같은 변수다. 정적 판(서버가 없다)은 여전히 곧장 부른다(`map.js` 의 `STATIC`).

def gibs_tile_key(epsg, layer, z, x, y):
    """GIBS WMTS 타일의 캐시 열쇠."""
    return tilecache.key_text("gibs", f"{epsg}/{layer}/{z}/{y}/{x}")


def _open_basemap(key, fetch, size, label):
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        content = fetch()
    except basemaps.BasemapError as exc:
        # 늙어서 다시 물었는데 상류가 못 준다 — 빈 자리보다 옛것이 낫다
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("%s 배경을 받지 못했다: %s", label, exc)
        return _tile(tiles.notice_tile(size, size, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, content)
    response = _tile(content)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def gibs_tile(request, epsg, layer, z, y, x):
    """NASA GIBS Blue Marble — `gibs/<투영>/<레이어>/<z>/<y>/<x>.jpeg`. 자리 차례는 WMTS 대로 z/y/x."""
    z, y, x = int(z), int(y), int(x)
    if not basemaps.knows_gibs_tile(epsg, layer, z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    return _open_basemap(gibs_tile_key(epsg, layer, z, x, y), lambda: basemaps.gibs_tile(epsg, layer, z, x, y),
                         512, "GIBS")


@require_GET
def npi_tile(request, service, z, y, x):
    """NPI 의 스발바르 지형도·위성 모자이크 — `npi/<서비스>/<z>/<y>/<x>` (wetherilli 200). 조건이 CC BY 4.0 이라 담는다."""
    z, y, x = int(z), int(y), int(x)
    if not basemaps.knows_npi_tile(service, z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    return _open_basemap(tilecache.key_text("npi-tile", f"{service}/{z}/{y}/{x}"),
                         lambda: basemaps.npi_tile(service, z, x, y), 256, "NPI")


def _open_wms(request, kind, layers, fetch, label):
    params = kigam.clean_params(request.GET)
    if not basemaps.wms_ok(params, layers):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    size = max(_int(params.get("width"), 256), _int(params.get("height"), 256))
    return _open_basemap(tilecache.key_for(kind, params), lambda: fetch(params), size, label)


@require_GET
def gibs_wms(request):
    """NASA GIBS WMS(4326) — 온 지구의 구(Cesium)가 부른다."""
    return _open_wms(request, "gibs", basemaps.GIBS_LAYERS, basemaps.gibs_wms, "GIBS")


@require_GET
def gebco_wms(request):
    """GEBCO 해저 지형 WMS — 지역 탭의 배경과 온 지구 평면이 부른다."""
    return _open_wms(request, "gebco", basemaps.GEBCO_LAYERS, basemaps.gebco_wms, "GEBCO")


@require_GET
def phyloserver_tile(request, layer, level, x, y):
    """한반도 지질도 타일 — `phyloserver/<레이어>/<레벨>/<x>_<y>.png` (026).

    카카오 격자의 번호 그대로 phyloserver 에 넘긴다. 같은 서버의 파일이라
    캐시에 담지 않는다. 없는 자리는 빈 타일이다."""
    name, level, x, y = f"phyloserver:{layer}", int(level), int(x), int(y)
    if _lab_only(name) or not phyloserver.valid_scan_tile(name, level, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    try:
        png = phyloserver.get_scan_tile(name, level, x, y)
    except phyloserver.PhyloserverError as exc:
        log.warning("phyloserver 타일을 받지 못했다 (%s %s/%s_%s): %s", name, level, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    if png is None:
        png = tiles.blank_tile(256, 256)
    return _tile(png)


@require_GET
def peninsula_tile(request, layer, z, x, y):
    """한반도 지질도 음영판·민판 타일 — `peninsula/<레이어>/<z>/<x>/<y>.webp` (027·028).

    `manage.py build_peninsula` 가 잘라 둔 파일을 내주기만 한다. 캐시에 담지 않는다 —
    이미 우리 디스크의 타일이다. 잘라 둔 것이 없으면 안내 타일, 바다는 빈 타일이다."""
    name, z, x, y = f"peninsula:{layer}", int(z), int(x), int(y)
    sheet = peninsula.SHEETS.get(name)
    if _lab_only(name) or sheet is None or not sheet.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    if not sheet.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_PENINSULA), store=False)
    data = sheet.read_tile(z, x, y)
    version = _dir_version(sheet.tiles_dir())
    if data is None:
        return _immutable(request, _tile(tiles.blank_tile(256, 256)), version)
    return _immutable(request, _tile(data, content_type="image/webp"), version)


@require_GET
def ibcso_tile(request, layer, z, x, y):
    """남극 해저·빙저 지형 타일 — `ibcso/<bed|ice>/<z>/<x>/<y>.webp` (047). 격자는 GeoMAP 의 3031.

    `manage.py build_ibcso` 가 잘라 둔 파일을 내주기만 한다. 캐시에 담지 않는다 — 이미 우리
    디스크의 타일이다. 잘라 둔 것이 없으면 안내 타일, 자료 밖(남위 50° 북쪽)은 빈 타일이다."""
    z, x, y = int(z), int(x), int(y)
    sheet = ibcso.SHEETS.get(f"ibcso:{layer}")
    if sheet is None or not ibcso.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    if not sheet.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_IBCSO), store=False)
    data = sheet.read_tile(z, x, y)
    version = _dir_version(sheet.tiles_dir())
    if data is None:
        return _immutable(request, _tile(tiles.blank_tile(256, 256)), version)
    return _immutable(request, _tile(data, content_type="image/webp"), version)


@require_GET
def ibcso_tid_tile(request, z, x, y):
    """IBCSO 자료 출처(TID) 타일 — `ibcso/tid/<z>/<x>/<y>.png` (071). 격자는 해저지형 배경과 같다.
    잘라 둔 파일을 내주기만 한다. 잘라 두지 않았으면 안내 타일, 자료 밖은 빈 타일이다."""
    z, x, y = int(z), int(x), int(y)
    if not ibcso.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    if not ibcso.tid_available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_IBCSO), store=False)
    data = ibcso.read_tid_tile(z, x, y)
    return _immutable(request, _tile(data if data is not None else tiles.blank_tile(256, 256)),
                      _dir_version(ibcso.tid_tiles_dir()))


@require_GET
def admap_tile(request, z, x, y):
    """남극 자력 이상 타일 — `admap/<z>/<x>/<y>.webp` (wetherilli 262). `manage.py build_admap` 이 잘라 둔 것을 내주기만 한다.
    잘라 두지 않았으면 안내 타일, 자료 밖은 빈 타일이다"""
    z, x, y = int(z), int(x), int(y)
    if not admap.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    if not admap.available():
        return _tile(tiles.notice_tile(256, 256, msg("자력 이상 자료(ADMAP-2)가 서버에 없다")), store=False)
    data = admap.read_tile(z, x, y)
    version = _dir_version(admap.tiles_dir())
    if data is None:
        return _immutable(request, _tile(tiles.blank_tile(256, 256)), version)
    return _immutable(request, _tile(data, content_type="image/webp"), version)


@require_GET
@browser_cached
def admap_info(request):
    """누른 자리의 자력 이상 — `admap/info/?lat=&lon=` (wetherilli 262). `/featureinfo/` 의 꼴로 낸다"""
    lang = i18n.lang_of(request)
    ll = _latlon(request)
    if ll is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    nt = admap.value_at(*ll)
    if nt is None:
        return JsonResponse({"features": []})
    props = {"자력 이상 (nT)": nt}
    return JsonResponse({"features": [{"props": i18n.props_en(props) if lang == "en" else props}]})


def _latlon(request):
    """`?lat=&lon=` → (위도, 경도). 없거나 틀리면 None."""
    try:
        lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
    except (KeyError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 360):
        return None
    return lat, lon


@require_GET
def ibcso_depth(request):
    """누른 자리의 수심·표고 — `ibcso/depth/?lat=&lon=` (070). 잘라 둔 수치 격자에서 읽는다.
    `{"bed": 해저·빙저 m, "ice": 얼음 위 m, "tid": 자료 출처}` — 없는 것은 빠진다. 자료 밖이면 빈 것이다."""
    ll = _latlon(request)
    if ll is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), i18n.lang_of(request))}, status=400)
    got = ibcso.depths({0: ll}).get(0, {})
    tid = ibcso.tid_at({0: ll}).get(0)
    if tid is not None:
        got["tid"] = i18n.t(ibcso.tid_label(tid), i18n.lang_of(request))
    return JsonResponse(got)


@require_GET
@browser_cached
def ibcso_info(request):
    """TID 레이어의 속성 — `ibcso/info/?lat=&lon=` (071). `/featureinfo/` 의 꼴(`features[].props`)로 낸다."""
    lang = i18n.lang_of(request)
    ll = _latlon(request)
    if ll is None:
        return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
    code = ibcso.tid_at({0: ll}).get(0)
    if code is None:
        return JsonResponse({"features": []})
    props = {"자료 출처": i18n.t(ibcso.tid_label(code), lang), "TID": code}
    depth = ibcso.depths({0: ll}).get(0, {})
    if "bed" in depth:
        props["해저·빙저 (m)"] = depth["bed"]
    return JsonResponse({"features": [{"props": i18n.props_en(props) if lang == "en" else props}]})


#: 3D 가 다시 편 타일을 받는 줌. 멀리서는 원본을 수십 장 모아야 해 묻지 않는다
WARP_ZOOMS = (5, 17)
#: GeoMAP 은 대륙 전체를 한눈에 볼 때도 얹는다 — 3D 의 "지질 레이어" 로 고르기 때문이다 (040).
#: 줌 3 이면 타일 한 장이 경도 45° 라 원본 몇 장이면 된다
GEOMAP_WARP_ZOOMS = (3, 17)
#: GeoMAP 이 덮는 것은 남위 60° 남쪽이다(`data/geomap_layers.json` 의 bbox) — 그 북쪽은 그리지 않는다
GEOMAP_NORTH = -60.0
#: 3D 의 남극 배경 IBCSO(051) — 대륙을 한눈에 보는 줌 2 부터. 남위 50° 남쪽만 덮는다
IBCSO_WARP_ZOOMS = (2, 17)


@require_GET
def warp_tile(request, upstream, layer, z, x, y, retina=None):
    """평면 격자 타일을 3857 로 다시 편 것 — `warp/<상류>/<레이어>/<z>/<x>/<y>.png` (3D 가 쓴다).
    `@2x` 면 512 px — 3D 의 "지질 레이어" 는 512 px 타일로 받는다.

    3D(MapLibre)는 3857 만 받아 5179(음영판·민판)·5181(스캔판)·3031(GeoMAP·IBCSO) 격자를 못 얹는다.
    요청마다 원본을 모아 편다(`warp.py`, 0.1 초 남짓). 편 것은 캐시에 담지 않는다 — 원본이 우리
    디스크(음영판)거나 같은 서버의 파일(스캔판, 026 이 캐시를 두지 않은 까닭 그대로)이거나,
    2D 와 함께 쓰는 GeoMAP 타일 캐시다."""
    z, x, y = int(z), int(x), int(y)
    size = 512 if retina else 256
    name = layer if upstream == "geomap" else f"{upstream}:{layer}"
    lang = i18n.lang_of(request)
    zooms = {"geomap": GEOMAP_WARP_ZOOMS, "ibcso": IBCSO_WARP_ZOOMS, "admap": IBCSO_WARP_ZOOMS}.get(upstream, WARP_ZOOMS)
    if _lab_only(name) or not (zooms[0] <= z <= zooms[1]) or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), lang)}, status=404)
    if name in peninsula.SHEETS:
        sheet = peninsula.SHEETS[name]
        if not sheet.available():
            return _tile(tiles.notice_tile(size, size, tiles.NO_PENINSULA), store=False)
        grid = warp.peninsula_grid(sheet)
    elif phyloserver.knows_scan(name):
        grid = warp.kakao_grid(phyloserver.SCAN_LEVELS, phyloserver.SCAN_ORIGIN, phyloserver.SCAN_TOP,
                               lambda level, tx, ty: phyloserver.get_scan_tile(name, level, tx, ty))
    elif upstream == "geomap" and name in geomap.LAYERS:
        if warp.south_of(z, y) > GEOMAP_NORTH:
            return _tile(tiles.blank_tile(size, size))
        if not geomap.available():
            return _tile(tiles.notice_tile(size, size, tiles.NO_DATA), store=False)
        grid = warp.geomap_grid(lambda level, tx, ty: _geomap_png(name, level, tx, ty)[0])
    elif name == "ibcso:tid":
        # IBCSO 자료 출처(071) — 2D 의 타일(GeoMAP 격자) 그대로 편다 (wetherilli 335)
        if warp.south_of(z, y) > elevation.IBCSO_NORTH:
            return _tile(tiles.blank_tile(size, size))
        if not ibcso.tid_available():
            return _tile(tiles.notice_tile(size, size, tiles.NO_IBCSO), store=False)
        grid = warp.polar_grid(ibcso.read_tid_tile, ibcso.MAX_ZOOM, ibcso.valid_tile)
    elif name == admap.NAME:
        # ADMAP-2 자력 이상(wetherilli 262) — 남위 60° 남쪽, 줌 4 까지 잘라 둔 WebP (wetherilli 335)
        if warp.south_of(z, y) > GEOMAP_NORTH:
            return _tile(tiles.blank_tile(size, size))
        if not admap.available():
            return _tile(tiles.notice_tile(size, size, msg("자력 이상 자료(ADMAP-2)가 서버에 없다")), store=False)
        grid = warp.polar_grid(admap.read_tile, admap.MAX_ZOOM, admap.valid_tile)
    elif upstream == "ibcso" and name in ibcso.SHEETS:
        if warp.south_of(z, y) > elevation.IBCSO_NORTH:
            return _tile(tiles.blank_tile(size, size))
        sheet = ibcso.SHEETS[name]
        if not sheet.wide_available():
            return _tile(tiles.notice_tile(size, size, tiles.NO_IBCSO), store=False)
        grid = warp.ibcso_grid(sheet)
    else:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), lang)}, status=404)
    # 편 것을 담는다 — 원본의 판이 열쇠에 든다(음영판·IBCSO 는 잘라 둔 폴더의 때, GeoMAP 은 자료의 판과 RENDERER).
    # 스캔판(phyloserver)은 담지 않는다 — 원본을 하루만 믿는 같은 서버의 연구실 자료라(026) 편 것만 오래 남으면 어긋난다
    key = _warp_key(name, upstream, z, x, y, size)
    if key:
        hit = tilecache.get(key)
        if hit is not None:
            return _tile(hit, cached=True)
    try:
        png = warp.render(grid, z, x, y, size)
    except (phyloserver.PhyloserverError, geomap.GeomapError, OSError, ValueError) as exc:
        log.warning("다시 펴지 못했다 (%s %s/%s/%s): %s", name, z, x, y, exc)
        return _tile(tiles.notice_tile(size, size, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    png = png or tiles.blank_tile(size, size)
    if key:
        tilecache.put(key, png)
    return _tile(png)


#: 다시 펴는 법(`warp.py`)을 고치면 올린다 — 담아 둔 편 것을 버리고 새로 편다
WARP_RENDERER = "1"


def _warp_key(name, upstream, z, x, y, size):
    """편 타일의 캐시 열쇠. 원본의 판을 모르면(스캔판, 파일 없음) None — 담지 않는다."""
    if name in peninsula.SHEETS:
        version = _dir_version(peninsula.SHEETS[name].tiles_dir())
    elif upstream == "geomap":
        version = geomap_version()
    elif upstream == "ibcso" and name in ibcso.SHEETS:
        version = _dir_version(ibcso.SHEETS[name].wide_dir())
    elif name == "ibcso:tid":
        version = _dir_version(ibcso.tid_tiles_dir())
    elif name == admap.NAME:
        version = _dir_version(admap.tiles_dir())
    else:
        return None
    if not version:
        return None
    return tilecache.key_text("warp", f"{name}/{version}/r{WARP_RENDERER}/{z}/{x}/{y}/{size}")


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@require_GET
@browser_cached
def gsj_info(request):
    """`?layer=gsj:geology&lat=35.36&lon=138.73` — 누른 자리의 속성. 팝업이 받는
    꼴(`features`)은 `/featureinfo/` 와 같다."""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if not gsj.knows(name) or lat is None or lon is None or not gsj.LAYERS[name]["info"]:
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "features": []},
                            status=400)
    # 1e-5° 는 1 m 남짓이다. 같은 자리를 다시 누르면 상류를 타지 않는다
    key = tilecache.key_text("gsj-info", f"{name}/{lat:.5f},{lon:.5f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"row": gsj.point_legend(name, lat, lon)}
        except gsj.GsjError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("GSJ 속성을 읽지 못했다: %s", exc)
                error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
                return JsonResponse({"error": error, "features": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    row = raw.get("row")
    if not row:
        return JsonResponse({"features": []})
    props = gsj.friendly(row, lang)
    if lang == "en":
        props = i18n.props_en(props)
    return JsonResponse({"features": [{"id": row.get("symbol", ""), "props": props}]})


@require_GET
def kigam50k_rose(request):
    """`?lat=&lon=` 누른 자리의 도폭, 또는 `?bbox=서,남,동,북` 고른 범위의 층리·엽리·편리·절리 장미도 (wetherilli 197).

    각도를 칸으로 센 것만 준다(`kigam50k.rose`) — 화면이 SVG 로 그린다. 받아 둔 파일을 읽고 상류를 타지 않는다.
    jikhanjung P01 §5 의 5 단계다. 도폭은 누른 자리에서 가장 가까운 자세 기호의 도폭이다."""
    lang = i18n.lang_of(request)
    if not kigam50k.available():
        return JsonResponse({"error": i18n.t(msg("5만 지질도의 자세 기호 파일이 없다"), lang)}, status=503)
    sheet = None
    if request.GET.get("bbox"):
        parts = [_float(v) for v in request.GET["bbox"].split(",")]
        if len(parts) != 4 or None in parts or parts[0] >= parts[2] or parts[1] >= parts[3]:
            return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang)}, status=400)
        rows, _ = kigam50k.within(*parts, limit=10 ** 6)
    else:
        lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
        if lat is None or lon is None:
            return JsonResponse({"error": i18n.t(msg("lat·lon 이 없다"), lang)}, status=400)
        sheet = kigam50k.sheet_at(lon, lat)
        if sheet is None:
            return JsonResponse({"sheet": None, "n": {}, "fetched": kigam50k.fetched_on()})
        rows = kigam50k.in_sheet(sheet[0])
    data = kigam50k.rose(rows)
    data.update(sheet={"no": sheet[0], "name": sheet[1]} if sheet else None, fetched=kigam50k.fetched_on())
    return JsonResponse(data)


@require_GET
def kigam50k_attitudes(request):
    """`?bbox=서,남,동,북` — 그 범위의 층리·엽리·편리·절리 자리와 값 (jikhanjung 004).

    5만 지질도 타일에 그림으로 박힌 자세 기호를 누를 수 있게 하려는 것이다. 받아 둔
    파일(`kigam50k`)을 읽고 상류를 타지 않는다. 파일이 없으면 빈 목록 — 뷰어는 돈다.
    """
    lang = i18n.lang_of(request)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "points": []}, status=400)
    west, south, east, north = parts
    if not kigam50k.available():
        return JsonResponse({"points": [], "truncated": False, "available": False})
    points, cut = kigam50k.within(west, south, east, north)
    response = JsonResponse({"points": points, "truncated": cut, "available": True,
                             "fetched": kigam50k.fetched_on()})
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


@require_GET
def gsj_geonavi(request):
    """지질도Navi 판 목록 (wetherilli 171). 1 849 판이라(60 KB 남짓, gzip) 지도 화면에 싣지 않고 일본·동아시아 탭이
    판 목록을 펼 때 받는다. 씨앗(`data/gsj_geonavi_layers.json`)에서 오므로 상류를 타지 않는다."""
    return JsonResponse(gsj.client_geonavi(i18n.lang_of(request)), json_dumps_params={"ensure_ascii": False})


@require_GET
@browser_cached
def gsj_legend(request):
    """`?layer=gsj:geology&bbox=서,남,동,북&z=9` — 보는 범위의 범례 칸들.

    원본은 범례가 2 416 칸이라 그림 한 장으로 줄 수 없다. 화면이 보는 범위에
    든 것만 물어 HTML 로 그린다. 간략판(14 칸)은 범위를 보지 않고 통째로 준다.
    범위는 소수 둘째 자리(1 km 남짓)로 잘라 캐시가 맞게 한다.
    """
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    spec = gsj.LAYERS.get(name)
    if not spec or not spec["legend"]:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    bbox, z = None, _int(request.GET.get("z"), spec["max"])
    if spec["legend"] == "extent":
        parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
        if len(parts) != 4 or None in parts:
            return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
        bbox = [round(v, 2) for v in parts]
    key = tilecache.key_text("gsj-legend", f"{name}/{bbox}/z{z if bbox else ''}")
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = gsj.extent_legend(name, bbox, z)
        except gsj.GsjError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("GSJ 범례를 받지 못했다 (%s): %s", name, exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []},
                                    status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    shown = [gsj.legend_row(r, lang) for r in rows[:gsj.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


@require_GET
@browser_cached
def gsmma_legend(request):
    """`?layer=gsmma:geology_50k&bbox=서,남,동,북` — 대만 지질도의 보는 범위 범례 (wetherilli 142).

    상류가 범례 그림을 주지 않아 문이 지층 면과 그림을 맞대어 떠 온다(`gsmma.extent_legend`). 칸마다 견본 조각이
    든다. 범위는 소수 둘째 자리로 잘라 캐시가 맞게 한다 — 일본(`gsj_legend`)과 같다. 너무 넓으면 422 로 들어오라고 한다.
    """
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in gsmma.LEGENDS:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    span = gsmma.LEGENDS[name]["span"]
    if bbox[2] - bbox[0] > span or bbox[3] - bbox[1] > span:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("gsmma-legend", f"{name}/{bbox}")
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = gsmma.extent_legend(name, bbox)
        except gsmma.GsmmaError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("대만 범례를 받지 못했다 (%s): %s", name, exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    shown = [gsmma.legend_row(r, lang) for r in rows[:gsmma.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


def ingemmet_tile_key(name, z, x, y):
    """페루 캐시 타일의 열쇠. `manage.py prewarm` 도 이것으로 담는다."""
    return tilecache.key_text("ingemmet", f"{name}/{z}/{x}/{y}")


@require_GET
def ingemmet_tile(request, sheet, z, x, y):
    """페루 지질도 — `ingemmet/<판>/<z>/<x>/<y>.png`. 상류의 REST 캐시(`tile/{z}/{y}/{x}`)를 중계한다 (wetherilli 195).
    단층·습곡(222)은 같은 주소로 상류의 `export` 를 그 칸만큼 받는다.
    캐시 밖(바다·나라 밖)은 투명한 빈 타일이고, 그것도 담는다 — 다시 물을 까닭이 없다"""
    name, z, x, y = f"{ingemmet.PREFIX}{sheet}", int(z), int(x), int(y)
    if not ingemmet.valid_tile(name, z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = ingemmet_tile_key(name, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = ingemmet.get_tile(name, z, x, y)
    except ingemmet.IngemmetError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("페루 타일을 받지 못했다 (%s %s/%s/%s): %s", name, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    png = png if png is not None else tiles.blank_tile(256, 256)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
@browser_cached
def ingemmet_info(request):
    """`?layer=ingemmet:50k&lat=-12.05&lon=-77.0` — 누른 자리의 속성 (wetherilli 195). 팝업이 받는 꼴은 `/featureinfo/` 와 같다."""
    lang = i18n.lang_of(request)
    name = ingemmet.base_of(request.GET.get("layer", ""))       # 지질 단위만의 판은 통합판에 묻는다 (wetherilli 234)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if ingemmet.knows_resource(name) and lat is not None and lon is not None:
        return _ingemmet_resource_info(request, name, lat, lon, lang)
    if not ingemmet.knows(name) or lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "features": []}, status=400)
    # 1e-5° 는 1 m 남짓이다. 같은 자리를 다시 누르면 상류를 타지 않는다
    key = tilecache.key_text("ingemmet-info", f"{name}/{lat:.5f},{lon:.5f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"row": ingemmet.point_attributes(name, lat, lon)}
        except ingemmet.IngemmetError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("페루 속성을 읽지 못했다: %s", exc)
                error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
                return JsonResponse({"error": error, "features": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    row = raw.get("row")
    if not row:
        return JsonResponse({"features": []})
    props = ingemmet.friendly(row, lang)
    if lang == "en":
        props = i18n.props_en(props)
    return JsonResponse({"features": [{"id": props.get("기호", ""), "props": props}]})



def _ingemmet_resource_info(request, name, lat, lon, lang):
    """페루 광물 산지·광상·광화대(wetherilli 277) — 점은 누른 둘레(`r`°, 화면이 8 픽셀만큼 보낸다)의 것, 면은 그 점을 품은 것"""
    radius = round(min(0.5, max(1e-4, _float(request.GET.get("r")) or 0.01)), 4)
    key = tilecache.key_text("ingemmet-resource", f"{name}/{lat:.5f},{lon:.5f}/{radius}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"rows": ingemmet.resource_attributes(name, lat, lon, radius)}
        except ingemmet.IngemmetError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("페루 광물 속성을 읽지 못했다: %s", exc)
                error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
                return JsonResponse({"error": error, "features": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    out = []
    for row in raw.get("rows") or []:
        props = ingemmet.resource_friendly(name, row, lang)
        if lang == "en":
            props = i18n.props_en(props)
        out.append({"id": props.get("이름", props.get("Name", "")), "props": props})
    return JsonResponse({"features": out})

@require_GET
@browser_cached
def ingemmet_legend(request):
    """`?layer=ingemmet:50k&bbox=서,남,동,북` — 페루 지질도의 보는 범위 범례 (wetherilli 195).

    범위 안의 단위는 통계 질의로, 색은 칠하기 규칙(`ingemmet.colors`, 한 번 받아 담는다)에서. 꼴은 브라질(`sgb_legend`)과 같다"""
    lang = i18n.lang_of(request)
    name = ingemmet.base_of(request.GET.get("layer", ""))       # 지질 단위만의 판은 통합판의 범례 (wetherilli 234)
    if not ingemmet.knows(name):
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    span = ingemmet.LAYERS[name]["span"]
    if bbox[2] - bbox[0] > span or bbox[3] - bbox[1] > span:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("ingemmet-legend", f"{name}/{bbox}")
    rows = (_cached_json(key) or {}).get("rows")
    try:
        if rows is None:
            rows = ingemmet.extent_legend(name, tuple(bbox))
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
        table = ingemmet.colors(name)
    except ingemmet.IngemmetError as exc:
        log.info("페루 범례를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    shown = [ingemmet.legend_row(name, r, table, lang) for r in rows[:ingemmet.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


@require_GET
@browser_cached
def cgs_legend(request):
    """`?layer=cgs:geology_1m` — 남아공 1:100만의 범례 목록 (wetherilli 209). WMS 가 꺼져 REST `legend` 를 칸마다 이름·견본으로 낸다.
    범례는 지도 자료가 아니라 칸 이름이라 캐시에 담는다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if not cgs.knows(name):
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    key = tilecache.key_text("cgs-legend", name)
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = cgs.legend_rows(name)
        except cgs.CgsError as exc:
            log.info("남아공 범례를 받지 못했다 (%s): %s", name, exc)
            return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse({"rows": rows})


@require_GET
@browser_cached
def dinamige_legend(request):
    """`?layer=dinamige:2` — 우루과이 지질도의 범례 목록 (wetherilli 196). WMS 의 그림 범례가 비어(18×18) ArcGIS REST 의
    `legend` 를 받아 칸마다 이름·시대·견본으로 낸다. 화면은 일본·대만의 범례와 같은 꼴로 그린다. 받은 것은 캐시에 담는다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in dinamige.LEGEND_LAYERS:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    key = tilecache.key_text("dinamige-legend", name)
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = dinamige.legend_rows(name)
        except dinamige.DinamigeError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("우루과이 범례를 받지 못했다 (%s): %s", name, exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse({"rows": rows})


@require_GET
@browser_cached
def mris_legend(request):
    """`?layer=mris:geology:1` — 몽골 지질도의 범례 목록 (wetherilli 221). 그림 범례는 칸이 255 라 ArcGIS REST 의 `legend` 를 받아
    칸마다 지수·풀린 시대·견본으로 낸다. 꼴과 캐시는 우루과이(`dinamige_legend`)와 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in mris.LEGEND_LAYERS:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    key = tilecache.key_text("mris-legend", name)
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = mris.legend_rows(name)
        except mris.MrisError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("몽골 범례를 받지 못했다 (%s): %s", name, exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    if lang == "ko":
        rows = [dict(r, age=i18n.age_ko(r["age"]) if r.get("age") else "") for r in rows]
    return JsonResponse({"rows": rows})


#: 목록 범례를 내는 문 — `legend_rows(이름)` 과 `LEGEND_LAYERS` 를 갖는다 (wetherilli 228)
LIST_LEGENDS = (jmg, dmr, calgs, georep, bas, usstates, geus, bgs)


@require_GET
@browser_cached
def list_legend(request):
    """`?layer=dmr:rock_units` — ArcGIS REST `legend` 를 목록으로 낸 범례 (wetherilli 228). 우루과이·몽골의 꼴을 문 여럿이 함께 쓰는 길이다.
    문이 견본까지 받아 담아 두므로 여기서는 담지 않는다. 시대는 한국어판이면 옮긴다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    mod = next((m for m in LIST_LEGENDS if name in m.LEGEND_LAYERS), None)
    if mod is None:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    try:
        rows = mod.legend_rows(name)
    except UPSTREAM_ERRORS as exc:
        log.info("목록 범례를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    if lang == "ko":
        rows = [dict(r, age=i18n.age_ko(r["age"]) if r.get("age") else "") for r in rows]
    return JsonResponse({"rows": rows})


@require_GET
@browser_cached
def esdm_legend(request):
    """`?layer=esdm:geology&bbox=서,남,동,북` — 인도네시아 지질도의 보는 범위 범례 (wetherilli 243). REST 통계로 범위 안의 단위를 세고
    색은 칠하기 규칙에서 찾는다(`esdm.extent_legend`·`esdm.colors`). 꼴은 사우디(`sgs_legend`)와 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in esdm.LAYERS:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    if bbox[2] - bbox[0] > esdm.SPAN or bbox[3] - bbox[1] > esdm.SPAN:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("esdm-legend", f"{name}/{bbox}")
    held = _cached_json(key)
    try:
        if held is None:
            held = {"rows": esdm.extent_legend(tuple(bbox))}
            tilecache.put(key, json.dumps(held, ensure_ascii=False).encode("utf-8"), ".json")
        table = esdm.colors()
    except esdm.EsdmError as exc:
        log.info("인도네시아 범례를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    shown = [esdm.legend_row(r, table, lang) for r in held["rows"][:esdm.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(held["rows"]) - len(shown))})


@require_GET
@browser_cached
def sigeom_legend(request):
    """`?layer=sigeom:generale&bbox=서,남,동,북` — 퀘벡 지질의 보는 범위 범례 (wetherilli 337). WFS 의 면 색(`COUL_REMPL_HEXA`)으로
    단위를 센다(`sigeom.extent_legend`). 꼴은 사우디(`sgs_legend`)와 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in sigeom.LEGEND:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    span = sigeom.legend_span(name)
    if bbox[2] - bbox[0] > span or bbox[3] - bbox[1] > span:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("sigeom-legend", f"{name}/{bbox}/{lang}")
    held = _cached_json(key)
    if held is None:
        try:
            held = {"rows": sigeom.extent_legend(name, tuple(bbox), lang)}
        except sigeom.SigeomError as exc:
            log.info("퀘벡 범례를 받지 못했다 (%s): %s", name, exc)
            return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        tilecache.put(key, json.dumps(held, ensure_ascii=False).encode("utf-8"), ".json")
    shown = held["rows"][:sigeom.MAX_LEGEND]
    return JsonResponse({"rows": shown, "more": max(0, len(held["rows"]) - len(shown))})


@require_GET
@browser_cached
def sgs_legend(request):
    """`?layer=sgs:geology&bbox=서,남,동,북` — 사우디 지질도의 보는 범위 범례 (wetherilli 227). 칠하기 규칙의 두 열(`Symbol`·`Label`)로
    범위 안의 단위를 센다. 꼴은 호주(`ga_legend`)와 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if not sgs.knows(name):
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    if bbox[2] - bbox[0] > sgs.SPAN or bbox[3] - bbox[1] > sgs.SPAN:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("sgs-legend", f"{name}/{bbox}")
    held = _cached_json(key)
    try:
        if held is None:
            held = {"rows": sgs.extent_legend(tuple(bbox))}
            tilecache.put(key, json.dumps(held, ensure_ascii=False).encode("utf-8"), ".json")
        table = sgs.swatches()
    except sgs.SgsError as exc:
        log.info("사우디 범례를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    shown = [sgs.legend_row(r, table, lang) for r in held["rows"][:sgs.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(held["rows"]) - len(shown))})


@require_GET
@browser_cached
def ga_legend(request):
    """`?layer=ga:lithostratigraphy&bbox=서,남,동,북` — 호주 지질도의 보는 범위 범례 (wetherilli 212). 범위가 넓으면 1:250만 판,
    좁으면 1:100만 판의 단위를 센다 — 상류가 그 축척에 그리는 판과 같게. 꼴은 페루(`ingemmet_legend`)와 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in ga.legend_layers():
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    if bbox[2] - bbox[0] > ga.SPAN or bbox[3] - bbox[1] > ga.SPAN:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("ga-legend", f"{name}/{bbox}")
    held = _cached_json(key)
    try:
        if held is None:
            rows, table = ga.extent_legend(name, tuple(bbox))
            held = {"rows": rows, "table": table}
            tilecache.put(key, json.dumps(held, ensure_ascii=False).encode("utf-8"), ".json")
    except ga.GaError as exc:
        log.info("호주 범례를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    shown = [ga.legend_row(r, held["table"], lang) for r in held["rows"][:ga.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(held["rows"]) - len(shown))})


@require_GET
@browser_cached
def austates_legend(request):
    """`?layer=gsq:state&bbox=서,남,동,북` — 호주 주 판의 보는 범위 범례 (wetherilli 225·232). 빅토리아는 GeoServer 의 빈 규칙 빼기,
    퀸즐랜드는 REST 통계와 칠하기 규칙, 남호주는 WFS 와 SLD 의 규칙으로 뜬다(`austates.extent_legend`). 꼴은 브라질(`sgb_legend`)과 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    upstream = name.split(":", 1)[0]
    if not austates.knows(upstream, name) or not austates.is_unit(upstream, name):
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    span = austates.LEGEND_SPAN[upstream]
    if bbox[2] - bbox[0] > span or bbox[3] - bbox[1] > span:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("austates-legend", f"{name}/{bbox}/{lang}")
    rows = _cached_json(key)
    if rows is None:
        try:
            rows = austates.extent_legend(upstream, name, tuple(bbox), lang)
        except austates.AuStatesError as exc:
            log.info("호주 주 판 범례를 받지 못했다 (%s): %s", name, exc)
            return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        tilecache.put(key, json.dumps(rows, ensure_ascii=False).encode("utf-8"), ".json")
    shown = rows[:austates.MAX_LEGEND]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


@require_GET
@browser_cached
def sgm_legend(request):
    """`?layer=sgm:8&bbox=서,남,동,북` — 멕시코 지질도의 보는 범위 범례 (wetherilli 206). 꼴은 페루(`ingemmet_legend`)와 같다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in sgm.legend_layers():
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    if name in sgm.BREAKS:
        # 원소 이상 지점(wetherilli 233) — 범례는 칠하기 구간이라 보는 범위와 무관하다
        try:
            return JsonResponse({"rows": sgm.breaks(name), "more": 0, "fixed": True})
        except sgm.SgmError as exc:
            log.info("멕시코 범례를 받지 못했다 (%s): %s", name, exc)
            return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    span = sgm.legend_span(name)
    if bbox[2] - bbox[0] > span or bbox[3] - bbox[1] > span:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("sgm-legend", f"{name}/{bbox}")
    rows = (_cached_json(key) or {}).get("rows")
    try:
        if rows is None:
            rows = sgm.extent_legend(name, tuple(bbox))
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
        table = sgm.colors(name)
    except sgm.SgmError as exc:
        log.info("멕시코 범례를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    shown = [sgm.legend_row(r, table, lang) for r in rows[:sgm.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


@require_GET
@browser_cached
def iige_legend(request):
    """`?layer=iige:geologia_general&bbox=서,남,동,북` — 에콰도르 지질도의 보는 범위 범례 (wetherilli 198). 꼴은 페루(`ingemmet_legend`)와 같다"""
    lang = i18n.lang_of(request)
    if not iige.knows(request.GET.get("layer", "")):
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    if bbox[2] - bbox[0] > iige.SPAN or bbox[3] - bbox[1] > iige.SPAN:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("iige-legend", str(bbox))
    rows = (_cached_json(key) or {}).get("rows")
    try:
        if rows is None:
            rows = iige.extent_legend(tuple(bbox))
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
        table = iige.colors()
    except iige.IigeError as exc:
        log.info("에콰도르 범례를 받지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
    shown = [iige.legend_row(r, table) for r in rows[:iige.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


@require_GET
@browser_cached
def sgb_legend(request):
    """`?layer=sgb:1m&bbox=서,남,동,북` — 브라질 지질도의 보는 범위 범례 (wetherilli 191).

    범례 그림이 225×46 700 이라 GeoServer 에 그 범위에 칠해진 칸만 묻는다(`sgb.extent_legend`). 이름·시대는 모아 둔
    이름표(`fetch_sgb_units`)가 있으면 붙는다. 범위는 대만(`gsmma_legend`)처럼 소수 둘째 자리로 잘라 캐시가 맞게 한다"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name not in sgb.legend_layers():
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    bbox = [round(v, 2) for v in parts]
    span = sgb.legend_span(name)
    if bbox[2] - bbox[0] > span or bbox[3] - bbox[1] > span:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []},
                            status=422)
    key = tilecache.key_text("sgb-legend", f"{name}/{bbox}")
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        west, south = tilegrid.lonlat_to_3857(bbox[0], bbox[1])
        east, north = tilegrid.lonlat_to_3857(bbox[2], bbox[3])
        try:
            rows = sgb.extent_legend(name, (west, south, east, north))
        except sgb.SgbError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("브라질 범례를 받지 못했다 (%s): %s", name, exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    units = sgb.load_units().get(name) or {}
    shown = [sgb.legend_row(r, units, lang) for r in rows[:sgb.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


def _immutable(request, response, version: str):
    """주소의 판(`?v=`)이 지금 판과 같으면 브라우저가 오래 들고 있게 한다 (wetherilli 151).

    판이 바뀌면 카탈로그가 주는 주소가 바뀌므로 옛 그림을 붙들 일이 없다. `?v=` 가 없거나 옛 판이면(옛 화면이 열려 있다)
    지금 그림을 하루짜리로 낸다 — 옛 주소에 새 그림을 오래 묶지 않는다. 안내 타일(`no-store`)은 건드리지 않는다
    """
    if (version and request.GET.get("v") == version and settings.TILE_IMMUTABLE_SECONDS > 0
            and response.get("Cache-Control", "").startswith("public")):
        response["Cache-Control"] = f"public, max-age={settings.TILE_IMMUTABLE_SECONDS}, immutable"
    return response


def _dir_version(path) -> str:
    """미리 잘라 둔 타일 폴더의 판 — 폴더의 고친 때. `build_*` 가 새 폴더를 만들어 바꿔 끼우므로 다시 구우면 바뀐다."""
    try:
        return format(int(Path(path).stat().st_mtime), "x")
    except (OSError, TypeError, ValueError):
        return ""


def _stamp(*parts) -> str:
    """판을 이루는 것들(그리는 법·파일의 판·구운 날) → 주소에 넣을 짧은 판. 하나라도 비면(파일이 없다) 빈 판이다."""
    if any(p in (None, "") for p in parts):
        return ""
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]


def _file_stamp(path) -> str:
    """우리 디스크(`/srv/GSM/db/…`)에 구워 둔 파일의 판 — 크기와 고친 때. 다시 구우면 바뀐다."""
    try:
        st = Path(path).stat()
    except (OSError, TypeError, ValueError):
        return ""
    return f"{st.st_size:x}-{int(st.st_mtime):x}"


_content_stamps = {}


def _content_stamp(path) -> str:
    """저장소에 든 자료 파일(`data/*.json`)의 판 — 내용의 해시. 이미지를 새로 구울 때마다 고친 때가 바뀌므로
    고친 때를 쓰면 판마다 주소와 캐시가 다 바뀐다. 해시는 고친 때가 바뀔 때만 다시 센다."""
    try:
        st = Path(path).stat()
    except (OSError, TypeError, ValueError):
        return ""
    key = (str(path), st.st_size, st.st_mtime_ns)
    hit = _content_stamps.get(key)
    if hit is None:
        try:
            hit = hashlib.sha1(Path(path).read_bytes()).hexdigest()[:10]
        except OSError:
            return ""
        _content_stamps[key] = hit
    return hit


def tile_versions(page: str) -> dict:
    """화면(JS)이 주소를 짓는 타일의 판 — 레이어 갈래 → 판 (wetherilli 183). 화면이 `?v=` 로 붙여 `_immutable` 을 탄다.

    판은 **그 타일의 서버 캐시 열쇠에 든 것과 같은 것**으로 센다 — 그리는 법(`RENDERER`)과 파일의 판. 그래야 파일을 다시
    굽거나 그리는 법을 고치면 주소도 캐시도 함께 바뀐다. 상류에서 받은 것(Trek·Macrostrat …)은 싣지 않는다 — 판이 없다."""
    if page == "moon":
        return {"orig": moonmap_version()}
    if page == "mars":
        return {"orig": marsmap_version()}
    if page == "mercury":
        return {"geology": mercurymap_version()}
    if page == "map":
        return {name.split(":", 1)[1]: _dir_version(sheet.tiles_dir()) if sheet.available() else ""
                for name, sheet in ibcso.SHEETS.items()}
    if page == "earth":
        return {"paleo": paleo_version(), "coast": paleocoast_version(), "fossils": fossils_version(),
                "fossildensity": fossils_version() + fossils.DENSITY_RENDERER,
                "volcanoes": volcanoes_version(), "pleistocene": volcanoes_version("pleistocene"), "quakes": quakes_version(), "recentquakes": recentquakes_version(), "neotoma": neotoma_version(),
                "crust": crust_version(), "ne": ne_version(), "icemargins": icemargins_version(),
                "glaciers": glaciers_version(),
                "impacts": impacts_version(),
                "faults": faults_version(),
                "minerals": minerals_version(),
                "stress": stress_version(),
                "tectonics": tectonics_version(),
                "seaage": seafloor_version("age"), "sediment": seafloor_version("sediment"),
                "glim": glim_version(), "heatflow": heatflow_version()}
    return {}


def moonmap_version() -> str:
    return _stamp(moonmap.RENDERER, _file_stamp(moonmap.data_file()))


def marsmap_version() -> str:
    return _stamp(marsmap.RENDERER, _file_stamp(marsmap.data_file()))


def mercurymap_version() -> str:
    return _stamp(mercurymap.RENDERER, _file_stamp(mercurymap.data_file()))


def paleo_version() -> str:
    return _stamp(paleo.RENDERER, _content_stamp(settings.PALEOMAP_FILE))


def paleocoast_version() -> str:
    return _stamp(paleocoast.RENDERER, _file_stamp(paleocoast.path()))


def fossils_version() -> str:
    conn = fossils.db()
    built = conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone()[0] if conn is not None else ""
    return _stamp(fossils.RENDERER, built, _file_stamp(fossils.path()))


def volcanoes_version(kind: str = "holocene") -> str:
    return _stamp(volcanoes.RENDERER, volcanoes.fetched(kind), _file_stamp(volcanoes.path(kind)))


def quakes_version() -> str:
    return _stamp(quakes.RENDERER, quakes.built(), _file_stamp(quakes.path()))


def recentquakes_version() -> str:
    """최근 지진 (wetherilli 292) — 매시 새 피드를 받으면 판이 바뀌어 주소가 바뀐다"""
    return _stamp(recentquakes.RENDERER, recentquakes.generated())


def neotoma_version() -> str:
    return _stamp(paleoeco.RENDERER, paleoeco.built(), _file_stamp(paleoeco.path()))


def glim_version() -> str:
    return _stamp(glim.RENDERER, _content_stamp(settings.GLIM_FILE))


def heatflow_version() -> str:
    return _stamp(heatflow.RENDERER, heatflow.built(), _file_stamp(heatflow.path()))


def seafloor_version(kind: str) -> str:
    return _stamp(seafloor.RENDERER, *(_content_stamp(p) for p in seafloor.files(kind)[::2]))


def stress_version() -> str:
    return _stamp(stress.RENDERER, stress.built(), _file_stamp(stress.path()))
def tectonics_version() -> str:
    return _stamp(tectonics.RENDERER, _content_stamp(settings.TECTONICS_FILE))


def minerals_version() -> str:
    return _stamp(minerals.RENDERER, minerals.built(), _file_stamp(minerals.path()))


def faults_version() -> str:
    return _stamp(faults.RENDERER, _content_stamp(settings.FAULTS_FILE))


def impacts_version() -> str:
    return _stamp(impacts.RENDERER, _content_stamp(settings.IMPACTS_FILE), paleo.RENDERER)


def glaciers_version() -> str:
    return _stamp(glaciers.RENDERER, glaciers.built(), _file_stamp(glaciers.path()))


def crust_version() -> str:
    return _stamp(crust.RENDERER, _content_stamp(settings.CRUST_FILE))


def ne_version() -> str:
    return _stamp(naturalearth.RENDERER, _content_stamp(settings.EARTH_WATER_FILE), _content_stamp(settings.EARTH_ICE_FILE))


def icemargins_version() -> str:
    return _stamp(icemargins.RENDERER, _content_stamp(settings.ICE_MARGINS_FILE))


def _versioned_url(url: str, version: str) -> str:
    """타일 주소에 판을 붙인다. 판을 모르면(파일이 없다) 붙이지 않는다 — 빈 판은 길게 두지 않는다."""
    return f"{url}?v={version}" if version else url


def sim3534_version() -> str:
    """대앤틸리스 타일 주소의 판 — 구운 파일의 때와 그리는 법 (wetherilli 254)"""
    if not caribmap.available():
        return ""
    return f"{int(caribmap.data_file().stat().st_mtime)}r{caribmap.RENDERER}"


@require_GET
def sim3534_tile(request, sheet, z, x, y):
    """대앤틸리스 지질도 — `sim3534/<units|faults>/<z>/<x>/<y>.png` (wetherilli 254). 우리 파일에서 그린다.
    그린 것은 캐시에 담는다 — 열쇠에 판(파일의 때·`caribmap.RENDERER`)이 들어 다시 구우면 새 것이 보인다"""
    lang = i18n.lang_of(request)
    name, z, x, y = f"{caribmap.PREFIX}{sheet}", int(z), int(x), int(y)
    if not caribmap.knows(name) or not caribmap.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), lang)}, status=404)
    if not caribmap.available():
        return _tile(tiles.notice_tile(256, 256, msg("대앤틸리스 지질도 파일이 서버에 없다")), store=False)
    key = tilecache.key_text("sim3534", f"{name}/{sim3534_version()}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _immutable(request, _tile(hit, cached=True), sim3534_version())
    try:
        png = caribmap.render_tile(name, z, x, y)
    except (caribmap.CaribMapError, OSError, ValueError) as exc:
        log.warning("대앤틸리스 타일을 그리지 못했다 (%s %s/%s/%s): %s", name, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.SLOW if metatile.slow(exc) else tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    return _immutable(request, _tile(png), sim3534_version())


@require_GET
@browser_cached
def sim3534_info(request):
    """`?layer=sim3534:units&lat=18.2&lon=-66.4` — 누른 자리의 단위 (wetherilli 254). 팝업이 받는 꼴은 `/featureinfo/` 와 같다"""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if request.GET.get("layer") != "sim3534:units" or lat is None or lon is None:
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "features": []}, status=400)
    if not caribmap.available():
        return JsonResponse({"error": i18n.t(msg("대앤틸리스 지질도 파일이 서버에 없다"), lang), "features": []}, status=503)
    unit = caribmap.identify(lon, lat)
    if not unit:
        return JsonResponse({"features": []})
    props = caribmap.friendly(unit, lang)
    if lang == "en":
        props = i18n.props_en(props)
    return JsonResponse({"features": [{"id": unit["label"], "props": props}]})


@require_GET
@browser_cached
def sim3534_legend(request):
    """`?layer=sim3534:units&bbox=서,남,동,북` — 보는 범위의 단위 (wetherilli 254). 단층은 갈래 다섯의 고정 목록"""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if name == "sim3534:faults":
        return JsonResponse({"rows": caribmap.fault_legend(lang), "more": 0, "fixed": True})
    if name != "sim3534:units":
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
    if len(parts) != 4 or None in parts:
        return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
    if parts[2] - parts[0] > caribmap.LEGEND_SPAN or parts[3] - parts[1] > caribmap.LEGEND_SPAN:
        return JsonResponse({"error": i18n.t(msg("범위가 넓다 — 더 들어오면 범례가 뜬다"), lang), "rows": []}, status=422)
    if not caribmap.available():
        return JsonResponse({"error": i18n.t(msg("대앤틸리스 지질도 파일이 서버에 없다"), lang), "rows": []}, status=503)
    rows = caribmap.extent_legend(*parts, lang=lang)
    shown = rows[:caribmap.MAX_LEGEND]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


def geomap_version() -> str:
    """GeoMAP 타일 주소의 판 — 자료의 판과 그리는 법. 캐시 열쇠(`geomap_tile_key`)와 같은 둘이다"""
    return f"{geomap.data_version()}r{geomap.RENDERER}" if geomap.available() else ""


def _tile(png: bytes, *, cached: bool = False, store: bool = True, content_type: str = "image/png"):
    """안내 타일과 캐시에서 꺼낸 타일을 같은 문으로 내보낸다.

    안내 타일은 `store=False` 다 — 브라우저가 들고 있으면 인증키가 생긴 뒤에도
    "키가 없다" 가 계속 뜬다. 캐시에서 꺼낸 것은 진짜 지도이므로 평소대로 둔다.
    """
    if png[:2] == b"\xff\xd8":        # 캐시에 JPEG 가 든 것(PGC 경사, wetherilli 099) — 바이트를 보고 가른다
        content_type = "image/jpeg"
    response = HttpResponse(png, content_type=content_type)
    if store and settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    else:
        response["Cache-Control"] = "no-store"
    response["X-GSM-Cache"] = "hit" if cached else "bypass"
    return response


@require_GET
@browser_cached
def feature_info(request):
    """`GetFeatureInfo` 중계. 팝업이 쓸 만큼만 추려 돌려준다.

    상류가 주는 속성 이름은 이미 한국어다(`지층명`·`지질시대`·`대표암석`).
    그래서 번역표를 두지 않고 **받은 차례 그대로** 보낸다 — 상류가 열을
    더하면 팝업에도 저절로 는다. 기하는 버린다. 팝업에 쓰지 않는데
    폴리곤 좌표가 한 응답에 수천 개씩 실려 오기 때문이다.
    """
    lang = i18n.lang_of(request)
    params = kigam.clean_params(request.GET)
    params.setdefault("feature_count", "5")

    # 속성도 담아 둔다. 같은 자리를 다시 누르면 상류를 타지 않는다 —
    # 지도 범위와 누른 픽셀이 같아야 맞으므로 타일만큼 자주 맞지는 않는다
    cache_key = tilecache.key_for("info", params)
    door = _Door(_upstream_of(params.get("query_layers") or params.get("layers")))
    data = None if door.nostore else _cached_json(cache_key)
    if data is None:
        if not door.ready:
            data = None if door.nostore else _cached_json(cache_key, stale=True)
            if data is None:
                return JsonResponse({"error": i18n.t(door.not_ready_message(), lang), "features": []},
                                    status=503)
        else:
            try:
                data = door.get_feature_info(params)
            except UPSTREAM_ERRORS as exc:
                data = _cached_json(cache_key, stale=True)
                if data is None:
                    log.warning("속성을 읽지 못했다: %s", exc)
                    error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
                    return JsonResponse({"error": error, "features": []},
                                        status=502)
            else:
                if not door.nostore:
                    _store_json(cache_key, data)

    # 같은 것이 여러 번 온다. 지질도는 폴리곤이 겹쳐 놓인 자리가 많고,
    # 클릭 한 점이 아니라 몇 픽셀 둘레를 물어보기 때문이다. 사람에게는
    # "여기가 무엇인가" 한 답이면 되므로 **속성이 같은 것은 하나로 친다.**
    features, seen = [], set()
    for feature in (data.get("features") or []):
        if _is_noise(feature.get("id", "")):
            continue
        props = {k: v for k, v in (feature.get("properties") or {}).items()
                 if v not in (None, "", "null")}
        if not props:
            continue
        mark = tuple(sorted((k, str(v)) for k, v in props.items()))
        if mark in seen:
            continue
        seen.add(mark)
        props = {k: _split_links(v) for k, v in props.items()}
        if door.name == "geusarc":
            props = geus.arc_friendly(props, lang)     # 그린란드 지질구 (wetherilli 259)
        elif door.name == "geus":
            props = geus.friendly(props)          # gu_name → 지질 단위 …
        elif door.name == "vworld":
            # riv_nm → 하천명 …. 토양도처럼 레이어마다 뜻이 다른 열이 있어 레이어를 넘긴다
            props = vworld.friendly(props, params.get("query_layers") or "")
        elif door.name == "ccop":
            props = gsj.ccop_friendly(props, lang)   # code → 지질기호 …, 시대를 옮긴다
        elif door.name == "gsjows":
            props = gsj.gsjows_friendly(props, lang)  # 1:200만 — 설명을 시대(일본어에서 옮긴다)와 암상으로 (wetherilli 316)
        elif door.name == "gsmma":
            props = gsmma.friendly(props, lang)      # Name → 지층명 …, 시대를 중국어에서 옮긴다
        elif door.name == "emodnet":
            props = emodnet.friendly(props, lang)    # 마흔 남짓한 열에서 추린다. 시대를 옮긴다
        elif door.name == "ngu":
            props = ngu.friendly(props)              # 노르웨이어 열 이름 → 한국어. 그리지 않은 칸은 비운다
        elif door.name in ("esdm", "jmg", "mgb", "dmr"):
            # 동남아(wetherilli 228) — 값은 그 나라 말·영어 그대로, 시대만 옮긴다(인도네시아어 표·태국 기호·영어 다듬기)
            props = {"esdm": esdm, "jmg": jmg, "mgb": mgb, "dmr": dmr}[door.name].friendly(props, lang)
        elif door.name == "sgs":
            props = sgs.friendly(props, lang)        # 사우디 — 이름·암석은 영어 그대로, 기(ICS)만 옮긴다 (wetherilli 227)
        elif door.name == "gsiindia":
            props = gsiindia.friendly(props, lang)   # 인도 — 단위 이름은 영어 그대로, 시대만 옮긴다 (wetherilli 226)
        elif door.name == "mris":
            props = mris.friendly(props, lang)       # 몽골 — 영어 열을 쓰고 시대는 층서 지수에서 푼다 (wetherilli 221)
        elif door.name == "gns":
            props = gns.friendly(props, lang)        # 뉴질랜드 — 이름·암석은 영어 그대로, 시대는 숫자 나이에서 고른다 (wetherilli 218)
        elif door.name == "sgu":
            props = sgu.friendly(props, lang)        # 스웨덴 — 1:100만은 영어 열, 5만은 스웨덴어 그대로 (wetherilli 213)
        elif door.name == "natt":
            props = natt.friendly(props, lang)       # 아이슬란드 — 1:60만의 부호를 범례 이름으로, 시대를 옮긴다 (wetherilli 216)
        elif door.name == "gtk":
            props = gtk.friendly(props, lang)        # ROCK_NAME_ → 암석 …, 시대를 옮긴다
        elif door.name == "bgsgi":
            props = bgs.geoindex_friendly(props, lang)   # 영국 광산·광물 산지 (wetherilli 258)
        elif door.name == "bgs":
            props = bgs.friendly(props, lang)        # LEX_D → 지층명 …, 시대를 옮긴다
        elif door.name == "brgm":
            props = brgm.friendly(props)             # DESCR → 암상. 값은 프랑스어 그대로
        elif door.name == "cgmw":
            props = brgm.cgmw_friendly(props, lang)   # 아프리카 1:1000만 — ICS 시대는 옮기고 암석은 영어 그대로 (wetherilli 207)
        elif door.name == "cgs":
            props = cgs.friendly(props, lang)         # 남아공 — 층서·시대·암석, 값은 영어 그대로 (wetherilli 209)
        elif door.name == "gsn":
            props = bgs.gsn_friendly(props, lang)     # 나미비아 — 연대·층서·암석 (wetherilli 209)
        elif door.name == "bumigeb":
            props = bgs.bumigeb_friendly(props, lang)     # 부르키나파소 — 기호·설명·암석, 프랑스어 그대로 (wetherilli 246)
        elif door.name == "aga":
            props = bgs.aga_friendly(props, lang)     # 나라마다 다른 `…GLG` 열이 암상이다 (wetherilli 207)
        elif door.name == "gsni":
            props = bgs.friendly(props, lang)        # BGS 와 같은 열(LEX_D …)
        elif door.name == "egdi":
            props = egdi.friendly(props, lang)       # 암상 판의 INSPIRE 열 → 암상·지질시대·제공 기관 (wetherilli 177)
        elif door.name == "bgr":
            props = bgr.friendly(props, lang)        # 독일 판은 독일어 그대로, IGME5000 은 시대만 옮긴다 (wetherilli 217)
        elif door.name in ("igme", "gsi"):
            props = igme.friendly(props, lang) if door.name == "igme" else gsi.friendly(props)   # 값은 그 나라 말 그대로
        elif door.name == "sgc":
            props = sgc.friendly(props, lang)        # 남미 판의 ICS 시대는 옮기고, 콜롬비아 판의 값은 에스파냐어 그대로
        elif door.name == "ga":
            props = ga.friendly(props, lang)         # 호주 — 시대만 옮기고 이름·설명은 영어 그대로 (wetherilli 212)
        elif door.name in ("gsq", "gsv", "gssa", "mrt", "gsnsw"):
            props = austates.UPSTREAMS[door.name][0].friendly(props, lang)     # 호주의 주 판 — 시대만 옮긴다 (wetherilli 225)
        elif door.name in ("ispra", "lneg", "swisstopo"):
            # 이탈리아·포르투갈·스위스(wetherilli 211) — 열 이름만 한국어로, 값은 그 나라 말 그대로
            props = {"ispra": ispra, "lneg": lneg, "swisstopo": swisstopo}[door.name].friendly(props, lang)
        elif door.name == "sgm":
            props = sgm.friendly(props, lang)        # 멕시코 — 시대만 옮기고 암상·지층은 에스파냐어 그대로 (wetherilli 206)
        elif door.name == "mrdata":
            props = mrdata.friendly(props, lang)     # 미국 — 값은 영어 그대로, 알래스카의 시대만 옮긴다 (wetherilli 205)
        elif door.name == "iige":
            props = iige.friendly(props, lang)       # 에콰도르 — 값은 에스파냐어 그대로 (wetherilli 198)
        elif door.name == "georep":
            props = georep.friendly(props, lang)     # 누벨칼레도니 — 값은 프랑스어 그대로, 1:5만의 기·절만 옮긴다 (wetherilli 260)
        elif door.name == "ineter":
            props = ineter.friendly(props, lang)     # 니카라과 — 값은 스페인어 그대로, 시대만 옮긴다 (wetherilli 242)
        elif door.name in ("skgs", "nsgs", "ags"):
            props = {"skgs": skgs, "nsgs": nsgs, "ags": ags}[door.name].friendly(props, lang)   # 캐나다 주 판 둘째 — 시대만 옮긴다 (wetherilli 235)
        elif door.name in ("geosphere", "pig", "tno", "dov", "spw"):
            # 유럽(wetherilli 237) — 값은 그 나라 말 그대로, 시대만 옮긴다(`i18n.age_local`)
            props = {"geosphere": geosphere, "pig": pig, "tno": tno, "dov": dov, "spw": spw}[door.name].friendly(props, lang)
        elif door.name in usstates.DOORS:
            props = usstates.friendly(props, lang)   # 네바다·워싱턴·오리건 — 시대만 옮긴다 (wetherilli 291)
        elif door.name in ("bcgs", "calgs"):
            # 브리티시컬럼비아·캘리포니아(wetherilli 231) — 값은 영어 그대로, 시대만 옮긴다
            props = {"bcgs": bcgs, "calgs": calgs}[door.name].friendly(props, lang)
        elif door.name in ("sigeom", "ygs"):
            # 퀘벡(프랑스어 값 그대로)·유콘(ICS 영어 시대는 옮긴다) (wetherilli 210)
            props = {"sigeom": sigeom, "ygs": ygs}[door.name].friendly(props, lang)
        elif door.name in ("nrcan", "ogs"):
            # 캐나다(wetherilli 204) — 열 이름은 한국어로, 지질시대(ICS 영어)는 한국어판에서 옮긴다. 암상·층서는 영어 그대로
            props = {"nrcan": nrcan, "ogs": ogs}[door.name].friendly(props, lang)
        elif door.name == "sgb":
            props = sgb.friendly(props, lang)        # 브라질 — 포르투갈어 시대만 옮기고 이름·설명은 그대로 (wetherilli 191)
        elif door.name in ("segemar", "dinamige"):
            # 아르헨티나·우루과이(wetherilli 196) — 열 이름만 한국어로, 값은 에스파냐어 그대로
            props = {"segemar": segemar, "dinamige": dinamige}[door.name].friendly(props, lang)
        elif door.name == "npolar":
            # NAME → 이름 …, 한국어판이면 지질시대(영문 ICS)를 옮긴다
            props = npolar.friendly(props, lang)
        if not props:                                # 추리고 나니 남은 것이 없다(NGU 의 그리지 않은 칸)
            continue
        if lang == "en":
            # 캐시에는 상류가 준 한국어 그대로 두고, 내보낼 때만 옮긴다
            props = i18n.props_en(props)
        features.append({"id": feature.get("id", ""), "props": props})
        if len(features) >= MAX_FEATURES:
            break
    return JsonResponse({"features": features})


def _cached_json(key: str, *, stale: bool = False):
    raw = tilecache.get(key, ".json", stale=stale)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _store_json(key: str, data: dict) -> None:
    """기하를 떼고 담는다. 팝업이 쓰지 않는 폴리곤 좌표가 대부분이다."""
    slim = dict(data)
    slim["features"] = [{k: v for k, v in f.items() if k != "geometry"}
                        for f in (data.get("features") or [])]
    tilecache.put(key, json.dumps(slim, ensure_ascii=False).encode("utf-8"),
                  ".json")


@require_GET
def legend(request):
    """레이어 범례 이미지. 레이어 패널에서 펼쳐 볼 때 부른다."""
    layer = request.GET.get("layer", "")
    if not layer:
        return JsonResponse({"error": i18n.t(msg("layer 가 없다"), i18n.lang_of(request))}, status=400)

    if layer in geomap.LAYERS:
        return _geomap_legend(request, layer)
    if phyloserver.knows_scan(layer) or layer in peninsula.LAYERS:
        # 한반도 지질도(026·027)는 범례를 따로 주지 않는다. KIGAM 에 묻지 않게 여기서 막는다
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), i18n.lang_of(request))}, status=404)

    # 범례도 캐시한다. 타일보다 훨씬 드물게 부르지만 한 장이 수십 KB 라
    # (25만 지질도 범례는 223x5218 픽셀이다) 다시 받을 까닭이 없다.
    cache_key = tilecache.key_for("legend", {"layer": layer})
    hit = tilecache.get(cache_key)
    if hit is not None:
        response = HttpResponse(hit, content_type="image/png")
        response["X-GSM-Cache"] = "hit"
        if settings.TILE_CACHE_SECONDS > 0:
            response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
        return response

    door = _Door(_upstream_of(layer))
    try:
        if not door.ready:
            raise kigam.UpstreamError("인증키가 없다", status=503)
        content, ctype = door.get_legend(layer)
    except UPSTREAM_ERRORS as exc:
        old = tilecache.get(cache_key, stale=True)
        if old is not None:
            response = HttpResponse(old, content_type="image/png")
            response["X-GSM-Cache"] = "stale"
            # 상류가 못 줘 낸 옛것이다 — 한 시간만 들고 있게 해 곧 다시 묻는다 (wetherilli 158)
            response["Cache-Control"] = "public, max-age=3600"
            return response
        log.info("범례를 받지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": str(exc)},
                            status=503 if not door.ready else 502)
    if door.name not in NO_STORE:
        tilecache.put(cache_key, content)
    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 벡터 레이어 — 모양을 받아 우리가 그린다 (단층, devlog 020) ──────────
#
# 타일이 아니라 모양(GeoJSON)을 준다. 브라우저가 선 색·굵기를 정하므로 어느
# 줌에서도 또렷하고, 누르면 그 선의 속성이 곧장 뜬다(상류를 다시 안 탄다).
#
# **위경도 1° 칸으로 나눠 받는다.** 화면 범위를 그대로 상류에 넘기면 지도를
# 조금만 움직여도 열쇠가 달라져 캐시가 맞지 않는다. 칸으로 자르면 같은 칸은
# 한 번만 받고, 칸 이름이 좌표계와 상관없어 극지 투영에서도 같은 것을 쓴다.
# 남한은 1° 칸 50 개 남짓이고, 한 칸에 단층이 많아야 수백 개(수십 KB)다.

#: 칸의 크기(도). 화면(`map.js`)은 카탈로그의 `cell` 로 이 값을 받는다
VECTOR_CELL = 1
#: 칸을 달리 두는 레이어 (077). 지하수 등수심선은 1° 칸에서 1000 줄(WFS 상한 — 더 달라면 오류를 준다)에 잘린다.
#: 0.25° 칸도 김포·인천 둘레에서 잘려 0.125° 로 줄였다 — 그 칸을 넷으로 나누니 많은 것이 902 줄(2026-09-30). 선의 점이
#: 5 m 마다 찍혀 무거워 솎아(`thin`, 도 — 50 m 남짓, 칸 하나가 절반 밑으로) 담고, 줌 11 부터 받는다(`minZoom`).
#: 관정 자료로 그은 등치선이라 50 m 보다 정확하지 않다. 칸은 1 을 2 의 거듭제곱으로 나눈 것만 쓴다 — 브라우저가
#: 더해 가며 칸 이름을 셈하는데 그래야 소수가 어긋나지 않는다
VECTOR_GRIDS = {
    "lt_l_gimsdepth": {"cell": 0.125, "thin": 0.0005, "minZoom": 11},
}


def vector_grid(name: str) -> dict:
    """레이어의 칸 — {cell, thin, minZoom}. 적지 않은 것은 1° 칸, 솎지 않음, 줌 제한 없음."""
    return {"cell": VECTOR_CELL, "thin": 0, "minZoom": 0, **VECTOR_GRIDS.get(name, {})}


def _deg(value: float) -> str:
    """칸 이름의 글자 — 127.0 은 `127`, 127.25 는 `127.25`. 1° 칸의 캐시 열쇠가 앞 판과 같다."""
    return f"{value:g}"


@require_GET
def vector(request):
    """`?layer=lt_l_gimsfault&lon=127&lat=36` — 칸 하나의 모양. 서남 모서리가 칸 이름이다."""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    grid = vector_grid(name)
    cell = grid["cell"]
    try:
        lon, lat = float(request.GET.get("lon", "")), float(request.GET.get("lat", ""))
    except ValueError:
        return JsonResponse({"error": "lon·lat"}, status=400)
    if (not (-180 <= lon < 180 and -90 <= lat < 90)
            or not (lon / cell).is_integer() or not (lat / cell).is_integer()):
        return JsonResponse({"error": "lon·lat"}, status=400)
    layer = Layer.objects.filter(name=name, kind="vector", enabled=True).first()
    if layer is None or layer.upstream != "vworld":
        return JsonResponse({"error": "layer"}, status=404)

    empty = {"type": "FeatureCollection", "features": []}
    box = layer.bbox
    if box and (lon + cell <= box[0] or lon >= box[2]
                or lat + cell <= box[1] or lat >= box[3]):
        return _vector_response(empty)             # 레이어 범위 밖이다. 상류에 묻지 않는다

    # 솎은 것은 솎은 채 담는다 — 솎는 정도가 바뀌면 열쇠도 바뀐다
    key = tilecache.key_text("vector", f"{name}|{_deg(lon)}|{_deg(lat)}|{_deg(cell)}"
                             + (f"|thin={_deg(grid['thin'])}" if grid["thin"] else ""))
    data = _cache_get(key)
    if data is None:
        try:
            if not vworld.enabled():
                raise vworld.VWorldError("VWorld 열쇠가 없다")
            data = vworld.get_features(name, lon, lat, lon + cell, lat + cell)
            if grid["thin"]:
                data = vworld.thin(data, grid["thin"])
        except vworld.VWorldError as exc:
            data = _cache_get(key, stale=True)     # 빈 자리보다 옛것이 낫다
            if data is None:
                log.warning("모양을 받지 못했다 (%s %s,%s): %s", name, lon, lat, exc)
                return JsonResponse({"error": i18n.t(msg("VWorld 가 답하지 않는다"), lang),
                                     "features": []}, status=502)
        else:
            _cache_put(key, data)

    # 팝업에 보일 이름을 곁들인다. 캐시에는 받은 그대로 두고 내보낼 때만 붙인다
    out = []
    for f in data.get("features") or []:
        props = dict(f.get("properties") or {})
        popup = vworld.friendly(props, name)
        props["_popup"] = i18n.props_en(popup) if lang == "en" else popup
        out.append(dict(f, properties=props))
    return _vector_response({"type": "FeatureCollection", "features": out})


def _vector_response(data):
    response = JsonResponse(data)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 점 레이어 (그린란드 정부 포털·NPI) ─────────────────────────────────
#
# 타일이 아니라 점을 통째로 받아 브라우저에 한 덩이로 준다 (`grportal.py` 019,
# `npolar.py` 021 — 받은 것을 줄이는 틀은 `arcpoints.py` 하나다).
# 캐시의 규칙은 타일과 같다 — 들고 있으면 묻지 않고, 3 년이 지나면 다시 묻고,
# 상류가 못 주면 옛것을 낸다. 담는 것은 feature 목록(JSON)이다.

_point_locks = {}

#: 점 레이어의 문. (알아보기, 받기, 싸기, 캐시 열쇠, 오류)
_POINT_DOORS = (
    ("grportal", grportal.knows, grportal, grportal.PortalError),
    ("npolar", npolar.knows_points, npolar, npolar.NpolarError),
    ("phyloserver", phyloserver.knows, phyloserver, phyloserver.PhyloserverError),
    # 남극 기지(054) — KPDC 지도 서버의 WFS 를 통째로
    ("kopri", kopri.knows_points, kopri, kopri.KopriError),
)
POINT_ERRORS = tuple(door[3] for door in _POINT_DOORS)


def _point_door(name: str):
    for key, knows, module, _ in _POINT_DOORS:
        if knows(name):
            return key, module
    return None, None


def _point_key(name: str) -> str:
    key, module = _point_door(name)
    return tilecache.key_text(key, module.signature(name))


def point_features(name: str, *, refresh: bool = False) -> bytes:
    """레이어 하나의 feature 목록(JSON 바이트). 못 받으면 그 문의 오류(`POINT_ERRORS`).

    같은 레이어를 두 사람이 한꺼번에 열어도 **상류에는 한 번만 묻는다** —
    2 만 점이면 열 장이다. 뒤에 온 사람은 앞사람이 받는 것을 기다린다.
    """
    _, module = _point_door(name)
    key = _point_key(name)
    # 날마다 바뀌는 상류(phyloserver 의 암맥, 026)는 하루면 다시 묻는다. 레이어마다 다른 문은
    # `fresh_seconds` 를 둔다 — 그린란드 포털의 불안정 사면은 30 일 (wetherilli 089)
    fresh = (module.fresh_seconds(name) if hasattr(module, "fresh_seconds")
             else getattr(module, "FRESH_SECONDS", None))
    if not refresh:
        hit = tilecache.get(key, ".json", max_age=fresh)
        if hit is not None:
            return hit
    lock = _point_locks.setdefault(name, threading.Lock())
    with lock:
        if not refresh:
            hit = tilecache.get(key, ".json", max_age=fresh)   # 기다리는 사이 앞사람이 담았다
            if hit is not None:
                return hit
        try:
            features = module.fetch(name)
        except POINT_ERRORS:
            old = tilecache.get(key, ".json", stale=True)
            if old is not None:
                return old
            raise
        data = json.dumps(features, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tilecache.put(key, data, ".json")
        return data


@gzip_page
@require_GET
def point_layer(request):
    """점 레이어 하나를 GeoJSON 으로. 2 만 점이 4.5 MB, 줄이면(gzip) 0.4 MB 다."""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if _lab_only(name):
        return JsonResponse({"error": i18n.t(msg("그런 점 레이어가 없다"), lang)}, status=404)
    if janmayen.knows(name):
        return _janmayen_layer(name, lang)
    if geo3al.knows(name):
        return _geo3al_layer(name, lang)
    if usgscarib.knows(name):
        return _usgscarib_layer(name, lang)
    if stri.knows(name):
        return _stri_layer(name, lang)
    if twopen.knows(name):
        return _twopen_layer(name, lang)
    if vmme.knows(name):
        return _vmme_layer(name, lang)
    if ags.knows_points(name):
        return _ags_points_layer(name, lang)
    if kopri.knows_file(name):
        return _kopri_layer(name, lang)
    if earthpoints.knows(name):
        return _earth_points_layer(request, name, lang)
    if kigam50k.knows_file(name):
        return _kigam50k_layer(name, lang)
    _, module = _point_door(name)
    # 지명은 레이어가 아니라 찾기 칸의 것이다 — 통째로 내주지 않는다
    if module is None or name in PLACE_FIELDS:
        return JsonResponse({"error": i18n.t(msg("그런 점 레이어가 없다"), lang)}, status=404)
    try:
        features = point_features(name)
    except POINT_ERRORS as exc:
        log.warning("점 레이어를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang)}, status=502)
    if module is grportal and grportal.LAYERS[name].get("slice"):
        # 전암 화학 3 만 점 — 고른 원소만 잘라 준다 (wetherilli 163)
        body = grportal.value_slice(name, features, request.GET.get("value", ""))
    else:
        body = module.body(name, features)
    response = HttpResponse(body, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


#: 스발바르 지명 8 393 — 찾기 칸이 뒤진다 (npolar.py, devlog 021)
PLACE_NAMES = "npolar:place_names"

#: 지역 → 그 지역의 지명 레이어 (wetherilli 096). 묶음 지역(북극)은 화면이 품은 지역들을 넘긴다
PLACE_SOURCES = {
    "svalbard": (PLACE_NAMES,),
    "greenland": ("grportal:place_names",),
    "antarctica": ("npolar:dml_place_names",),
}
#: 지명 레이어 → (이름 열들, 곁말 열들). 이름 열의 첫 것이 보이는 이름이다
PLACE_FIELDS = {
    PLACE_NAMES: (("name",), ("area",), None),
    "npolar:dml_place_names": (("name",), ("area",), None),
    # 그린란드는 같은 이름이 흔하다(Nuuk 라는 곶이 여럿) — 도시(BY)·마을(BYGD)·공항(FLYPL)을 앞세운다
    "grportal:place_names": (("name", "old", "da", "alt"), ("da", "kind", "mun"), ("kind", ("BY", "BYGD", "FLYPL"))),
}
#: 지명 색인을 메모리에 들고 있는 초. 그린란드는 33 000 건·수 MB 라 찾을 때마다 캐시 파일을 풀지 않는다
PLACE_INDEX_SECONDS = 3600
_place_index = {}


def _place_index_for(name: str) -> list:
    hit = _place_index.get(name)
    if hit and time.monotonic() - hit[0] < PLACE_INDEX_SECONDS:
        return hit[1]
    names, side, prefer = PLACE_FIELDS[name]
    index = arcpoints.name_index(json.loads(point_features(name)), names, side, prefer)
    _place_index[name] = (time.monotonic(), index)
    return index


@require_GET
def place_names(request):
    """지명 찾기 — 스발바르·그린란드·드로닝모드랜드. 한국의 `search/`(VWorld) 자리다. 지명을 한 번 통째로
    받아 두고 그 안에서 찾는다 — 찾을 때마다 상류에 묻지 않는다. `region` 은 쉼표로 여럿(북극 묶음)."""
    lang = i18n.lang_of(request)
    query = (request.GET.get("q") or "").strip()[:100]
    if not query:
        return JsonResponse({"results": []})
    regions = [r for r in (request.GET.get("region") or "svalbard").split(",") if r in PLACE_SOURCES]
    sources = [name for r in regions for name in PLACE_SOURCES[r]] or [PLACE_NAMES]
    index, failed = [], 0
    for name in sources:
        try:
            index += _place_index_for(name)
        except (POINT_ERRORS + (ValueError,)) as exc:
            log.warning("지명을 받지 못했다 (%s): %s", name, exc)
            failed += 1
    if failed == len(sources):
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang)}, status=502)
    return JsonResponse({"results": arcpoints.match_index(index, query)})


def _janmayen_layer(name, lang):
    """얀마옌 지질도 한 레이어 (022). 파일이 없으면 503 으로 까닭을 말한다 —
    화면은 그 글을 레이어 패널에 띄우고, 나머지는 그대로 돈다."""
    if not janmayen.available(name):
        return JsonResponse({"error": i18n.t(msg("얀마옌 지질도 자료(NPI)가 서버에 없다"), lang)},
                            status=503)
    try:
        content = janmayen.body(name, lang)
    except (janmayen.JanMayenError, OSError, ValueError) as exc:
        log.warning("얀마옌 지질도를 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("얀마옌 지질도 자료(NPI)를 읽지 못했다"), lang)},
                            status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _usgscarib_layer(name, lang):
    """USGS 카리브 지질도 한 덩이 (wetherilli 248). 처음 한 번 상류에서 받아 캐시에 30 일 둔다(`usgscarib.features`)"""
    try:
        content = usgscarib.body(name, lang)
    except usgscarib.UsgsCaribError as exc:
        log.warning("USGS 카리브 지질도를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("USGS 카리브 지질도를 받지 못했다"), lang)}, status=502)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _vmme_layer(name, lang):
    """파라과이 VMME 지질도 한 덩이 (wetherilli 256). 꼴은 `_usgscarib_layer` 와 같다"""
    try:
        content = vmme.body(name, lang)
    except vmme.VmmeError as exc:
        log.warning("파라과이 지질도를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("파라과이 지질도(VMME)를 받지 못했다"), lang)}, status=502)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _ags_points_layer(name, lang):
    """앨버타 광물 산지 한 덩이 (wetherilli 321). 꼴은 `_vmme_layer` 와 같다"""
    try:
        content = ags.points_body(name, lang)
    except ags.AgsError as exc:
        log.warning("앨버타 광물 산지를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("앨버타 광물 산지를 받지 못했다"), lang)}, status=502)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _twopen_layer(name, lang):
    """대만 지질운 열린자료 한 덩이 (wetherilli 305). 받아 둔 파일만 읽는다 — 없으면 503 (`fetch_taiwan_open`)"""
    try:
        content = twopen.body(name, lang)
    except FileNotFoundError:
        return JsonResponse({"error": i18n.t(msg("대만 지질운 열린자료가 서버에 없다"), lang)}, status=503)
    except (OSError, ValueError) as exc:
        log.warning("대만 지질운 열린자료를 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("대만 지질운 열린자료를 읽지 못했다"), lang)}, status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _stri_layer(name, lang):
    """파나마 STRI 지질도 한 덩이 (wetherilli 253). 꼴은 `_usgscarib_layer` 와 같다"""
    try:
        content = stri.body(name, lang)
    except stri.StriError as exc:
        log.warning("STRI 파나마 지질도를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("파나마 지질도(STRI)를 받지 못했다"), lang)}, status=502)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _geo3al_layer(name, lang):
    """중국 지질도(USGS geo3al) 한 레이어 (025). 꼴과 까닭은 `_janmayen_layer` 와 같다."""
    if not geo3al.available():
        return JsonResponse({"error": i18n.t(msg("중국 지질도 자료(USGS geo3al)가 서버에 없다"), lang)},
                            status=503)
    try:
        content = geo3al.body(name, lang)
    except (geo3al.Geo3alError, OSError, ValueError) as exc:
        log.warning("geo3al 을 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("중국 지질도 자료(USGS geo3al)를 읽지 못했다"), lang)},
                            status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _kopri_layer(name, lang):
    """극지연구소에서 모아 둔 것(053·055·056) — 꼴과 까닭은 `_janmayen_layer` 와 같다.
    파일은 `manage.py fetch_kopri` 가 쓴다."""
    try:
        content = kopri.file_body(name, lang)
    except FileNotFoundError:
        return JsonResponse({"error": i18n.t(msg("극지연구소 자료를 아직 모으지 않았다 (fetch_kopri)"), lang)},
                            status=503)
    except (OSError, ValueError) as exc:
        log.warning("극지연구소 자료를 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("극지연구소 자료를 읽지 못했다"), lang)}, status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if kopri.file_of(name) == "araon":
        # 아라온호 항적은 매시간 자란다 (koprifossillab 006)
        response["Cache-Control"] = f"public, max-age={kopri.ARAON_MAX_AGE}"
    elif settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _kigam50k_layer(name, lang):
    """5만 지질도의 화석산지·시료·광산·도폭 틀 (wetherilli 199, jikhanjung P01 §5) — 받아 둔 WFS 파일에서. 꼴과 까닭은
    `_kopri_layer` 와 같다. 파일은 `manage.py fetch_kigam50k` 가 쓴다."""
    try:
        content = kigam50k.layer_body(name)
    except FileNotFoundError:
        return JsonResponse({"error": i18n.t(msg("5만 구조 요소를 아직 받지 않았다 (fetch_kigam50k)"), lang)}, status=503)
    except (OSError, ValueError) as exc:
        log.warning("5만 구조 요소를 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("모아 둔 자료를 읽지 못했다"), lang)}, status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _earth_points_layer(request, name, lang):
    """지역 탭의 지구 자료 점(wetherilli 185) — 화석 산지·홀로세 화산·지진·고생태 산지를 지역의 네모만큼. 꼴과 까닭은
    `_kopri_layer` 와 같다. 모아 둔 파일에서 자를 뿐이라 상류를 타지 않는다."""
    try:
        content = earthpoints.body(name, lang)
    except FileNotFoundError:
        return JsonResponse({"error": i18n.t(earthpoints.MISSING[earthpoints.source_of(name)], lang)}, status=503)
    except (OSError, ValueError, sqlite3.Error) as exc:
        log.warning("지구 자료 점을 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("모아 둔 자료를 읽지 못했다"), lang)}, status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    # 모아 둔 파일에서 나오니 판이 있다 — 카탈로그가 준 `?v=` 가 맞으면 오래 둔다 (wetherilli 183)
    return _immutable(request, response, earthpoints.version(name))


def _geomap_legend(request, layer):
    """GeoMAP 범례는 스타일 표에서 그때그때 그린다 — 파일도 상류도 타지 않는다."""
    try:
        content, ctype = geomap.get_legend(layer)
    except (geomap.GeomapError, OSError, ValueError) as exc:
        log.info("GeoMAP 범례를 그리지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), i18n.lang_of(request))},
                            status=500)
    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 점묶음 ────────────────────────────────────────────────────────────

def _pointset_summary(ps):
    shapes = list(ps.shapes.values_list("kind", flat=True))
    elevated = ps.points.filter(elev__isnull=False).count()
    return {
        "id": ps.id,
        "name": ps.name,
        "body": ps.body,
        "color": ps.color,
        "visible": ps.visible,
        "count": ps.points.count(),
        "lines": shapes.count("line"),
        "polygons": shapes.count("polygon"),
        "elevated": elevated,
        # VWorld 둘레(074) — 물을 만한 점(대한민국 둘레)과 이미 채운 점
        "korean": _korean_points(ps).count(),
        "placed": ps.points.exclude(place={}).count(),
    }


def _body(value) -> str:
    """요청이 적은 몸. 모르는 값은 지구다 — 지구 화면은 몸을 적지 않는다 (037)."""
    return value if value in dict(PointSet.BODIES) else "earth"


def _pointset_list(body: str = "earth"):
    """한 몸의 점묶음만. 지구 화면(2D·3D)은 지구 것만, 달 화면은 달 것만 그린다 (037)."""
    return [_pointset_summary(ps) for ps in PointSet.objects.filter(body=body)]


@require_GET
def pointset_index(request):
    return JsonResponse({"pointsets": _pointset_list(_body(request.GET.get("body")))})


@require_POST
def pointset_upload(request):
    lang = i18n.lang_of(request)
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": i18n.t(msg("올린 파일이 없다"), lang)}, status=400)

    body = _body(request.POST.get("body"))
    try:
        code = request.POST.get("crs") or "4326"
        points, notes = pointsets.parse(upload.name, upload.read(),
                                        crs_code=code if code in crs.SYSTEMS else "4326",
                                        lunar=body != "earth")
    except pointsets.UploadError as exc:
        return JsonResponse({"error": i18n.t(exc.args[0], lang)}, status=400)
    except pointsets.NeedsAddresses as need:
        return _needs_addresses(need, body, lang)

    name = (request.POST.get("name") or "").strip() or upload.name.rsplit(".", 1)[0]
    color = (request.POST.get("color") or "").strip() or "#e4572e"

    with transaction.atomic():
        pointset = PointSet.objects.create(
            name=name[:120], source_filename=upload.name[:255], color=color[:7], body=body)
        Point.objects.bulk_create([
            Point(pointset=pointset, lat=p["lat"], lon=p["lon"],
                  label=p["label"][:200], props=p["props"])
            for p in points if "geometry" not in p
        ])
        Shape.objects.bulk_create([
            Shape(pointset=pointset, kind=p["kind"], geometry=p["geometry"],
                  lat=p["lat"], lon=p["lon"], label=p["label"][:200], props=p["props"])
            for p in points if "geometry" in p
        ])

    _auto_places(pointset)
    summary = _pointset_summary(pointset)
    log.info("점묶음 '%s' 생겼다 — 점 %d, 선 %d, 면 %d", pointset.name,
             summary["count"], summary["lines"], summary["polygons"])
    return JsonResponse({
        "pointset": summary,
        "notes": [i18n.t(note, lang) for note in notes],
    })


def _needs_addresses(need, body: str, lang: str):
    """위경도가 없고 주소만 있는 CSV (wetherilli 152). 점묶음을 만들지 않고 줄들을 화면에 돌려준다 — 화면이
    `pointsets/geocode/` 로 50 줄씩 나눠 좌표를 받아, 위도·경도 열을 붙인 CSV 를 다시 올린다. 올리기 한 번이 60 초에
    묶여(gunicorn) 서버가 한 번에 다 찾으면 150 줄쯤에서 끊긴다."""
    if body != "earth":
        return JsonResponse({"error": i18n.t(msg("주소로 찾는 것은 지구의 점묶음뿐이다."), lang)}, status=400)
    if not vworld.enabled():
        return JsonResponse({"error": i18n.t(msg("VWorld 열쇠가 없어 주소로 좌표를 찾지 못한다. 위경도 열을 넣어 올린다."),
                                             lang)}, status=400)
    if len(need.rows) > pointsets.MAX_ADDRESS_ROWS:
        return JsonResponse({"error": i18n.t(msg("주소로 찾는 것은 한 번에 {n}줄까지다. 나눠 올린다.",
                                                 n=pointsets.MAX_ADDRESS_ROWS), lang)}, status=400)
    return JsonResponse({"geocode": {"fields": need.fields, "column": need.column, "rows": need.rows,
                                     "blank": need.blank, "chunk": GEOCODE_CHUNK}})


#: 화면이 한 번에 보내는 주소 수. 하나에 0.1–0.2 초(2026-10-02)라 50 이면 한 요청이 10 초 안쪽이다 — 60 초 제한에서 넉넉하다
GEOCODE_CHUNK = 50


@require_POST
def pointset_geocode(request):
    """주소 몇 줄 → 좌표 (wetherilli 152). 받는 것: `{"addresses": ["…", …]}` (한 번에 `GEOCODE_CHUNK` 줄까지).
    주는 것: 같은 차례의 `{"lat", "lon", "kind", "matched"}` 또는 null(못 찾음).

    **차례로 묻는다** — 한꺼번에 묻지 않는다. VWorld 지오코더는 하루 호출 수가 정해져 있고, 같은 주소는 캐시에서 꺼낸다.
    못 찾은 것(null)도 담는다 — 같은 표를 다시 올려도 다시 묻지 않는다. VWorld 가 거절하면 거기서 멈추고 까닭을 준다"""
    lang = i18n.lang_of(request)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": i18n.t(msg("읽지 못했다"), lang)}, status=400)
    addresses = payload.get("addresses") if isinstance(payload, dict) else None
    if not isinstance(addresses, list) or not addresses or len(addresses) > GEOCODE_CHUNK:
        return JsonResponse({"error": i18n.t(msg("주소는 한 번에 {n}줄까지 보낸다", n=GEOCODE_CHUNK), lang)}, status=400)
    if not vworld.enabled():
        return JsonResponse({"error": i18n.t(msg("VWorld 열쇠가 없다"), lang)}, status=503)
    results = []
    for address in addresses:
        address = " ".join(str(address or "").split())[:200]
        key = tilecache.key_text("geocode", address)
        hit = _cached_json(key)
        if hit is not None:
            results.append(hit.get("point"))
            continue
        if usage.paused():
            return JsonResponse({"error": i18n.t(msg("상류가 바빠 잠시 멈췄다. 조금 뒤에 다시 올린다."), lang),
                                 "results": results}, status=503)
        try:
            point = vworld.geocode(address)
        except vworld.VWorldError as exc:
            log.warning("주소로 좌표를 찾지 못했다: %s", exc)
            error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
            return JsonResponse({"error": error, "results": results}, status=502)
        tilecache.put(key, json.dumps({"point": point}, ensure_ascii=False).encode("utf-8"), ".json")
        results.append(point)
    return JsonResponse({"results": results})


@require_POST
def pointset_create(request):
    """찍어 둔 점을 **목록으로 저장한다.** 구글 지도의 "장소 저장" 과 같은 자리다.

    지도에서 찍은 점은 새로 고치면 사라지는 임시 표시다. 그러다 "이건 남겨야
    겠다" 싶은 때가 오는데, 그때 파일로 내보냈다 다시 올리게 하면 아무도 안
    한다. 그래서 있는 그대로 점묶음이 되게 했다.

    받는 것: `{"name": "...", "color": "#rrggbb", "points": [{lat, lon, label}]}`
    """
    lang = i18n.lang_of(request)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": i18n.t(msg("읽지 못했다"), lang)}, status=400)

    rows = payload.get("points") or []
    shape_rows = payload.get("shapes") or []
    if not rows and not shape_rows:
        return JsonResponse({"error": i18n.t(msg("저장할 점이 없다"), lang)}, status=400)
    if len(rows) > MAX_SAVED_POINTS:
        return JsonResponse(
            {"error": i18n.t(msg("한 번에 {n}점까지 저장한다", n=MAX_SAVED_POINTS), lang)},
            status=400)

    points = []
    for row in rows:
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        points.append((lat, lon, str(row.get("label") or "")[:200]))
    # 잡은 범위·잰 선·면. 올린 GeoJSON 과 같은 거름을 탄다
    shapes = []
    for row in shape_rows[:MAX_SAVED_SHAPES]:
        geom = (row or {}).get("geometry") or {}
        if geom.get("type") not in pointsets.SHAPE_KINDS:
            continue
        try:
            shape = pointsets._shape_from(geom)
        except pointsets.UploadError as exc:
            return JsonResponse({"error": i18n.t(exc.args[0], lang)}, status=400)
        if shape:
            shape.pop("vertices")
            props = row.get("props") if isinstance(row.get("props"), dict) else {}
            shapes.append(dict(shape, label=str(row.get("label") or "")[:200], props=props))
    if not points and not shapes:
        return JsonResponse({"error": i18n.t(msg("쓸 만한 좌표가 없다"), lang)}, status=400)

    name = (payload.get("name") or "").strip() or "찍은 점"
    color = (payload.get("color") or "").strip() or "#27456f"

    with transaction.atomic():
        pointset = PointSet.objects.create(
            name=name[:120], source_filename="", color=color[:7], body=_body(payload.get("body")))
        Point.objects.bulk_create([
            Point(pointset=pointset, lat=lat, lon=lon, label=label)
            for lat, lon, label in points
        ])
        Shape.objects.bulk_create([
            Shape(pointset=pointset, kind=s["kind"], geometry=s["geometry"],
                  lat=s["lat"], lon=s["lon"], label=s["label"], props=s["props"])
            for s in shapes
        ])

    _auto_places(pointset)
    log.info("찍은 점 %d개·모양 %d개를 '%s' 로 저장했다", len(points), len(shapes), pointset.name)
    return JsonResponse({"pointset": _pointset_summary(pointset)})


#: 표고 타일에서 읽은 고도를 GeoJSON 에 싣는 이름(P03). "고도" 로 하지 않는 것은 원본의
#: `고도` 열(실측)과 부딪히지 않게 하려는 것이다. 되살리기(`pointsets.restore`)가 이 둘을 떼어
#: 제 칸으로 돌린다
ELEV_PROP, ELEV_SOURCE_PROP = "표고(DEM)", "표고 출처"


#: 남극 바다·얼음 밑 점에 IBCSO 에서 읽어 붙이는 이름(070). 저장하지 않고 부를 때마다 읽는다 — 우리 디스크의
#: 격자라 상류를 타지 않고, 판이 바뀌면 곧바로 따라간다. 되살리기가 이 이름들을 떼어 버린다
IBCSO_BED_PROP, IBCSO_ICE_PROP = "해저·빙저(IBCSO)", "얼음 두께(IBCSO)"


def _point_props(p, depth=None) -> dict:
    props = dict(p.props, **{"이름표": p.label} if p.label else {})
    if p.elev is not None:
        props[ELEV_PROP] = round(p.elev, 1)
        props[ELEV_SOURCE_PROP] = p.elev_source
    props.update(_place_props(p.place))
    if depth and "bed" in depth:
        props[IBCSO_BED_PROP] = depth["bed"]
        if "ice" in depth and depth["ice"] - depth["bed"] > 1:
            props[IBCSO_ICE_PROP] = depth["ice"] - depth["bed"]
    return props


def _pointset_features(pointset) -> dict:
    """점묶음 하나를 GeoJSON FeatureCollection 으로. 내려받기와 지울 때의 사본이 쓴다.
    지구 점묶음의 남위 50° 남쪽 점에는 IBCSO 수심·빙저를 붙인다(070)."""
    points = list(pointset.points.all())
    depths = {}
    if pointset.body == "earth":
        depths = ibcso.depths({p.id: (p.lat, p.lon) for p in points if p.lat <= ibcso.NORTH})
    return {
        "type": "FeatureCollection",
        "name": pointset.name,
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
            "properties": _point_props(p, depths.get(p.id)),
        } for p in points] + [{
            "type": "Feature",
            "geometry": s.geometry,
            "properties": dict(s.props, **{"이름표": s.label} if s.label else {}),
        } for s in pointset.shapes.all()],
    }


@require_GET
def pointset_geojson(request, pk):
    """점묶음을 GeoJSON 으로. 지도가 그릴 때도, 사람이 내려받을 때도 쓴다.

    `?download=1` 이면 파일로 내려준다. 한글 이름이 깨지지 않게 파일명을
    RFC 5987 로도 적는다.
    """
    pointset = get_object_or_404(PointSet, pk=pk)
    response = JsonResponse(_pointset_features(pointset),
                            json_dumps_params={"ensure_ascii": False})
    if request.GET.get("download"):
        from urllib.parse import quote
        stem = re.sub(r'[\\/:*?"<>|]+', "_", pointset.name).strip() or f"pointset-{pk}"
        response["Content-Type"] = "application/geo+json; charset=utf-8"
        response["Content-Disposition"] = (
            f'attachment; filename="pointset-{pk}.geojson"; '
            f"filename*=UTF-8''{quote(stem + '.geojson')}")
    return response


@require_GET
def pointset_csv(request, pk):
    """점묶음의 점을 CSV 로 내려받는다 (wetherilli 190). 엑셀이 한글을 알아보게 BOM 붙인 UTF-8 이다.

    열은 이름표·위도·경도, 올린 속성(표고·VWorld 둘레·IBCSO 수심을 붙인 GeoJSON 의 속성 그대로), 그리고 **우리 파일에서 읽는
    값**(`pointvalues`) — 지구는 GeoMAP 단위·지각 두께·가까운 화석 산지, 달·화성·수성은 그 몸의 지질도 단위다. `?extras=` 로
    갈래를 고른다(쉼표, `none` 이면 붙이지 않는다). 점이 `pointvalues.LIMIT` 를 넘으면 붙일 값을 읽지 않고 413 으로 까닭을 말한다 —
    화면은 점 수를 알고 미리 `none` 으로 부른다. 선·면(모양)은 CSV 에 담지 않는다 — GeoJSON 으로 받는다."""
    lang = i18n.lang_of(request)
    pointset = get_object_or_404(PointSet, pk=pk)
    asked = (request.GET.get("extras") or "all").strip()
    wanted = None if asked == "all" else set() if asked == "none" else set(asked.split(","))
    kinds = pointvalues.kinds(pointset.body, wanted)
    points = list(pointset.points.all())
    if kinds and len(points) > pointvalues.LIMIT:
        return JsonResponse({"error": i18n.t(msg("점이 {n} 개라 붙일 값을 읽지 않는다 — {limit} 개까지다. extras=none 으로 부른다",
                                                 n=len(points), limit=pointvalues.LIMIT), lang)}, status=413)
    depths = {}
    if pointset.body == "earth":
        depths = ibcso.depths({p.id: (p.lat, p.lon) for p in points if p.lat <= ibcso.NORTH})
    rows, keys = [], {}
    for p in points:
        props = _point_props(p, depths.get(p.id))
        label = props.pop("이름표", "")
        for k in props:
            keys.setdefault(k, None)
        rows.append((p, label, props, pointvalues.values(pointset.body, kinds, p.lat, p.lon, lang) if kinds else {}))
    extra = pointvalues.columns(pointset.body, kinds)

    # 영어판은 우리가 붙인 열만 옮긴다 — 올린 열의 이름은 그 사람의 자료다
    ours = {"이름표", "위도", "경도", ELEV_PROP, ELEV_SOURCE_PROP, IBCSO_BED_PROP, IBCSO_ICE_PROP, FAULT_PROP,
            PLACENAME_PROP, *(label for _, label in PLACE_PROPS), *extra}

    def head(name):
        return i18n.PROP_EN.get(name, name) if lang == "en" and name in ours else name

    def cell(value):
        if value is None:
            return ""
        return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    writer.writerow([head(c) for c in ["이름표", "위도", "경도", *keys, *extra]])
    for p, label, props, values in rows:
        writer.writerow([label, p.lat, p.lon, *(cell(props.get(k)) for k in keys), *(cell(values.get(c)) for c in extra)])
    from urllib.parse import quote
    stem = re.sub(r'[\\/:*?"<>|]+', "_", pointset.name).strip() or f"pointset-{pk}"
    response = HttpResponse(out.getvalue().encode("utf-8"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (f'attachment; filename="pointset-{pk}.csv"; '
                                       f"filename*=UTF-8''{quote(stem + '.csv')}")
    return response


@require_POST
def pointset_delete(request, pk):
    """지운다. **지우기 전에 기록과 사본을 남긴다** (`PointSetDeletion`)."""
    pointset = get_object_or_404(PointSet, pk=pk)
    summary = _pointset_summary(pointset)
    client = _client(request)
    with transaction.atomic():
        PointSetDeletion.objects.create(
            name=pointset.name, body=pointset.body, color=pointset.color,
            source_filename=pointset.source_filename, created_at=pointset.created_at,
            client=client, points=summary["count"], lines=summary["lines"],
            polygons=summary["polygons"], snapshot=_pointset_features(pointset))
        pointset.delete()
    log.info("점묶음 '%s' 지웠다 — 점 %d, 선 %d, 면 %d (%s)", summary["name"],
             summary["count"], summary["lines"], summary["polygons"], client)
    return JsonResponse({"ok": True})


@require_GET
def pointset_deleted(request):
    """최근 지운 점묶음 20 개. 설정의 "지금 상태" 가 부른다. 사본은 싣지 않는다."""
    return JsonResponse({"deleted": [{
        "id": d.id, "name": d.name, "body": d.body, "deleted_at": d.deleted_at.isoformat(),
        "client": d.client, "points": d.points, "lines": d.lines, "polygons": d.polygons,
        "restored": bool(d.restored_at),
    } for d in PointSetDeletion.objects.all()[:20]]})


@require_POST
def pointset_restore(request, pk):
    """지운 점묶음을 되살린다. 한 기록은 한 번만 — 두 번 누르면 두 벌이 생긴다."""
    lang = i18n.lang_of(request)
    gone = get_object_or_404(PointSetDeletion, pk=pk)
    if gone.restored_at:
        return JsonResponse({"error": i18n.t(msg("이미 되살렸다"), lang)}, status=409)
    ps, _, _ = pointsets.restore(gone)
    log.info("지운 점묶음 '%s' 을 되살렸다 (%s)", ps.name, _client(request))
    return JsonResponse({"pointset": _pointset_summary(ps)})


#: VWorld 둘레(074)를 GeoJSON·팝업에 싣는 이름. "(VWorld)" 를 붙여 원본의 `주소` 열과 부딪히지 않게 한다.
#: 되살리기(`pointsets.restore`)가 이 이름들을 떼어 제 칸(`Point.place`)으로 돌린다
PLACE_PROPS = (("road", "도로명(VWorld)"), ("parcel", "지번(VWorld)"), ("emd", "읍면동(VWorld)"),
               # 보호구역·지목·소유구분 (wetherilli 173)
               ("protected", "보호구역(VWorld)"), ("jimok", "지목(VWorld)"), ("owner", "소유구분(VWorld)"))
FAULT_PROP, PLACENAME_PROP = "가까운 단층(VWorld, m)", "둘레 지명(VWorld)"


def _place_props(place: dict) -> dict:
    out = {label: place[key] for key, label in PLACE_PROPS if place.get(key)}
    if place.get("fault_m") is not None:
        out[FAULT_PROP] = place["fault_m"]
    if place.get("place"):
        out[PLACENAME_PROP] = f"{place['place']} · {place['place_m']} m"
    return out


def _korean_points(ps):
    """VWorld 에 물을 만한 점 — 지구 점묶음의 대한민국 둘레(`vworld.KOREA_BOX`)."""
    if ps.body != "earth":
        return ps.points.none()
    w, s_, e, n = vworld.KOREA_BOX
    return ps.points.filter(lat__gte=s_, lat__lte=n, lon__gte=w, lon__lte=e)


#: 한 번의 요청 안에서 VWorld 에 묻는 점의 수. 한 점에 열 번 묻는다(넷 + 보호구역 넷 + 토지 둘, wetherilli 173). 넘으면 명령(`fill_places`)으로
PLACES_IN_REQUEST = 50
#: 올리거나 찍을 때 곧바로 묻는 점의 수. 넘으면 사람이 📍 를 누른다 — 올리기가 느려지지 않게
PLACES_AUTO = 20
#: 점과 점 사이(초). 한도를 재지 않는 빠르기로 간다(010)
PLACES_PAUSE = 0.2


def fill_places(pointset, *, only_missing: bool = False, pause: float = PLACES_PAUSE) -> tuple:
    """점묶음의 한국 점마다 VWorld 둘레를 채운다. (채운 수, 못 읽은 수). 명령과 화면이 함께 쓴다.
    다시 부르면 덮는다. 한 점이 실패해도 나머지는 간다 — 다 실패하면 첫 오류를 올린다."""
    import time
    from django.utils import timezone
    points = _korean_points(pointset)
    if only_missing:
        points = points.filter(place={})
    rows = list(points)
    filled, errors = [], []
    today = timezone.localdate().isoformat()
    for index, p in enumerate(rows):
        if index and pause:
            time.sleep(pause)
        try:
            facts = vworld.point_facts(p.lat, p.lon)
        except vworld.VWorldError as exc:
            errors.append(exc)
            continue
        p.place = dict(facts, at=today)
        filled.append(p)
    Point.objects.bulk_update(filled, ["place"])
    if rows and not filled and errors:
        raise errors[0]
    return len(filled), len(rows) - len(filled)


def _auto_places(pointset):
    """올리거나 찍은 점이 적으면 곧바로 둘레를 채운다(074). 실패해도 점묶음은 생긴다."""
    if not vworld.enabled():
        return
    n = _korean_points(pointset).count()
    if not n or n > PLACES_AUTO:
        return
    try:
        fill_places(pointset)
    except vworld.VWorldError as exc:
        log.info("둘레를 채우지 못했다 (%s): %s", pointset.id, exc)


@require_POST
def pointset_places(request, pk):
    """`POST pointsets/<번호>/places/` — 한국 점마다 주소·읍면동·가까운 단층·둘레 지명·보호구역·지목·소유구분을 채운다 (074·wetherilli 173)."""
    lang = i18n.lang_of(request)
    ps = PointSet.objects.filter(pk=pk).first()
    if ps is None:
        return JsonResponse({"error": i18n.t(msg("그런 점묶음이 없다"), lang)}, status=404)
    if not vworld.enabled():
        return JsonResponse({"error": i18n.t(msg("VWorld 열쇠가 없다"), lang)}, status=503)
    if _korean_points(ps).count() > PLACES_IN_REQUEST:
        return JsonResponse({"error": i18n.t(msg("점이 많아 화면에서 채우지 않는다 — 서버에서 "
                                                 "manage.py fill_places {id} 를 부른다", id=ps.id), lang)},
                            status=400)
    try:
        filled, missed = fill_places(ps)
    except vworld.VWorldError as exc:
        log.warning("둘레를 채우지 못했다 (%s): %s", ps.id, exc)
        return JsonResponse({"error": i18n.t(msg("VWorld 에서 받지 못했다"), lang)}, status=502)
    return JsonResponse({"filled": filled, "missed": missed, "pointset": _pointset_summary(ps)})


#: 한 번의 요청 안에서 채우는 점의 수. 넘으면 명령(`fill_elevation`)으로 채운다.
#: 극지는 한 점에 한 번 PGC 에 묻고 사이를 두어 따로 적게 둔다
ELEV_IN_REQUEST = 2000
ELEV_POLAR_IN_REQUEST = 100


#: 지구 밖의 몸 → (표고 읽기, 출처, 높이 기준). 지구의 표고 원천을 타지 않는다
BODY_ELEVATION = {
    "moon": lambda: (trek.lola_values, trek.ELEV_SOURCE, trek.ELEV_DATUM),
    "mars": lambda: (trek.mars_values, trek.MARS_ELEV_SOURCE, trek.MARS_ELEV_DATUM),
    "mercury": lambda: (trek.mercury_values, trek.MERCURY_ELEV_SOURCE, trek.MERCURY_ELEV_DATUM),
}


def fill_elevation(pointset, *, only_missing: bool = False, pause: float = elevation.PGC_PAUSE) -> tuple:
    """점묶음의 점마다 표고를 채운다. (채운 수, 못 읽은 수). 명령과 화면이 함께 쓴다.
    다시 부르면 덮는다 — 원천이 판을 올리면 출처 칸이 달라져 알아볼 수 있다(P03 §3).

    달 점묶음은 LOLA 로 간다(`trek.lola_values`, 037) — 지구의 표고 원천을 타지 않는다.
    화성 점묶음은 MOLA–HRSC 로 간다(`trek.mars_values`, 058). 수성은 MESSENGER 665 m(`trek.mercury_values`, P10)."""
    points = pointset.points.all()
    if only_missing:
        points = points.filter(elev__isnull=True)
    rows = {p.id: p for p in points}
    if pointset.body in BODY_ELEVATION:
        values, source, datum = BODY_ELEVATION[pointset.body]()
        got = values({pid: (p.lat, p.lon) for pid, p in rows.items()})
        for pid, value in got.items():
            p = rows[pid]
            p.elev, p.elev_source, p.elev_datum = round(value, 1), source, datum
        Point.objects.bulk_update([rows[pid] for pid in got], ["elev", "elev_source", "elev_datum"])
        return len(got), len(rows) - len(got)
    got = elevation.elevations({pid: (p.lat, p.lon) for pid, p in rows.items()}, pause=pause)
    for pid, (value, source) in got.items():
        p = rows[pid]
        p.elev, p.elev_source, p.elev_datum = round(value, 1), source, elevation.SOURCES[source][1]
    Point.objects.bulk_update([rows[pid] for pid in got], ["elev", "elev_source", "elev_datum"])
    return len(got), len(rows) - len(got)


@require_POST
def pointset_elevation(request, pk):
    """`POST pointsets/<번호>/elevation/` — 점마다 표고를 채운다 (P03)."""
    lang = i18n.lang_of(request)
    ps = PointSet.objects.filter(pk=pk).first()
    if ps is None:
        return JsonResponse({"error": i18n.t(msg("그런 점묶음이 없다"), lang)}, status=404)
    total = ps.points.count()
    # 극지의 한 점씩 묻기(PGC)는 지구의 일이다. 달·화성은 한 번에 100 점씩이라 극지를 가르지 않는다
    polar = 0 if ps.body != "earth" else ps.points.filter(
        Q(lat__gte=elevation.POLAR_LAT) | Q(lat__lte=-elevation.POLAR_LAT)).count()
    if total > ELEV_IN_REQUEST or polar > ELEV_POLAR_IN_REQUEST:
        return JsonResponse({"error": i18n.t(msg("점이 많아 화면에서 채우지 않는다 — 서버에서 "
                                                 "manage.py fill_elevation {id} 를 부른다", id=ps.id), lang)},
                            status=400)
    try:
        filled, missed = fill_elevation(ps)
    except (elevation.ElevationError, trek.TrekError) as exc:
        log.warning("표고를 채우지 못했다 (%s): %s", ps.id, exc)
        return JsonResponse({"error": i18n.t(msg("표고를 받지 못했다"), lang)}, status=502)
    return JsonResponse({"filled": filled, "missed": missed, "pointset": _pointset_summary(ps)})


@require_GET
def dem_tile(request, z, x, y, kind="ice"):
    """3D 의 촘촘한 지형 — Terrarium 꼴 표고 타일 (`dem/<z>/<x>/<y>.png`, `dem/bed/…`).

    남위 50° 남쪽은 IBCSO v2 수치 격자(500 m, 051)이고, 그 가운데 남위 60° 너머 줌 11 부터는 PGC
    REMA(2 m, 032)다 — REMA 의 구멍(바다)은 IBCSO 가 메운다. `bed` 는 얼음을 걷어 낸 IBCSO 해저·빙저라
    REMA(얼음 윗면)로 넘어가지 않는다. 북위 60° 너머는 PGC ArcticDEM, 일본은 국토지리원(10 m, 031).
    그 밖이거나 못 만들면 AWS 로 넘긴다(302). 3D 는 이 자리들의 타일만 여기로 부른다."""
    z, x, y = int(z), int(x), int(y)
    if not (0 <= x < 2 ** z and 0 <= y < 2 ** z) or z > elevation.POLAR_MAX_ZOOM:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    n = 2 ** z
    lon = (x + 0.5) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / n))))
    png = None
    try:
        if lat <= elevation.IBCSO_NORTH:
            if kind == "ice" and lat <= -elevation.POLAR_LAT and z >= elevation.POLAR_MIN_ZOOM:
                png = elevation.polar_terrarium(z, x, y)
            if png is None:
                png = elevation.ibcso_terrarium(kind, z, x, y)
        elif abs(lat) >= elevation.POLAR_LAT:
            if z >= elevation.POLAR_MIN_ZOOM:
                png = elevation.polar_terrarium(z, x, y)
        elif z <= elevation.GSI_ZOOM and elevation.in_japan(lat, lon):
            png = elevation.japan_terrarium(z, x, y)
    except (elevation.ElevationError, OSError, ValueError) as exc:
        log.info("표고 타일을 못 만들어 AWS 로 넘긴다 (%s/%s/%s): %s", z, x, y, exc)
        png = None
    if png is None:
        response = HttpResponse(status=302)
        response["Location"] = elevation.TERRARIUM_URL.format(z=z, x=x, y=y)
        # 넘기는 자리는 바뀌지 않는다 — 브라우저가 하루 기억하면 다시 묻지 않고 AWS 로 간다 (wetherilli 158)
        if settings.TILE_CACHE_SECONDS > 0:
            response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
        return response
    return _tile(png)


def _client(request) -> str:
    """지운 곳. nginx 가 붙여 주는 X-Real-IP 가 먼저다 (deploy/nginx)."""
    return (request.META.get("HTTP_X_REAL_IP")
            or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", ""))[:64]


# ── 주소 (VWorld) ─────────────────────────────────────────────────────
#
# KIGAM 을 타지 않는다. 문은 `vworld.py` 다. 받은 것은 타일처럼 캐시에
# 담는다 — 주소는 지질도보다도 드물게 바뀐다.

def _cache_get(key, *, stale=False):
    raw = tilecache.get(key, ".json", stale=stale)
    try:
        return json.loads(raw) if raw is not None else None
    except ValueError:
        return None


def _cache_put(key, data):
    tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")


def _vworld_cached(key, fetch, lang):
    """캐시 → VWorld → (실패하면) 늙은 캐시. 셋 다 없으면 오류 응답."""
    data = _cache_get(key)
    if data is not None:
        return data, None
    if not vworld.enabled():
        return None, JsonResponse(
            {"error": i18n.t(msg("주소 검색이 꺼져 있다 — VWorld 열쇠가 없다"), lang)}, status=503)
    try:
        data = fetch()
    except vworld.VWorldError as exc:
        old = _cache_get(key, stale=True)
        if old is not None:
            return old, None
        log.warning("VWorld 에서 받지 못했다: %s", exc)
        return None, JsonResponse(
            {"error": i18n.t(msg("VWorld 가 답하지 않는다"), lang)}, status=502)
    _cache_put(key, data)
    return data, None


@require_GET
def place_search(request):
    """주소·장소·행정구역 검색. 화면 아래 검색 칸이 부른다.

    좌표는 여기 오지 않는다 — 브라우저가 먼저 `coords/parse/` 로 물어보고,
    좌표가 아닐 때만 여기로 온다.
    """
    lang = i18n.lang_of(request)
    query = (request.GET.get("q") or "").strip()[:100]
    if not query:
        return JsonResponse({"results": []})
    data, error = _vworld_cached(tilecache.key_text("search", query),
                                 lambda: {"results": vworld.search(query)}, lang)
    return error or JsonResponse(data)


@require_GET
def whereis(request):
    """좌표 → 지번·도로명. 속성 팝업의 위경도 밑에 붙는다."""
    lang = i18n.lang_of(request)
    try:
        # 다섯째 자리(약 1 m)에서 자른다. 같은 자리를 두 번 묻지 않으려는 것이다
        lat = round(float(request.GET["lat"]), 5)
        lon = round(float(request.GET["lon"]), 5)
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": i18n.t(msg("좌표로 읽지 못했다"), lang)}, status=400)
    data, error = _vworld_cached(tilecache.key_text("whereis", f"{lat},{lon}"),
                                 lambda: vworld.reverse(lat, lon), lang)
    return error or JsonResponse(data)


# ── 좌표 ──────────────────────────────────────────────────────────────

@require_GET
def coord_parse(request):
    """찍어 넣은 좌표 한 줄을 읽는다.

    화면 아래 늘 떠 있는 좌표는 브라우저가 스스로 그린다 — 마우스가 움직일
    때마다 서버를 부를 수는 없다. 여기로 오는 것은 **사람이 입력칸에 넣고
    누른 한 번**뿐이고, 도분초·반구 글자까지 받아내는 까다로운 쪽이라
    파이썬에 두고 시험한다.
    """
    lang = i18n.lang_of(request)
    code = request.GET.get("crs", "4326")
    swapped = False
    if crs.is_planar(code):
        q = request.GET.get("q", "")
        not_read = JsonResponse({"error": i18n.t(msg("{name} 좌표로 읽지 못했다 — 한반도 밖으로 간다",
                                                     name=crs.SYSTEMS[code][0]), lang)}, status=400)
        labelled = crs.labelled_pair(q)
        if labelled:
            # 동·북 이름을 붙여 적었으면 그대로 읽는다
            lat, lon = crs.to_latlon(code, *labelled)
            if not crs.in_korea(lat, lon):
                return not_read
        else:
            nums = crs.two_numbers(q)
            found = crs.candidates(code, *nums) if nums else []
            if not found:
                return not_read
            if len(found) == 2:
                # **두 차례가 다 말이 되면 고르지 않는다.** 중부원점에서는 동·북을
                # 뒤바꿔도 둘 다 한반도 안에 떨어지는 일이 있다 — 사람이 고른다
                return JsonResponse({"candidates": [
                    {"lat": la, "lon": lo, "order": order,
                     "east": nums[0] if order == "en" else nums[1],
                     "north": nums[1] if order == "en" else nums[0]}
                    for la, lo, order in found]})
            lat, lon, order = found[0]
            swapped = order == "ne"
    else:
        pair = coords.parse(request.GET.get("q", ""))
        if pair is None:
            return JsonResponse({"error": i18n.t(msg("좌표로 읽지 못했다"), lang)}, status=400)
        lat, lon = pair
    return JsonResponse({"lat": lat, "lon": lon, "swapped": swapped,
                         "dms": coords.format_pair(lon, lat, dms=True)})


@require_GET
def coord_project(request):
    """위경도 → 고른 평면 좌표계. 팝업의 한 줄이 부른다."""
    code = request.GET.get("crs", "")
    try:
        lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "lat·lon"}, status=400)
    if not crs.is_planar(code):
        return JsonResponse({"error": "crs"}, status=400)
    east, north = crs.from_latlon(code, lat, lon)
    return JsonResponse({"crs": code, "east": round(east, 2), "north": round(north, 2)})


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
