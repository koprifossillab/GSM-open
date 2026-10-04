"""SGB(브라질 지질조사소, 옛 CPRM)로 나가는 문 — 브라질 지질도 (wetherilli 191).

- 주소가 둘이다. **`geoservicos.sgb.gov.br/geoserver/ows`** — 리토스트라티그래피 1:100만(전국 46 도폭, GIS Brasil 2004)·1:25만(간행된
  도폭만). **`opendata.sgb.gov.br/geoserver/ows`** — 2025 년판 1:250만(전국)과 그 구조선. 둘 다 GeoServer 라 3857 을 그린다. 열쇠가 없다
- 레이어명은 `sgb:<판>` 이다(`LAYERS`). 상류의 이름(`geosgb:…`·`geonode:…`)과 주소는 여기서만 안다
- **속성에는 `propertyName` 을 붙인다** — 안 붙이면 기하까지 와서 한 번에 1–2 MB 다(2026-10-04: 1:100만 0.9 MB, 1:250만 2.3 MB).
  붙이면 기하가 빠지고 1–2 KB 다(GeoServer 의 벤더 인자)
- **범례는 보는 범위의 것**이다 — 범례 그림은 225×46 700 이라 쓸 수 없다. GeoServer 의 `GetLegendGraphic` 에
  `hideEmptyRules`·`countMatched` 와 범위를 주면 그 범위에 칠해진 칸만 JSON 으로 준다(기호·색·폴리곤 수). 단위 이름은 그 답에 없어,
  모아 둔 이름표(`manage.py fetch_sgb_units`)가 있으면 붙인다
- 시대 값은 포르투갈어다(`Cambriano`·`Neoproterozóico`). ICS 영문 이름으로 옮긴 뒤 한국어판이면 `i18n.age_ko` 로 한 번 더 옮긴다
- 조건: GetCapabilities 의 Fees·AccessConstraints 는 `NONE`. GeoSGB 사이트는 **CC BY-NC 4.0**(비상업, 출처 SGB)이라 적는다
  (`geosgb.sgb.gov.br/geosgb/footer.html`, 2026-10-04) — EOX 처럼 밖에 열 때 다시 본다. 정적 판에는 싣지 않았다
- 응답이 1–5 초로 들쭉날쭉하다 — 받은 것은 캐시에 담는다
"""
import json
import logging
import unicodedata
from pathlib import Path

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "sgb:"
ATTRIBUTION = ('<a href="https://geosgb.sgb.gov.br/" target="_blank" rel="noopener">SGB/CPRM</a> '
               '(Serviço Geológico do Brasil, CC BY-NC 4.0)')

#: 레이어 → (서버, 상류 이름, 속성 열, 범례의 기호 열, 처음 그리는 화면 줌, 범례를 뜨는 가장 넓은 범위(°)).
#: 1:250만은 나라 전체(경도 40° 남짓)를 한눈에 보는 판이라 그 범위의 범례도 뜬다 — 칸이 많으면 `MAX_LEGEND` 에서 끊는다
LAYERS = {
    "sgb:2500k": ("opendata", "geonode:mgbrasil_litoestratigrafia_escala_1_2500000",
                  ("sigla_unid", "nome_unida", "hierarquia", "idade_max", "idade_min", "era_maxima", "periodo_ma",
                   "era_minima", "periodo_mi", "litotipo1", "litotipo2", "classe_r_1"), "sigla_unid", None, 80),
    "sgb:2500k_structures": ("opendata", "geonode:mgbrasil_estruturas_terrestres_escala_1_2500000",
                             ("nmestrutur", "tipo_estru"), None, None, None),
    "sgb:1m": ("geoservicos", "geosgb:litoestratigrafia_1m",
               ("sigla", "hierarquia", "nome", "legenda", "litotipos", "idade_min", "idade_max", "era_min", "era_max",
                "sistema_min", "sistema_max", "ambiente_tectonico", "mapa"), "sigla", 6, 15),
    "sgb:250k": ("geoservicos", "geosgb:litoestratigrafia_250k",
                 ("sigla", "hierarquia", "nome", "legenda", "litotipos", "idade_min", "idade_max", "era_min", "era_max",
                  "sistema_min", "sistema_max", "ambiente_tectonico", "mapa"), "sigla", 9, 5),
}
SERVERS = {"geoservicos": "SGB_GEOSERVICOS_URL", "opendata": "SGB_OPENDATA_URL"}
#: 범례 칸을 몇 개까지 싣나 — 넘치면 "그 밖 N 칸" 이다
MAX_LEGEND = 60
#: 넓은 줌의 1:100만 한 장은 3–4 초인데, 화면이 여러 장을 한꺼번에 물으면 밀린다. EGDI·SGC 처럼 더 기다린다
TIMEOUT = 45


