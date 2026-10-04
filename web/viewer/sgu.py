"""SGU(스웨덴 지질조사소)로 나가는 문 — 스웨덴 기반암 지질도 1:100만·1:5만–25만 (wetherilli 213).

- 주소: `maps3.sgu.se/geoserver/berg/ows` (GeoServer). 열쇠가 없다. 안내 문서의 `resource.sgu.se/service/wms/130/…` 는
  무엇을 물어도 GetCapabilities 를 돌려준다 — 그 Capabilities 가 가리키는 GeoServer 를 곧장 부른다
- 조건: **CC0 1.0** — SGU 는 2024-06-09 부터 모든 지질 자료를 열었다(EU 고가치 자료 규정). Fees·AccessConstraints 도 `NONE`.
  출처는 적는다(`ATTRIBUTION`). 정적 판에 고르면 싣는다(`static_site.py --with sweden`)
- **3413 으로 곧장 받는다.** Capabilities 는 3006·3857·4326 만 적지만 GeoServer 가 3413·3575 도 그려 준다(2026-10-04, 스톡홀름 둘레).
  GTK 와 같다. 3D 는 3857 로 묻는다
- **축척에 따라 판이 갈마든다** — 1:5만–25만 판(`…GEOLOGISK_ENHET.YTA.50K`)은 1:50만 남짓보다 가까울 때만 그리고, 덮지 않은 곳도 있다.
  두 판을 한 번에 물으면 1:100만 위에 5만이 얹혀 그려진다 — 멀면 1:100만만, 가까우면 5만이 덮은 곳은 5만이다. 그래서 레이어 하나가
  두 판을 함께 부른다(GA, wetherilli 212 와 같은 꼴)
- 속성은 `application/json`. 1:100만은 영어 열(`lithology`·`tect_unit`·`subunit`)이 따로 있어 그것을 쓰고, 5만은 스웨덴어뿐이라
  값을 그대로 둔다. GeoServer 는 누른 둘레의 이웃 면도 함께 주므로 `buffer` 를 좁히고 판마다 첫 하나만 남긴다
- 레이어명에 `sgu:` 를 붙여 카탈로그에 둔다. 상류로 나갈 때 판들의 이름으로 바꾼다
"""
import logging

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

PREFIX = "sgu:"
ATTRIBUTION = ('<a href="https://www.sgu.se/" target="_blank" rel="noopener">© SGU</a>'
               " (Sveriges geologiska undersökning, CC0)")
#: 레이어 → 함께 묻는 상류 레이어. **아래(먼저 그리는 것)부터** — GetMap 은 이 차례로 겹치고, 속성은 거꾸로(자세한 것부터) 묻는다
LAYERS = {
    "sgu:bedrock": ("SE.GOV.SGU.BERGGRUND_NA10", "SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K"),
    "sgu:deformation": ("SE.GOV.SGU.BERGGRUND_NA10_DFZ",),
}
#: 범례 — 1:100만 판의 것(555×5 576). 5만 판의 범례는 칸이 수천이라 싣지 않는다
LEGEND = {"sgu:bedrock": "SE.GOV.SGU.BERGGRUND_NA10", "sgu:deformation": "SE.GOV.SGU.BERGGRUND_NA10_DFZ"}
#: 누를 수 있는 레이어 — 변형대는 선이 가늘어 누른 자리에 걸리지 않는다(2026-10-04, 둘레 40 픽셀에도 빈 답)
QUERYABLE = ("sgu:bedrock",)
#: 누른 둘레(픽셀). 기본값이면 이웃 면이 너덧 함께 온다
QUERY_BUFFER = 1


class SguError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def upstream_names(name: str, reverse: bool = False) -> str:
    names = [n.strip() for n in str(name or "").split(",") if n.strip()]
    parts = []
    for n in names:
        if n not in LAYERS:
            raise SguError(f"모르는 레이어다: {n}")
        parts.extend(reversed(LAYERS[n]) if reverse else LAYERS[n])
    if not parts:
        raise SguError("레이어가 없다")
    return ",".join(parts)


def _get(params: dict):
    left = usage.paused()
    if left:
        raise SguError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.SGU_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("sgu", ok=False)
        raise SguError(f"SGU 에 닿지 못했다: {exc}") from exc
    log.info("SGU %s -> %s", r.url, r.status_code)
    usage.record("sgu", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    params.setdefault("styles", "")
    return params


def get_map(params: dict):
    params = _wms(params, "GetMap")
    params["layers"] = upstream_names(params.get("layers"))
    params["styles"] = ""                      # 판이 여럿이라 스타일 칸도 그 수만큼이어야 한다 — 빈 값이면 GeoServer 가 기본을 쓴다
    r = _get(params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise SguError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    name = LEGEND.get(layer)
    if not name:
        raise SguError(f"범례가 없는 레이어다: {layer}")
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png", "layer": name})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise SguError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    names = upstream_names(params.get("query_layers") or params.get("layers"), reverse=True)
    params.update(layers=names, query_layers=names, styles="", info_format="application/json",
                  feature_count=5, buffer=QUERY_BUFFER)
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise SguError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        features = r.json().get("features") or []
    except ValueError as exc:
        raise SguError("속성이 JSON 이 아니다") from exc
    return {"features": first_per_layer(features)}


def first_per_layer(features: list) -> list:
    """판마다 첫 하나만 — id 가 `<상류 레이어>.fid-…` 꼴이다. 기하는 버린다(팝업은 쓰지 않는다)"""
    seen, out = set(), []
    for f in features:
        layer = str(f.get("id") or "").split(".fid", 1)[0]
        if layer in seen:
            continue
        seen.add(layer)
        out.append({"id": f.get("id"), "properties": f.get("properties") or {}})
    return out


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로.** 같은 이름이 둘이면 앞의 것이 이긴다.
#: 1:100만(`lithology`·`tect_unit`·`subunit`, 영어 열)과 5만(`*_tx`, 스웨덴어)은 열이 겹치지 않는다
FRIENDLY = (
    ("geo_enh_tx", "지질 단위"),
    ("lithology", "암석"),
    ("bergart_tx", "암석"),
    ("lito_n_tx", "암층서 단위"),
    ("tect_unit", "지구조 단위"),
    ("tekt_n_tx", "지구조 단위"),
    ("subunit", "하위 단위"),
    ("min_ss_tx", "광물 조성"),
    ("handel1_tx", "생성"),
    ("prod_bet", "도폭"),
)


def clean(value) -> str:
    """`;` 로 이은 값에서 빈 칸(`Null:okänt`·`Null:saknas` 따위)을 뺀다. 정적 판의 `sguFriendly` 가 같은 셈을 한다"""
    parts = [p.strip() for p in str("" if value is None else value).split(";")]
    return "; ".join(p for p in parts if p and not p.lower().startswith("null"))


def friendly(props: dict, lang: str = "ko") -> dict:
    out = {}
    for key, label in FRIENDLY:
        value = clean(props.get(key))
        if value and label not in out:
            out[label] = value
    return out
