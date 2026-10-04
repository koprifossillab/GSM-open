"""ArcGIS WMS 를 중계하는 문들이 함께 쓰는 틀 (wetherilli 228). **문이 아니다** — `requests` 를 쓰지 않는다.

동남아 문(`esdm.py`·`mgb.py`·`dmr.py`)과 유럽 문(`geosphere.py`·`pig.py`·`tno.py`·`dov.py`·`spw.py`, wetherilli 237)이 같은 꼴이라
여기 모았다. 이름은 ArcGIS 지만 GeoServer WMS 도 이 틀로 돈다. 문은 제 `_get`(상류로 나가는 길)을 넘기고, 이 틀은 WMS 변수를 고치고
응답을 읽기만 한다. ArcGIS WMS 의 GetFeatureInfo 는 판에 따라 geojson 을 주기도 하고 ESRI XML(`<FIELDS a="…"/>`)만 주기도 한다 — 둘 다 읽는다.
"""
import xml.etree.ElementTree as ET


class Door:
    """`layers` — 우리 이름 → 상류 WMS 이름. `queryable` — 누를 수 있는 우리 이름. `info_format` — 상류가 주는 속성 꼴"""

    def __init__(self, *, url, layers: dict, queryable=(), info_format="application/geojson", get, error, info_params=None):
        self.url, self.layers, self.queryable = url, layers, tuple(queryable)
        self.info_format, self._get, self.Error = info_format, get, error
        #: 속성을 물을 때 더 붙일 변수 — `{우리 이름: {...}}`. GeoServer 의 `propertyName`(모양째 오는 것을 피한다, wetherilli 237)
        self.info_params = info_params or {}

    def knows(self, name: str) -> bool:
        return bool(name) and all(n.strip() in self.layers for n in str(name).split(","))

    def names(self, names: str) -> str:
        if not self.knows(names):
            raise self.Error(f"모르는 레이어다: {names}")
        return ",".join(self.layers[n.strip()] for n in str(names).split(","))

    def _wms(self, params: dict, request: str) -> dict:
        params = dict(params, service="WMS", request=request, version="1.1.1")
        if "crs" in params and "srs" not in params:
            params["srs"] = params.pop("crs")
        for key in ("layers", "query_layers"):
            if key in params:
                params[key] = self.names(params[key])
        return params

    def get_map(self, params: dict):
        r = self._get(self.url(), self._wms(params, "GetMap"))
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or not ctype.startswith("image/"):
            raise self.Error(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
        return r.content, ctype

    def get_legend(self, layer: str):
        r = self._get(self.url(), {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
                                   "layer": self.names(layer)})
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            raise self.Error(f"범례가 아닌 것이 왔다 (status={r.status_code})")
        return r.content, r.headers.get("content-type")

    def get_feature_info(self, params: dict) -> dict:
        name = str(params.get("query_layers") or params.get("layers") or "").split(",")[0].strip()
        if name not in self.queryable:
            raise self.Error(f"누를 수 없는 레이어다: {name}")
        params = self._wms(params, "GetFeatureInfo")
        params["info_format"] = self.info_format
        params.update(self.info_params.get(name, {}))
        if "i" in params and "x" not in params:
            params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
        r = self._get(self.url(), params)
        if r.status_code != 200:
            raise self.Error(f"속성을 읽지 못했다 (status={r.status_code})")
        if "json" in self.info_format:
            try:
                return {"features": r.json().get("features") or []}
            except ValueError as exc:
                raise self.Error("속성이 JSON 이 아니다") from exc
        try:
            rows = fields_xml(r.content)
        except ET.ParseError as exc:
            raise self.Error("속성이 XML 이 아니다") from exc
        return {"features": [{"id": f"{name}.{i}", "properties": p} for i, p in enumerate(rows)]}


def fields_xml(text) -> list:
    """ArcGIS WMS 의 ESRI XML(`<FeatureInfoResponse><FIELDS a="…" …/></FeatureInfoResponse>`) → 속성 사전 목록. 값 `Null` 은 뺀다"""
    root = ET.fromstring(text)
    out = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "FIELDS":
            out.append({k: v for k, v in el.attrib.items() if str(v).strip() and str(v).strip().lower() != "null"})
    return out


def legend_list(data: dict, layer_ids=None) -> list:
    """REST `legend?f=json` → `[(칸 이름, data URI)]`. `layer_ids` 를 주면 그 레이어만, 같은 이름은 처음 것 하나만"""
    seen, out = set(), []
    for part in data.get("layers") or []:
        if layer_ids is not None and part.get("layerId") not in layer_ids:
            continue
        for item in part.get("legend") or []:
            label = str(item.get("label") or "").strip()
            if not label or label in seen or not item.get("imageData"):
                continue
            seen.add(label)
            out.append((label, f"data:{item.get('contentType') or 'image/png'};base64,{item['imageData']}"))
    return out
