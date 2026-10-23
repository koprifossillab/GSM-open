"""박스 하나의 타일을 오프라인 묶음(`.gsmpack`) 하나로 굽는다 (wetherilli P13·381).

굽는 고리(어림·예산·받기·자르기·쓰기)는 패키지 `gsmpack`(`tools/gsmpack/`, wetherilli P16)에 있다. 여기는 GSM 안의 소스 —
KIGAM·VWorld 문과 서버 캐시 — 와 지층 면 모으기를 꽂는다.

    manage.py build_offline_pack jangseong --dry-run      # 장수·크기 어림, 예산에 맞춰 덜 줌
    manage.py build_offline_pack jangseong                # <DB 옆>/offline/jangseong-20261010.gsmpack

박스는 `data/offline_boxes.json` — 경위도 범위와 레이어마다 `[처음 줌, 마지막 줌]`(화면 줌). 적은 차례가 앞설 차례다.

- **받는 것은 화면이 부르는 것과 한 글자까지 같다** — KIGAM 은 `prewarm.plan_for` 의 계획(3857, 512 px WMS)을 빌려 캐시 열쇠가 같다.
  캐시에 있으면 그것을 쓰고, 없으면 문으로 받아 캐시에 담는다(큰 그림 한 장을 잘라 — `prewarm --meta 4` 와 같다)
- VWorld 배경은 `vworld.get_wmts_tile` 로 받는다 — 키는 문 안에서만이고, 지금처럼 서버 캐시에 담지 않는다(033). 굽다 멈췄을 때 다시
  받지 않게 받은 것을 `<출력>/.<박스>.parts.sqlite` 에 두었다가 다 구우면 지운다
- **빠르기는 미리 데우기와 같다**(devlog 010) — 상류에 1 초에 한 번, 차단 조짐이면 곧장 멈춘다. 연달아 3 번 실패해도 멈춘다
- **예산(`budget_mb`, 기본 200 MB)을 넘으면 뒤의 레이어부터 마지막 줌을 한 단계씩 내린다** — 받기 전에는 어림(캐시에 있는 타일의
  줌마다의 평균, 모자라면 `gsmpack.bake.GUESS_BYTES` 의 줌마다 잰 값 — wetherilli 404)으로, 받은 뒤에는 실제 크기로. 덜어 낸 것은 머리의 `dropped` 에 레이어마다 빠진 첫 줌으로 적는다
- 묶음의 타일 열쇠는 **화면의 tileCoord** — KIGAM 은 512 px 격자라 화면 줌보다 하나 작고, VWorld 는 256 px 라 화면 줌 그대로다.
  머리의 `layers.<이름>.zooms` 는 그 격자의 줌이고 `tile_size` 가 격자를 밝힌다
- 빈 타일(투명 한 장, VWorld 의 자료 밖)은 넣지 않는다. **키는 머리에도 주소에도 없다**
- **타일과 지층 면을 박스로 잘라 낸다**(wetherilli 385) — 얕은 줌의 타일 한 장은 도폭보다 훨씬 넓다(화면 줌 8 의 5만 타일 한 장이 2.8°).
  그대로 두면 축소했을 때 둘레 도폭까지 그려져 "어디까지가 묶음인가" 가 흐려진다. 박스에 걸친 타일은 박스 밖을 투명하게 비워 PNG 로
  다시 적고(위성 JPEG 도), 박스 밖의 타일은 넣지 않는다. 지층 면도 박스 네모로 잘라 이웃 도폭의 면이 묶음 밖으로 나가지 않게 한다
- **누른 자리의 속성은 지층 면으로 담는다**(wetherilli 384) — 박스의 `units` 에 적은 레이어(5만·25만·100만 지질도)만. 레이어를
  이루는 지층 피처 타입(`DescribeLayer` 에서 이름에 `litho` 가 든 것)을 박스 범위로 WFS 한 번에 받아, 속성은 서버의 `feature_info`
  처럼 추리고 좌표는 소수 다섯 자리(1 m 남짓)로 줄여 묶음 안에 `@units/<레이어>` 한 덩이(GeoJSON)로 넣는다. 화면은 망이 없을 때
  누른 자리를 품은 면의 속성을 낸다. 범례 색으로 찾지 않는 까닭 — 한 도폭 안에서도 단위 둘이 한 색이다(장성의 풍촌석회암층·화절층)
"""
import math
import time
import urllib.parse
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gsmpack import bake, boxes, format, grid, units
from gsmweb.version import VERSION
from viewer import elevation, geomap, i18n, kigam, offlinereq, tilecache, tilegrid, usage, views, vworld
from viewer.management.commands.prewarm import PREWARM_ERRORS, WmsPlan, plan_for
from viewer.models import Layer

