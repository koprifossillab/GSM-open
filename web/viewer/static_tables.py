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

from . import arcpoints, dov, elevation, emodnet, ga, geosphere, geus, grportal, i18n, kopri, mrdata, npolar, pig, sgc, sgu, spw, tno


#: `arcwms.Door` 를 쓰는 상류 가운데 정적 판에 고를 수 있게 둔 것 (wetherilli 257) — 상류 → (출처, 문들, 범례에 쓸 WMS 레이어를 고르는 손).
#: 범례 손이 None 이면 범례를 두지 않는다(서버 판도 두지 않는다). 손은 서버 문의 `get_legend` 가 고르는 것과 같아야 한다
ARC = {
    "tno": (tno.ATTRIBUTION, (tno.DOOR,), lambda wms: wms),
    "dov": (dov.ATTRIBUTION, (dov.DOOR,), lambda wms: wms),
    "spw": (spw.ATTRIBUTION, (spw.DOOR,), None),
    "geosphere": (geosphere.ATTRIBUTION, geosphere.DOORS, lambda wms: wms.split(",")[0]),
    "pig": (pig.ATTRIBUTION, pig.DOORS, lambda wms: wms.split(",")[-1]),
}


def arc_layers(upstream: str) -> set:
    """정적 판이 곧장 부를 수 있는 그 상류의 레이어 — WMS 로 도는 것만. 지오스피어 1:5만처럼 REST 로 옮기는 것은 빠진다"""
    return {name for door in ARC[upstream][1] for name in door.layers} if upstream in ARC else set()


def _arc(upstream: str) -> dict:
    attribution, doors, legend = ARC[upstream]
    return {"attribution": attribution,
            "doors": [{"url": door.url(), "layers": door.layers, "queryable": list(door.queryable),
                       "infoFormat": door.info_format, "infoParams": door.info_params} for door in doors],
            "legend": {name: legend(wms) for door in doors for name, wms in door.layers.items()} if legend else {}}


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
        # 미국 USGS(wetherilli 205) — 공공 도메인. 싣는 것은 굽는 사람이 고른다(`static_site.py --with usa`)
        "mrdata": {
            "url": settings.MRDATA_URL.rstrip("/"), "attribution": mrdata.ATTRIBUTION,
            "layers": {name: list(parts) for name, parts in mrdata.LAYERS.items()}, "queryable": list(mrdata.QUERYABLE),
            "sgmcFields": list(mrdata.SGMC_FIELDS),
        },
        # 스웨덴 SGU(wetherilli 213) — CC0. 싣는 것은 굽는 사람이 고른다(`static_site.py --with sweden`)
        "sgu": {
            "url": settings.SGU_WMS_URL, "attribution": sgu.ATTRIBUTION,
            "layers": {name: list(parts) for name, parts in sgu.LAYERS.items()}, "legend": sgu.LEGEND,
            "queryable": list(sgu.QUERYABLE),
            # 기반암·산지(wetherilli 270)의 열은 겹치지 않아 한 표로 잇는다
            "friendly": [list(pair) for pair in sgu.FRIENDLY + sgu.MINERAL_FRIENDLY + (("mag_anom", "자력 이상 (nT)"),)],
        },
        # 호주 GA(wetherilli 212) — CC BY 4.0. 싣는 것은 굽는 사람이 고른다(`static_site.py --with australia`)
        "ga": {
            "url": settings.GA_WMS_URL, "attribution": ga.ATTRIBUTION,
            "layers": {name: f"{spec[0]},{spec[1]}" for name, spec in ga.LAYERS.items()},
            "queryable": ga.legend_layers(),
            # 지질구·핵심 광물·지구물리 격자(wetherilli 241) — 다른 서비스라 주소가 따로다. 레이어 → [주소, WMS 레이어, 누르기가 되나]
            "other": {name: [ga._url(name), spec[1], spec[2]] for name, spec in ga.OTHER.items()},
        },
        # 유럽 넷(wetherilli 257) — `arcwms.Door` 를 쓰는 상류. 싣는 것은 굽는 사람이 고른다(`static_site.py --with netherlands` 따위)
        **{up: _arc(up) for up in ARC},
        # 지질시대 — 영문 ICS 값을 한국어로(`i18n.age_ko` 의 표)
        "age": {"words": i18n.AGE_WORDS_KO, "modifiers": i18n.AGE_MODIFIERS_KO, "joiners": i18n.AGE_JOINERS_KO},
        # 독일어·네덜란드어·폴란드어·프랑스어 시대 → ICS 영어(`i18n.age_local` 의 표, wetherilli 257)
        "ageLocal": {"words": i18n.AGE_LOCAL_WORDS, "modifiers": i18n.AGE_LOCAL_MODIFIERS, "glued": list(i18n._AGE_GLUED)},
        # 영어판 팝업 이름(`i18n.PROP_EN`)과 링크 이름표
        "propEn": i18n.PROP_EN, "linkEn": i18n.LINK_EN,
    }
