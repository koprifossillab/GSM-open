"""GSM 경유 — GSM 서버가 화면에 내주는 길(`/GSM/wms/`·`/GSM/vworld/…`)을 그대로 부른다. 키는 서버에만 있다 (wetherilli P16·407).

**주소의 꼴은 GSM 이 알려 준다**(`offline/plan/?layer=`) — 패키지가 계획을 베끼지 않는다. 화면과 한 글자까지 같은 주소라 GSM 의 서버
캐시 열쇠가 맞고(029), 캐시에 있던 것은 상류를 타지 않는다(머리 `X-GSM-Cache: hit`). 지층 면도 GSM 에 묻는다(`offline/units/`).

- 안내 타일(키가 없다·느리다 — 머리 `X-GSM-Notice`)은 실패다. 묶음에 넣지 않는다
- GSM 의 쉬는 중·차단 조짐(503·429·403)은 차단 조짐으로 읽어 곧장 멈춘다 — 우리는 GSM 의 `usage.paused()` 를 못 본다
"""
import json
import urllib.parse

from .. import bake, grid, net
from . import PartsSource


class GsmError(Exception):
    pass


def _base(url: str) -> str:
    return url if url.endswith("/") else url + "/"


def _json(url, where):
    status, _, body = net.get(url, where=where)
    if status != 200:
        raise GsmError(f"GSM 이 {where} 에 {status} 를 냈다 — 연구소 판의 판이 1.2 보다 옛것이거나 그 레이어를 굽지 못한다")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise GsmError(f"GSM 의 {where} 가 JSON 이 아니다") from exc


def plan(base: str, layer: str) -> dict:
    """레이어 하나를 받을 주소의 꼴 — `{title, attribution, kind, type, tile_size, zoom_offset, url}`."""
    return _json(_base(base) + "offline/plan/?" + urllib.parse.urlencode({"layer": layer}), f"offline/plan/ ({layer})")


class GsmSource(PartsSource):
    def __init__(self, base, name, spec, parts):
        super().__init__(name, parts)
        self.base, self.spec = _base(base), spec
        self.title, self.attribution = spec["title"], spec["attribution"]
        self.kind, self.type, self.tile_size = spec["kind"], spec["type"], spec["tile_size"]

    def grid_zoom(self, screen):
        return max(0, screen + self.spec["zoom_offset"])

    def fetch(self, z, x, y):
        where = f"{self.name}/{z}/{x}/{y}"
        url = self.base + self.spec["url"].format(z=z, x=x, y=y, bbox=grid.bbox_text(grid.cell_extent(z, x, y)))
        status, head, body = net.get(url, where=where)
        self.touched = head.get("x-gsm-cache") != "hit"
        if status != 200:
            raise bake.FetchError(f"GSM 이 {status} 를 냈다 ({where})", blocked=net.looks_blocked(status, body))
        if head.get("x-gsm-notice"):
            raise bake.FetchError(f"GSM 이 안내 타일을 냈다 ({where}) — 상류가 못 주었거나 서버에 키가 없다")
        if not head.get("content-type", "").startswith("image/"):
            raise bake.FetchError(f"타일이 아닌 것이 왔다 ({where}, {head.get('content-type')})")
        return self.keep(z, x, y, body)


def units(base, names, bbox, log=print) -> dict:
    """`{레이어: (GeoJSON 바이트, 피처 타입들)}` — GSM 이 상류에 1 초 간격으로 묻고 서버의 손질(링크·영어판)까지 해서 준다."""
    out = {}
    for name in names:
        query = urllib.parse.urlencode({"layer": name, "bbox": ",".join(str(v) for v in bbox)})
        try:
            data = _json(_base(base) + "offline/units/?" + query, f"offline/units/ ({name})")
        except (GsmError, bake.FetchError) as exc:
            log(f"  {name} 지층 면을 받지 못했다 — 속성 없이 굽는다: {exc}")
            continue
        if not data.get("features"):
            continue
        body = bake.units_body(data["features"])
        out[name] = (body, data.get("types") or [])
        log(f"  {name} 지층 면 {len(data['features'])} — {', '.join(out[name][1])}, {len(body) / 1024:.0f} KB")
    return out
