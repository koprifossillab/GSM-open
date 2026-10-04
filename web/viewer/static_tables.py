"""정적 판(GitHub Pages)이 극지 상류를 브라우저에서 곧장 부를 때 쓰는 표 — 문이 아니다 (wetherilli 161).

서버의 문(`npolar.py`·`geus.py`·`grportal.py`·`elevation.py` 의 PGC·`emodnet.py`·`kopri.py`)이 들고 있는 명세 — 주소, 레이어
번호, 받을 열, 팝업 이름, 지질시대 낱말 — 를 **그대로 떠서** JSON 하나로 묶는다. `static-kinds.js` 가 이것을 읽어 서버가 하던
일을 브라우저에서 한다. 표를 JS 에 또 적지 않는다 — 원본은 파이썬 하나이고, 빌드(`static_site.py`)가 이것을 `static-tables.json`
으로 떠 싣는다. 상류가 바뀌어 문의 표를 고치면 정적 판도 다음 빌드에 따라온다.

여기서는 상류를 부르지 않는다(`requests` 가 없다). 연구실 내부용(`views.LAB_ONLY` 의 geo3al·phyloserver·peninsula)은 싣지 않는다.
콜롬비아 SGC 는 조건이 열린 1:50만 판만 싣는다(wetherilli 201). 극지연구소(KPDC)의 **지도 서버 레이어는 싣는다** — 사용자가 "공개 자료는 싣는다" 고 정했다(2026-10-02). 모아 둔 파일에서 그리는
KOPRI 점(시료·운석·KPDC 목록)은 여기 없다 — 굽는 쪽(`bake_static`)의 몫이다.
"""
from django.conf import settings

from . import arcpoints, elevation, emodnet, geus, grportal, i18n, kopri, npolar, sgc


def _points(spec: dict, url: str, oid: str, page: int, max_pages: int) -> dict:
    """점 레이어 하나의 명세 — `arcpoints.collect`·`compact`·`body` 를 JS 가 따라 할 만큼."""
    out = {
        "url": url, "oid": oid, "page": page, "maxPages": max_pages, "paged": spec.get("paged", True),
        "areal": bool(spec.get("areal")), "generalize": spec.get("generalize") or 0, "style": spec["style"],
        "fields": spec["fields"], "labels": arcpoints.labels(spec), "links": arcpoints.links(spec),
    }
    if "classes" in spec:
        classes = spec["classes"]
        out["classes"] = {"by": classes["by"], "numeric": bool(classes.get("numeric")),
                          "table": [[code, label, color, shape, _heads(heads)]
                                    for code, label, color, shape, heads in classes["table"]],
                          "else": list(classes["else"])}
    if spec["style"] == "value":
        # 연속값(지화학, wetherilli 159) — 원소 표와 처음 고를 원소. 원소마다 잘라 받는 것(`slice`, 전암 화학 3 만 점)은 브라우저가
        # 통째로 받기에 무거워 표시만 해 둔다 — JS 가 거절하고 굽는 쪽이 싣는다
        out["values"] = [[key, label, unit] for key, _, label, unit in grportal._table(spec)]
        out["default"] = grportal.DEFAULT_ELEMENT
        out["slice"] = bool(spec.get("slice"))
    return out


def _heads(heads):
    """갈래 표의 머리 하나 → JSON. 머리말(글자·글자 묶음)·구간(`numeric` 의 (이상, 미만))·`{"gt0": 열}`. 함수는 JS 가 못 돌린다 —
    들어오면 여기서 깨져 알아챈다(`class_of` 는 받지만 정적 판에는 글자로 적은 꼴만 간다)"""
    if callable(heads):
        raise ValueError("갈래 표에 함수가 있다 — 정적 판이 따라 하지 못한다. {'gt0': 열} 처럼 글자로 적는다")
    if isinstance(heads, dict):
        return heads
    return list(heads) if isinstance(heads, tuple) else [heads]


def _max_features() -> int:
    from . import views                  # views 가 무겁다 — 표를 뜰 때만 부른다
    return views.MAX_FEATURES


def tables() -> dict:
    npolar_points = {}
    for name, spec in npolar.POINTS.items():
        npolar_points[name] = _points(spec, npolar._point_url(spec), spec["oid"], npolar.PAGE, npolar.MAX_PAGES)
    portal_points = {}
    for name, spec in grportal.LAYERS.items():
        portal_points[name] = _points(spec, grportal._query_url(spec["service"], spec.get("layer", 0)),
                                      spec.get("oid", "FID"), grportal.PAGE, grportal.MAX_PAGES)
    return {
        "version": 1,
        # 한 번 누른 자리에서 팝업에 싣는 속성 덩이 수 — 서버의 `views.MAX_FEATURES`
        "maxFeatures": _max_features(),
        "geus": {
            "url": settings.GEUS_WMS_URL, "mapname": settings.GEUS_MAPNAME,
            "friendly": geus.FRIENDLY, "hidden": sorted(geus.HIDDEN),
        },
        "npolar": {
            "url": settings.NPOLAR_URL.rstrip("/"), "attribution": npolar.ATTRIBUTION,
            "tiles": npolar.TILES,
            # 차례가 뜻이다 — 같은 이름(`이름`)이 둘이면 앞의 것이 이긴다
            "friendly": list(npolar.FRIENDLY.items()),
            "linkProps": sorted(npolar.LINK_PROPS), "ageProps": list(npolar.AGE_PROPS),
            "points": npolar_points,
        },
        "grportal": {"points": portal_points},
        "pgc": {
            "export": elevation.PGC_EXPORT_URL, "identify": elevation.PGC_IDENTIFY_URL,
            "attribution": elevation.PGC_ATTRIBUTION,
            "layers": {name: {"service": s["service"], "srs": s["srs"], "draw": s["draw"], "read": list(s["read"]),
                              "format": s.get("format", "png32"), "min": s.get("min")}
                       for name, s in elevation.PGC_LAYERS.items()},
        },
        "emodnet": {
            "url": settings.EMODNET_WMS_URL, "attribution": emodnet.ATTRIBUTION, "prefix": emodnet.PREFIX,
            "friendly": list(emodnet.FRIENDLY),
        },
        "kopri": {
            "url": settings.KOPRI_GEO_URL.rstrip("/") + "/wms", "attribution": kopri.ATTRIBUTION,
            "wms": kopri.WMS, "projection": {name: kopri.wms_projection(name) for name in kopri.WMS},
        },
        # 콜롬비아 1:50만(wetherilli 201) — 조건이 열린 판만. 싣는 것은 굽는 사람이 고른다(`static_site.py --with colombia`)
        "sgc": {
            "url": settings.SGC_WMS_URL.rstrip("/"), "attribution": sgc.STATIC_ATTRIBUTION,
            "sheets": {sheet: sgc.SHEETS[sheet] for sheet in sgc.STATIC_SHEETS},
            "friendly": [list(pair) for pair in sgc.FRIENDLY],
        },
        # 지질시대 — 영문 ICS 값을 한국어로(`i18n.age_ko` 의 표)
        "age": {"words": i18n.AGE_WORDS_KO, "modifiers": i18n.AGE_MODIFIERS_KO, "joiners": i18n.AGE_JOINERS_KO},
        # 영어판 팝업 이름(`i18n.PROP_EN`)과 링크 이름표
        "propEn": i18n.PROP_EN, "linkEn": i18n.LINK_EN,
    }