class SgbError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def _layer(name: str):
    names = [n.strip() for n in str(name or "").split(",") if n.strip()]
    if len(names) != 1 or names[0] not in LAYERS:
        raise SgbError(f"모르는 레이어다: {name}")
    return names[0], LAYERS[names[0]]


def zooms(name: str) -> tuple:
    """화면이 그리는 줌 (처음, 마지막). 1:100만·1:25만은 넓게 보면 무겁고(1:100만 512 칸 한 장 320 KB) 1:250만이 그 자리를 덮는다"""
    return (LAYERS[name][4], None) if name in LAYERS else (None, None)


def _url(server: str) -> str:
    return getattr(settings, SERVERS[server])


def _get(server: str, params: dict):
    left = usage.paused()
    if left:
        raise SgbError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(_url(server), params=params, timeout=max(settings.UPSTREAM_TIMEOUT, TIMEOUT),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sgb", ok=False)
        raise SgbError(f"SGB 에 닿지 못했다: {exc}") from exc
    log.info("SGB %s -> %s", r.url, r.status_code)
    usage.record("sgb", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str):
    """화면의 변수 → 상류의 변수. 레이어 이름만 갈고 나머지는 그대로다(GeoServer 는 1.3.0 의 3857 을 그대로 받는다)."""
    name, spec = _layer(params.get("layers") or params.get("query_layers"))
    params = dict(params, service="WMS", request=request, layers=spec[1])
    if "query_layers" in params:
        params["query_layers"] = spec[1]
    return name, spec, params


def get_map(params: dict):
    _, spec, params = _wms(params, "GetMap")
    r = _get(spec[0], params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SgbError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    """범례 그림은 225×46 700 이라 내주지 않는다 — 화면은 보는 범위의 범례(`sgb/legend/`)를 부른다."""
    raise SgbError("SGB 범례는 보는 범위로만 뜬다")


def get_feature_info(params: dict) -> dict:
    _, spec, params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/json"
    # 기하를 빼고 고른 열만 — 안 빼면 한 번에 1–2 MB 다
    params["propertyName"] = ",".join(spec[2])
    r = _get(spec[0], params)
    if r.status_code != 200:
        raise SgbError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise SgbError("속성이 JSON 이 아니다") from exc


# ── 지질시대 — 포르투갈어 → ICS 영문 ────────────────────────────────

#: 덧붙임표를 떼고 작은 글자로 견준다(`Neoproterozóico`·`Neogeno` 처럼 상류의 적기가 들쭉날쭉하다)
AGES_PT = {
    "hadeano": "Hadean", "arqueano": "Archean", "eoarqueano": "Eoarchean", "paleoarqueano": "Paleoarchean",
    "mesoarqueano": "Mesoarchean", "neoarqueano": "Neoarchean",
    "proterozoico": "Proterozoic", "paleoproterozoico": "Paleoproterozoic", "mesoproterozoico": "Mesoproterozoic",
    "neoproterozoico": "Neoproterozoic", "fanerozoico": "Phanerozoic",
    "paleozoico": "Paleozoic", "mesozoico": "Mesozoic", "cenozoico": "Cenozoic",
    "sideriano": "Siderian", "riaciano": "Rhyacian", "orosiriano": "Orosirian", "estateriano": "Statherian",
    "calimiano": "Calymmian", "ectasiano": "Ectasian", "esteniano": "Stenian", "toniano": "Tonian",
    "criogeniano": "Cryogenian", "ediacarano": "Ediacaran",
    "cambriano": "Cambrian", "ordoviciano": "Ordovician", "siluriano": "Silurian", "devoniano": "Devonian",
    "carbonifero": "Carboniferous", "permiano": "Permian", "triassico": "Triassic", "jurassico": "Jurassic",
    "cretaceo": "Cretaceous", "paleogeno": "Paleogene", "neogeno": "Neogene", "quaternario": "Quaternary",
    "paleoceno": "Paleocene", "eoceno": "Eocene", "oligoceno": "Oligocene", "mioceno": "Miocene",
    "plioceno": "Pliocene", "pleistoceno": "Pleistocene", "holoceno": "Holocene",
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def age_en(value: str) -> str:
    """포르투갈어 시대 이름 하나 → ICS 영문. 모르면 원문 그대로."""
    return AGES_PT.get(_fold(value), str(value or "").strip())


def _value(props: dict, key: str) -> str:
    value = str(props.get(key) if props.get(key) is not None else "").strip()
    return "" if value.lower() in ("none", "null") else value


def _span(old: str, young: str, lang: str) -> str:
    """가장 오랜 것과 젊은 것 — 같으면 하나, 다르면 `오랜 - 젊은` 으로 잇고, 한국어판이면 `i18n.age_ko` 로 옮긴다."""
    a, b = age_en(old) if old else "", age_en(young) if young else ""
    age = a if a == b or not b else (b if not a else f"{a} - {b}")
    return i18n.age_ko(age) if lang == "ko" and age else age


def _ma(old: str, young: str) -> str:
    if old and young and old != young:
        return f"{young}–{old}"
    return old or young


def friendly(props: dict, lang: str = "ko") -> dict:
    """열 이름을 한국어로. 이름·설명·암석은 포르투갈어 그대로 두고 지질시대만 옮긴다."""
    v = lambda k: _value(props, k)          # noqa: E731
    if "tipo_estru" in props:                                          # 1:250만 구조선
        return {k: x for k, x in (("이름", v("nmestrutur")), ("갈래", v("tipo_estru"))) if x}
    if "sigla_unid" in props:                                          # 1:250만 (2025)
        age = _span(v("periodo_ma") or v("era_maxima"), v("periodo_mi") or v("era_minima"), lang)
        rows = (("기호", v("sigla_unid")), ("이름", v("nome_unida")), ("위계", v("hierarquia")),
                ("지질시대", age), ("연대 (Ma)", _ma(v("idade_max"), v("idade_min"))),
                ("암석", v("litotipo1") or v("litotipo2")), ("암석 분류", v("classe_r_1")))
    else:                                                              # 1:100만·1:25만
        age = _span(v("sistema_max") or v("era_max"), v("sistema_min") or v("era_min"), lang)
        rows = (("기호", v("sigla")), ("이름", v("nome")), ("위계", v("hierarquia")), ("지질시대", age),
                ("연대 (Ma)", _ma(v("idade_max"), v("idade_min"))), ("암석", v("litotipos")), ("설명", v("legenda")),
                ("지구조 환경", v("ambiente_tectonico")), ("도폭", v("mapa")))
    return {k: x for k, x in rows if x}


# ── 보는 범위의 범례 ────────────────────────────────────────────────

def legend_layers() -> list:
    """보는 범위의 범례를 뜨는 레이어 — 기호 열이 있는 것(단위 면)."""
    return [name for name, spec in LAYERS.items() if spec[3]]


def legend_span(name: str) -> float:
    return LAYERS[name][5]


def extent_legend(name: str, bbox_3857: tuple, width: int = 1024, height: int = 768) -> list:
    """범위 `(서, 남, 동, 북)`(3857 미터)에 칠해진 칸 — `[{"symbol", "color", "count"}, …]`, 많이 칠해진 것부터.

    GeoServer 가 그 범위를 그려 보고 빈 규칙을 뺀다(`hideEmptyRules`). 규칙의 이름이 곧 기호다. 이름 없는 규칙(기호가 빈 면)은 뺀다."""
    name, spec = _layer(name)
    if not spec[3]:
        raise SgbError("범례가 없는 레이어다")
    r = _get(spec[0], {"service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "application/json",
                       "layer": spec[1], "legend_options": "countMatched:true;hideEmptyRules:true",
                       "bbox": ",".join(f"{v:.0f}" for v in bbox_3857), "srs": "EPSG:3857", "crs": "EPSG:3857",
                       "srcwidth": str(width), "srcheight": str(height)})
    if r.status_code != 200:
        raise SgbError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        rules = (r.json().get("Legend") or [{}])[0].get("rules") or []
    except (ValueError, AttributeError, IndexError) as exc:
        raise SgbError("범례가 JSON 이 아니다") from exc
    out = []
    for rule in rules:
        symbol = str(rule.get("name") or "").strip()
        fill = next((s["Polygon"].get("fill") for s in rule.get("symbolizers") or [] if "Polygon" in s), None)
        if not symbol or not fill:
            continue
        title = str(rule.get("title") or "")
        count = int(title.rsplit("(", 1)[1].rstrip(") ")) if title.endswith(")") and "(" in title else 0
        out.append({"symbol": symbol, "color": fill, "count": count})
    return sorted(out, key=lambda r: -r["count"])


# ── 단위 이름표 — 범례에 이름·시대를 붙인다 ─────────────────────────

UNITS_FILE = "units.json"
#: WFS 한 번에 받는 줄 수. 1:100만은 4 만 6 천 줄이라 열 번 남짓 묻는다
PAGE = 5000


def units_path() -> Path:
    return Path(settings.SGB_DIR) / UNITS_FILE


def load_units() -> dict:
    """`{레이어: {기호: [이름, 오랜 시대, 젊은 시대]}}`. 없으면 빈 것 — 범례는 기호만 보인다."""
    try:
        return json.loads(units_path().read_text(encoding="utf-8")).get("layers") or {}
    except (OSError, ValueError):
        return {}


def fetch_units(name: str, pause: float = 1.0, log_line=print) -> dict:
    """한 판의 기호 → 이름·시대를 WFS 로 쪽마다 받아 모은다(`manage.py fetch_sgb_units`). 기하는 받지 않는다."""
    import time
    name, spec = _layer(name)
    if not spec[3]:
        raise SgbError("단위 면이 아닌 레이어다")
    two_and_half = spec[3] == "sigla_unid"
    cols = ("sigla_unid", "nome_unida", "periodo_ma", "periodo_mi", "era_maxima", "era_minima") if two_and_half \
        else ("sigla", "nome", "sistema_max", "sistema_min", "era_max", "era_min")
    units, start = {}, 0
    while True:
        r = _get(spec[0], {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": spec[1],
                           "propertyName": ",".join(cols), "outputFormat": "application/json", "count": str(PAGE),
                           "startIndex": str(start), "sortBy": cols[0]})
        if r.status_code != 200:
            raise SgbError(f"단위를 읽지 못했다 (status={r.status_code})")
        try:
            feats = r.json().get("features") or []
        except ValueError as exc:
            raise SgbError("단위가 JSON 이 아니다") from exc
        for f in feats:
            p = f.get("properties") or {}
            symbol = _value(p, cols[0])
            if symbol and symbol not in units:
                units[symbol] = [_value(p, cols[1]), _value(p, cols[2]) or _value(p, cols[4]),
                                 _value(p, cols[3]) or _value(p, cols[5])]
        log_line(f"  {name}: {start + len(feats):,}줄 — 기호 {len(units):,}")
        if len(feats) < PAGE:
            return units
        start += PAGE
        time.sleep(pause)


def legend_row(row: dict, units: dict, lang: str = "ko") -> dict:
    """화면이 그리는 한 칸 — 일본(GSJ)·대만의 칸과 같은 이름이다. 이름표가 없으면 기호가 이름 자리에 선다."""
    unit = units.get(row["symbol"])
    return {"color": row["color"], "symbol": row["symbol"], "swatch": "",
            "lithology": f"{row['symbol']} {unit[0]}".strip() if unit and unit[0] else row["symbol"],
            "age": _span(unit[1], unit[2], lang) if unit else ""}