META = 4                       # KIGAM 큰 그림 한 변의 타일 수 — `prewarm --meta 4`
VWORLD_ATTRIBUTION = "VWorld (국토교통부 공간정보 오픈플랫폼)"
KIGAM_ATTRIBUTION = "한국지질자원연구원 지오빅데이터 오픈플랫폼"


def load_boxes(path=None) -> dict:
    return boxes.load(path or settings.OFFLINE_BOXES_FILE)


def _fetch_error(exc):
    """문의 오류 → 굽는 고리의 오류. 차단 조짐은 문이 안다(`usage.paused`)."""
    return bake.FetchError(str(exc), blocked=bool(usage.paused()) or "차단" in str(exc))


class KigamSource:
    """KIGAM WMS — 화면의 `wmsSource`(3857, `createXYZ({tileSize: 512})`). 화면 줌 s 는 격자 줌 s − 1 이다."""
    tile_size = 512

    def __init__(self, name, title):
        self.name, self.title = name, title
        self.plan = plan_for(name, "kigam")
        if not isinstance(self.plan, WmsPlan):
            raise CommandError(f"{name} 은 타일 레이어가 아니다")
        self.attribution = KIGAM_ATTRIBUTION
        self.kind = "kigam"
        self.type = "image/png"

    def grid_zoom(self, screen):
        return max(0, screen - 1)

    def tiles(self, bbox, z):
        return grid.tiles_for(bbox, z)

    def cached(self, z, x, y):
        return tilecache.get(self.plan.key(z, x, y))

    def cached_size(self, z, x, y):
        return tilecache.size(self.plan.key(z, x, y))

    def calls_for(self, missing):
        return math.ceil(missing / (META * META) * 1.5)

    def fetch(self, z, x, y):
        """그 타일을 품은 큰 그림 한 장을 받아 잘라 캐시에 담고, 이 타일을 돌려준다. 상류에 한 번."""
        try:
            self.plan.fetch_block(z, x // META, y // META, META)
        except PREWARM_ERRORS as exc:
            raise _fetch_error(exc) from exc
        return self.cached(z, x, y)


#: VWorld 의 남극 기지 위성(테마)이 덮는 네모 — 화면의 `VWORLD_THEMES`(`map.js`)와 같다. 그 밖은 빈 자리라 묻지 않는다 (wetherilli 093·411)
THEME_BBOX = {"AntarcticaSejong": (-58.8196, -62.2679, -58.6073, -62.1697),
              "AntarcticaJangbogo": (163.9775, -74.6491, 164.3443, -74.5501)}


class VWorldSource:
    """VWorld 배경 — 화면의 `vworldSource`(256 px XYZ). 격자 줌이 화면 줌이다. 서버 캐시에 담지 않는다(033) — 받은 것은 parts 에."""
    tile_size = 256

    def __init__(self, name, layer, parts):
        if not vworld.knows_wmts(layer):
            raise CommandError(f"VWorld 배경에 {layer} 가 없다 — {', '.join([*vworld.WMTS_LAYERS, *vworld.WMTS_THEMES])}")
        self.name, self.layer, self.parts = name, layer, parts
        self.title = f"VWorld {layer}"
        self.attribution = VWORLD_ATTRIBUTION
        self.kind = name
        # 남극 기지 위성(테마, wetherilli 093)은 PNG 다. 화면이 3031 에 옮겨 그려도 소스의 격자는 3857 이라 열쇠·줌은 3857 의 것이다 (wetherilli 411)
        self.type = "image/jpeg" if vworld.WMTS_LAYERS.get(layer) == "jpeg" else "image/png"

    def grid_zoom(self, screen):
        return screen

    def tiles(self, bbox, z):
        theme = THEME_BBOX.get(self.layer)
        if theme:                       # 기지 위성은 기지 둘레 10 km 남짓뿐이다 — 박스와 겹치는 네모만 센다
            bbox = (max(bbox[0], theme[0]), max(bbox[1], theme[1]), min(bbox[2], theme[2]), min(bbox[3], theme[3]))
            if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                return []
        return grid.tiles_for(bbox, z)

    def cached(self, z, x, y):
        return self.parts.get(format.tile_key(self.name, z, x, y))

    def fetch(self, z, x, y):
        try:
            got = vworld.get_wmts_tile(self.layer, z, y, x)
        except (*PREWARM_ERRORS, vworld.VWorldError) as exc:
            raise _fetch_error(exc) from exc
        data = got[0] if got else b""
        self.parts.put(format.tile_key(self.name, z, x, y), data)
        return data


def tidy(props):
    """지층 면의 속성 손질 — 서버의 `feature_info` 처럼 링크를 가르고 영어판을 붙인다."""
    props = {k: views._split_links(v) for k, v in props.items()}
    return props, i18n.props_en(props)


class GeomapSource:
    """남극 GeoMAP 지질도 — 우리가 그린다(`views._geomap_png`). 화면의 `geomapSource`(3031 `GEOMAP_GRID`, 256 px) — 격자 줌이 화면 줌이다.
    캐시에 있으면 그것, 없으면 그려 캐시에 담는다(화면과 같은 열쇠). 상류를 타지 않으니 1 초를 쉬지 않는다(`touched`) (wetherilli P17·411)"""
    tile_size, kind, type, touched = geomap.TILE, "geomap", "image/png", False
    grid = grid.ANTARCTIC

    def __init__(self, name, title):
        self.name, self.title, self.attribution = name, title, geomap.ATTRIBUTION

    def grid_zoom(self, screen):
        return screen

    def tiles(self, bbox, z):
        return self.grid.tiles_for(bbox, z)

    def _key(self, z, x, y):
        return views.geomap_tile_key(self.name, z, x, y, geomap.TILE)

    def cached(self, z, x, y):
        return tilecache.get(self._key(z, x, y))

    def cached_size(self, z, x, y):
        return tilecache.size(self._key(z, x, y))

    def calls_for(self, missing):
        """상류에 묻는 어림 — 우리가 그리니 0 이다(장보고 어림이 그린 것 3 만 장을 "상류에 527 분" 으로 셌다)"""
        return 0

    def fetch(self, z, x, y):
        try:
            png, _ = views._geomap_png(self.name, z, x, y, geomap.TILE)
        except (geomap.GeomapError, OSError, ValueError) as exc:
            raise bake.FetchError(f"GeoMAP 을 그리지 못했다 ({self.name}/{z}/{x}/{y}): {exc}") from exc
        return png


#: 남극의 REMA 음영 배경 — 묶음의 이름 → (PGC 서비스, 그리는 법). 화면의 `BASEMAPS.rema*`(`pgcHillshade`)와 같다
REMA = {"basemap:rema": ("rema_latest", "Hillshade Gray"),
        "basemap:rema_multi": ("rema_latest", "Hillshade Multidirectional"),
        "basemap:rema_tinted": ("rema_latest", "Hillshade Elevation Tinted")}
PGC_ATTRIBUTION = "REMA © Polar Geospatial Center, Byrd Polar (CC BY 4.0)"


class RemaSource:
    """REMA 음영 — 화면의 `pgcHillshade`(3031 `createXYZ`, 512 px). 화면 줌 s 는 격자 줌 s − 1. PGC 가 부를 때마다 그려 서버 캐시에 담지 않는다 —
    받은 것은 parts 에 (wetherilli P17·411)"""
    tile_size, type = 512, "image/png"
    grid = grid.ANTARCTIC.with_tile(512)

    def __init__(self, name, parts):
        self.name, self.parts, self.kind = name, parts, name
        self.service, self.rendering = REMA[name]
        self.title, self.attribution = f"REMA ({self.rendering})", PGC_ATTRIBUTION

    def grid_zoom(self, screen):
        return max(0, screen - 1)

    def tiles(self, bbox, z):
        return self.grid.tiles_for(bbox, z)

    def cached(self, z, x, y):
        return self.parts.get(format.tile_key(self.name, z, x, y))

    def fetch(self, z, x, y):
        try:
            data = elevation.pgc_image(self.service, self.grid.cell_extent(z, x, y), self.tile_size, 3031, self.rendering)
        except elevation.ElevationError as exc:
            raise _fetch_error(exc) from exc
        self.parts.put(format.tile_key(self.name, z, x, y), data)
        return data


def geomap_units(name, bbox):
    """GeoMAP 레이어 하나의 지층 면 — 우리 파일(gpkg)의 R*Tree 에서 박스의 면을 뽑아 경위도로 옮긴다. 상류를 타지 않는다 (wetherilli 411)"""
    data = {"features": [{"type": "Feature", "properties": props,
                          "geometry": {"type": "MultiPolygon", "coordinates": [
                              [[list(geomap.xy3031_to_lonlat(ring[i], ring[i + 1])) for i in range(0, len(ring), 2)] for ring in rings]
                              for rings in parts]}}
                         for parts, props in geomap.polygons_in(name, grid.ANTARCTIC.projected_bbox(bbox))]}
    return unit_features(data, bbox), [f"geomap:{geomap.style_of(name).table}"]


def unit_features(data: dict, bbox=None) -> list:
    """WFS GeoJSON → 묶음에 넣을 면(`gsmpack.units.features`) — 손질은 GSM 의 것. `bbox` 가 있으면 그 네모로 잘라 낸다(wetherilli 385)."""
    return units.features(data, bbox, tidy)


def layer_units(name, bbox, gap):
    """레이어 하나의 지층 면 — `(면들, 피처 타입들)`. 상류에 DescribeLayer 한 번과 피처 타입마다 WFS 한 번, `gap` 초 간격.
    `/GSM/offline/units/`(GSM 을 거쳐 굽는 쪽, wetherilli 407)도 이것을 부른다. 못 받으면 문의 오류(`PREWARM_ERRORS`)"""
    types = [t for t in kigam.describe_layer(name) if "litho" in t.lower()]
    time.sleep(gap)
    features = []
    for type_name in types:
        features += unit_features(kigam.wfs_in_bbox(type_name, bbox), bbox)
        time.sleep(gap)
    return features, types


def plan_spec(name):
    """레이어 하나를 GSM 을 거쳐 받을 주소의 꼴 — `/GSM/offline/plan/` 이 낸다(wetherilli 407). 굽지 못하는 레이어면 None.
    주소는 화면이 부르는 것과 한 글자까지 같다 — KIGAM 은 `tilegrid.wms_params` 그대로라 서버 캐시의 열쇠가 맞는다(029).
    `{bbox}` 는 굽는 쪽이 칸의 3857 범위를 자바스크립트의 숫자 꼴로 채운다(`gsmpack.grid.bbox_text`)"""
    if name.startswith("vworld:"):
        layer = name.split(":", 1)[1]
        if layer not in vworld.WMTS_LAYERS:
            return None
        ext = vworld.WMTS_LAYERS[layer]
        return {"title": f"VWorld {layer}", "attribution": VWORLD_ATTRIBUTION, "kind": name, "tile_size": 256, "zoom_offset": 0,
                "type": "image/jpeg" if ext == "jpeg" else "image/png", "url": f"vworld/{layer}/{{z}}/{{y}}/{{x}}.{ext}"}
    row = Layer.objects.filter(upstream="kigam", enabled=True, name=name).values_list("title", flat=True).first()
    if row is None or not isinstance(plan_for(name, "kigam"), WmsPlan):
        return None
    params = dict(tilegrid.wms_params(name, 0, 0, 0), bbox="BBOX")
    query = urllib.parse.urlencode(params).replace("BBOX", "{bbox}")
    return {"title": row or name, "attribution": KIGAM_ATTRIBUTION, "kind": "kigam", "tile_size": 512, "zoom_offset": -1,
            "type": "image/png", "url": f"wms/?{query}"}


def make_sources(box, parts) -> tuple:
    """박스의 레이어마다 GSM 안의 소스 — `(소스들, 건너뛴 이름들)`. 카탈로그에 없거나 꺼졌거나 타일이 아닌 KIGAM 레이어는 건너뛴다.
    요청 화면의 어림(`views.offline_estimate`)도 이것으로 짓는다"""
    titles = dict(Layer.objects.filter(upstream__in=("kigam", "geomap")).values_list("name", "title"))
    enabled = set(Layer.objects.filter(upstream="kigam", enabled=True).values_list("name", flat=True))
    sources, skipped = {}, []
    for name in box["layers"]:
        if name.startswith("vworld:"):
            sources[name] = VWorldSource(name, name.split(":", 1)[1], parts)
        elif name in REMA:
            sources[name] = RemaSource(name, parts)
        elif name in geomap.LAYERS and geomap.available():
            sources[name] = GeomapSource(name, titles.get(name) or name)
        elif name in enabled and isinstance(plan_for(name, "kigam"), WmsPlan):
            sources[name] = KigamSource(name, titles.get(name) or name)
        else:
            skipped.append(name)
    return sources, skipped


class Command(BaseCommand):
    help = "박스 하나의 타일을 오프라인 묶음(.gsmpack)으로 굽는다 — 또는 승인된 요청을 차례로(--queue)"

    def add_arguments(self, parser):
        parser.add_argument("box", nargs="?", help="data/offline_boxes.json 의 박스 이름")
        parser.add_argument("--dry-run", action="store_true", help="받지 않고 장수·크기만 어림한다")
        parser.add_argument("--out", help=f"출력 폴더 (기본 {settings.OFFLINE_DIR})")
        parser.add_argument("--rate", type=float, default=1.0, help="1 초에 몇 번 묻나 (최대 1)")
        parser.add_argument("--queue", action="store_true",
                            help="승인된 요청(OfflinePackRequest)을 하나씩 굽는다 — 다른 일꾼이 돌면 곧장 끝난다 (wetherilli 408)")

    def handle(self, *args, **o):
        if o["queue"]:
            return self.queue()
        if not o["box"]:
            raise CommandError("박스 이름이나 --queue 를 준다")
        table = load_boxes()
        if o["box"] not in table:
            raise CommandError(f"박스가 없다: {o['box']} — {', '.join(table)}")
        self.bake_box(o["box"], table[o["box"]], Path(o["out"] or settings.OFFLINE_DIR), dry_run=o["dry_run"], rate=o["rate"])

    def bake_box(self, name, box, out_dir, *, dry_run=False, rate=1.0):
        """박스 하나를 굽는다. 돌려주는 것은 `bake.bake` 의 것(어림만이면 None). 멈추면 `CommandError`"""
        parts = bake.Parts(bake.parts_path(out_dir, name)) if not dry_run else bake.NoParts()
        sources, skipped = make_sources(box, parts)
        if skipped:
            self.stderr.write(f"건너뛴다(카탈로그에 없거나 꺼졌거나 타일이 아니다): {', '.join(skipped)}")

        plan = bake.Plan(name, box, sources, rate=rate)
        for line in plan.lines:
            self.stdout.write(line)
        if dry_run:
            return None
        if any(isinstance(s, KigamSource) for s in sources.values()) and not kigam.has_key():
            raise CommandError("KIGAM 인증키가 없다")
        try:
            done = bake.bake(plan, out_dir, parts, units=lambda bbox, gap: self.gather_units(box, sources, bbox, gap),
                             extra={"gsm": VERSION}, log=self.stdout.write)
        except bake.BakeError as exc:
            raise CommandError(str(exc)) from exc
        path = done["path"]
        drawn = f", 그린 것 {done['made']:,}" if done.get("made") else ""
        done["line"] = (f"{path.name} — 타일 {done['tiles']:,} 장, {path.stat().st_size / 1024 / 1024:.1f} MB, "
                        f"상류에 {done['asked']:,} 번{drawn}, 실패 {done['fails']}")
        self.stdout.write(self.style.SUCCESS(f"{path} — {done['line'].split(' — ', 1)[1]}"))
        return done

    def queue(self):
        """승인된 요청을 하나씩 — 끊긴 "굽는 중" 이 먼저, 다음은 승인한 차례. 남은 것이 없으면 끝난다 (wetherilli 408)"""
        from viewer.models import OfflinePackRequest as Req
        with offlinereq.queue_lock() as mine:
            if not mine:
                self.stdout.write("다른 일꾼이 굽는 중이다 — 그쪽이 이어 집는다")
                return
            while True:
                req = (Req.objects.filter(status=Req.BAKING).order_by("started_at", "id").first()
                       or Req.objects.filter(status=Req.APPROVED).order_by("decided_at", "id").first())
                if req is None:
                    return
                self.stdout.write(f"=== {req.box_name} {req.box.get('title', '')} ({req.requester}) {timezone.localtime():%Y-%m-%d %H:%M}")
                req.status, req.started_at = Req.BAKING, req.started_at or timezone.now()
                req.save(update_fields=["status", "started_at"])
                try:
                    done = self.bake_box(req.box_name, req.box, Path(settings.OFFLINE_DIR))
                    req.status, req.pack, req.last_line = Req.DONE, done["path"].name, done["line"][:500]
                except Exception as exc:                      # noqa: BLE001 — 무엇으로 멈추든 "굽는 중" 에 남지 않게
                    req.status, req.last_line = Req.FAILED, kigam.redact(str(exc))[:500]
                    self.stderr.write(f"{req.box_name} 을 굽지 못했다: {req.last_line}")
                req.finished_at = timezone.now()
                req.save(update_fields=["status", "pack", "last_line", "finished_at"])


    def gather_units(self, box, sources, bbox, gap):
        """박스의 `units` 레이어마다 지층 면 — `{레이어: (GeoJSON 바이트, 피처 타입)}`. 상류에 레이어마다 두 번(DescribeLayer·WFS),
        1 초 간격. 실패해도 묶음은 굽는다(속성 없이)"""
        out = {}
        for name in box.get("units", []):
            if not isinstance(sources.get(name), (KigamSource, GeomapSource)):
                continue
            try:
                if isinstance(sources[name], GeomapSource):
                    features, types = geomap_units(name, bbox)
                else:
                    features, types = layer_units(name, bbox, gap)
            except (*PREWARM_ERRORS, geomap.GeomapError) as exc:
                self.stderr.write(f"  {name} 지층 면을 받지 못했다 — 속성 없이 굽는다: {exc}")
                continue
            if not features:
                continue
            body = bake.units_body(features)
            out[name] = (body, types)
            self.stdout.write(f"  {name} 지층 면 {len(features)} — {', '.join(types)}, {len(body) / 1024:.0f} KB")
        return out
