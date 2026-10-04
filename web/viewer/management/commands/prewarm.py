"""보고 싶은 자리의 타일을 **천천히** 미리 받아 둔다.

    manage.py prewarm --bbox 127.25,36.33,127.5,36.5 --zooms 10-15 --dry-run
    manage.py prewarm --around 36.378,127.362 --km 5 --zooms 12-16
    manage.py prewarm --bbox ... --layers L_50K_Geology_Map,L_250K_Geology_Map

**한계를 재지 않고, 누가 봐도 무리가 없는 빠르기로 간다** (devlog 010).

- 기본 **1 초에 한 장.** 사람이 지도를 볼 때 나가는 것보다 느리다
- 한 번에 **최대 2 000 장**(`--max`). 남은 것은 다음에 이어 받는다 — 이미
  받아 둔 타일은 건너뛰므로 같은 명령을 다시 부르면 이어진다
- **차단 조짐이 한 번이라도 보이면 곧장 멈춘다.** 실패가 연달아 3 번이어도
  멈춘다
- 받는 타일은 브라우저가 부르는 것과 **한 글자까지 같다** (`tilegrid.py`).
  그래야 캐시가 맞는다
- **큰 그림 한 장을 받아 잘라 담는다** (`--meta 4` 면 2048 px 한 장 = 타일
  16 장). 호출이 16 분의 1 로 준다. 지질 경계·색·무늬는 따로 받은 타일과
  똑같고, 지명·기호 **글자 자리만** 다르다 — GeoServer 가 그림 한 장 안에서
  글자가 겹치지 않게 놓기 때문이다. 2026-09-27 에 견줘 보니 다른 픽셀이
  1.3~1.6% 였고 모두 글자였다. `--meta 1` 이면 한 장씩 받는다

**상류마다 받는 꼴이 다르다** — 브라우저가 부르는 꼴 그대로 받아야 캐시가 맞는다.

| 상류 | 꼴 | 큰 그림 |
|---|---|---|
| KIGAM·GEUS·VWorld | WMS, 3857, 512 px | 된다 |
| NPI | WMS, 지역의 투영(3413·3031), 512 px (021) | 된다 |
| GSJ | z/x/y, 256 px, 줌 13 까지 (024) | 안 된다 — 한 장씩 |
| GeoMAP | 우리가 굽는다, 3031, 256 px (018) | 안 된다. 상류가 없어 쉬지 않는다 |
| 3D 극지 표고(`dem`) | PGC 를 3857 Terrarium 으로 편다, 줌 11–15 (032) | 4×4 네모째 (034) |
| 극지연구소(KOPRI) WMS | NPI 와 같다 — 지역의 투영(3031·3413), 512 px (057) | 된다 |
| 유럽·북극 상류(EMODnet·NGU·GTK·BGS·GSNI·BRGM·EGDI·BGR·IGME·GSI) | 카탈로그 행의 투영(3413·3575·4326·3857), 512 px. 화면이 그리는 줌만 | 된다 |
| 달·화성 Trek(`moon:units`·`moon:dem`·`mars:units`·`mars:dem` …) | 그 몸의 경위도 격자, z/x/y (036·058) | 안 된다 — 한 장씩 |

**달·화성은 레이어가 아니라 이름으로 부른다** — `--bbox` 는 그 몸의 경위도다(wetherilli 158).

    manage.py prewarm --bbox 20,0,40,30 --zooms 3-7 --layers moon:units,moon:dem     # 고요의 바다 둘레
    manage.py prewarm --bbox -90,-20,-60,10 --zooms 3-6 --layers mars:units          # 마리네리스 협곡

    manage.py prewarm --bbox 10,76,30,81 --zooms 3-8 --layers npolar:svalbard_units
    manage.py prewarm --bbox=-0.2,51.45,-0.1,51.55 --zooms 11-14 --layers bgs:BGS.50k.Bedrock     # 런던 (서경은 = 로 붙인다)
    manage.py prewarm --bbox -180,-90,180,-60 --zooms 0-5 --layers geomap_simple_geology

**`dem` 은 레이어가 아니라 3D 의 극지 지형이다** — 위도 60° 너머, 줌 11 부터 3D 가 서버에 묻는
타일(`dem/<z>/<x>/<y>.png`)이다. 빈 캐시에서 처음 가는 자리는 20 초 남짓 걸린다(034). 네모 하나에
5 초 남짓이라 반지름 몇 km 만 받는다.

    manage.py prewarm --around 78.925,11.93 --km 5 --zooms 11-15 --layers dem     # 다산기지
    manage.py prewarm --around -74.62,164.23 --km 5 --zooms 11-15 --layers dem    # 장보고기지
    manage.py prewarm --around -62.22,-58.79 --km 5 --zooms 11-15 --layers dem    # 세종기지

밤에 돌리려면 cron 에 건다. 이 명령 자체는 시간을 가리지 않는다.
"""
import io
import math
import time

from PIL import Image

from django.core.management.base import BaseCommand, CommandError

from viewer import elevation, geomap, gsj, ingemmet, kigam, kopri, npolar, tilecache, tilegrid, trek, usage, views
from viewer.models import Layer

DEFAULT_LAYERS = ["L_50K_Geology_Map"]
#: 큰 그림 한 장을 그려 받는 데 드는 초. 2026-09-27 에 5만 지질도로 쟀다
#: (512 px 0.2 초, 2048 px 1.1 초, 4096 px 2.4 초).
SECONDS_PER_CALL = {1: 0.2, 2: 0.5, 4: 1.1, 8: 2.4}


def parse_zooms(text):
    lo, _, hi = text.partition("-")
    lo, hi = int(lo), int(hi or lo)
    if not (0 <= lo <= hi <= 19):
        raise CommandError("--zooms 는 0~19 사이, 예: 10-15")
    return range(lo, hi + 1)


class Command(BaseCommand):
    help = "보고 싶은 자리의 타일을 천천히 미리 받아 둔다"

    def add_arguments(self, parser):
        area = parser.add_mutually_exclusive_group(required=True)
        area.add_argument("--bbox", help="서,남,동,북 (위경도)")
        area.add_argument("--around", help="위도,경도 — --km 와 함께")
        parser.add_argument("--km", type=float, default=5.0, help="--around 의 반지름")
        parser.add_argument("--zooms", default="10-15")
        parser.add_argument("--layers", default=",".join(DEFAULT_LAYERS))
        parser.add_argument("--meta", type=int, default=4,
                            help="큰 그림 한 변에 타일 몇 장 (1·2·4·8). 4 면 2048 px 에 16 장")
        parser.add_argument("--rate", type=float, default=1.0, help="1 초에 몇 번 묻나 (최대 2)")
        parser.add_argument("--max", type=int, default=2000, help="한 번에 최대 몇 번 묻나")
        parser.add_argument("--dry-run", action="store_true", help="받지 않고 셈만 한다")

    def handle(self, *args, **o):
        bbox = self._bbox(o)
        zooms = parse_zooms(o["zooms"])
        layers = [n.strip() for n in o["layers"].split(",") if n.strip()]
        rows = dict(Layer.objects.filter(name__in=layers, enabled=True).values_list("name", "upstream"))
        unknown = [n for n in layers if n not in rows and n not in NOT_LAYERS]
        if unknown:
            raise CommandError(f"카탈로그에 없거나 꺼진 레이어: {', '.join(unknown)}")
        plans = {name: NOT_LAYERS[name]() if name in NOT_LAYERS else plan_for(name, rows[name])
                 for name in layers}
        cannot = [n for n, p in plans.items() if p is None]
        if cannot:
            raise CommandError(f"미리 받을 수 없는 레이어(타일이 아니다): {', '.join(cannot)}")
        rate = min(max(o["rate"], 0.1), 2.0)          # 2 번/초 위로는 올리지 않는다
        meta = o["meta"]
        if meta not in (1, 2, 4, 8):
            raise CommandError("--meta 는 1·2·4·8 가운데 하나")

        # 타일을 블록으로 묶는다 — WMS 는 meta×meta, 표고는 4×4, 나머지는 1×1. 빠진 타일이
        # 하나라도 있는 블록만 묻는다
        blocks, have, missing = {}, 0, 0
        for name, plan in plans.items():
            m = plan.block(meta)
            for z in zooms:
                for _, x, y in plan.tiles_for(bbox, z):
                    if tilecache.get(plan.key(z, x, y)) is None:
                        missing += 1
                        blocks.setdefault((name, z, x // m, y // m), True)
                    else:
                        have += 1
        todo = list(blocks)
        batch = todo[:o["max"]]
        wms = f"(WMS 는 큰 그림 {512 * meta}px)" if any(isinstance(p, WmsPlan) for p in plans.values()) else ""
        self.stdout.write(
            f"타일 {have + missing:,}장 — 이미 있는 것 {have:,}, 받을 것 {missing:,}. "
            f"{len(todo):,}번에 나눠 묻는다{wms}. 이번에 {len(batch):,}번, "
            f"약 {math.ceil(sum(plans[b[0]].seconds(rate, meta) for b in batch) / 60)}분.")
        if o["dry_run"] or not batch:
            return
        if any(p.upstream == "kigam" for p in plans.values()) and not kigam.has_key():
            raise CommandError("인증키가 없다")

        got = fails = in_a_row = 0
        gap = 1.0 / rate
        for i, (name, z, bx, by) in enumerate(batch, start=1):
            plan = plans[name]
            started = time.monotonic()
            try:
                got += plan.fetch_block(z, bx, by, plan.block(meta))
            except PREWARM_ERRORS as exc:
                fails += 1
                in_a_row += 1
                if usage.paused() or "차단" in str(exc):
                    self.stderr.write(self.style.ERROR(f"차단 조짐 — 멈춘다: {exc}"))
                    break
                if in_a_row >= 3:
                    self.stderr.write(self.style.ERROR(f"연달아 3 번 실패 — 멈춘다: {exc}"))
                    break
            else:
                in_a_row = 0
            if i % 50 == 0:
                self.stdout.write(f"  {i:,}/{len(batch):,}번 — 타일 {got:,}장, 실패 {fails}")
            if plan.remote:                           # GeoMAP 은 우리 디스크라 쉬지 않는다
                time.sleep(max(0.0, gap - (time.monotonic() - started)))
        self.stdout.write(self.style.SUCCESS(
            f"물은 것 {i:,}번, 담은 타일 {got:,}장, 실패 {fails}번. 남은 블록 {len(todo) - i + fails:,}."))

    def _bbox(self, o):
        try:
            if o["bbox"]:
                w, s, e, n = (float(v) for v in o["bbox"].split(","))
            else:
                lat, lon = (float(v) for v in o["around"].split(","))
                dlat = o["km"] / 111.0
                dlon = o["km"] / (111.0 * math.cos(math.radians(lat)))
                w, s, e, n = lon - dlon, lat - dlat, lon + dlon, lat + dlat
        except ValueError as exc:
            raise CommandError("범위를 읽지 못했다 — --bbox 서,남,동,북 / --around 위도,경도") from exc
        if not (w < e and s < n):
            raise CommandError("범위가 뒤집혀 있다")
        return w, s, e, n


# ── 상류마다 받는 꼴 ────────────────────────────────────────────────

PREWARM_ERRORS = views.UPSTREAM_ERRORS + (gsj.GsjError, elevation.ElevationError, trek.TrekError, OSError, ValueError)


def _crop(content, nx, ny, size):
    """큰 그림을 타일로 자른다. {(dx, dy): PNG 바이트}"""
    image = Image.open(io.BytesIO(content))
    pieces = {}
    for dx in range(nx):
        for dy in range(ny):
            buf = io.BytesIO()
            image.crop((dx * size, dy * size, dx * size + size, dy * size + size)).save(
                buf, format="PNG", optimize=True)
            pieces[(dx, dy)] = buf.getvalue()
    return pieces


class WmsPlan:
    """WMS 로 받는 것 — KIGAM·GEUS·VWorld(3857)와 NPI·KOPRI·유럽 상류(지역의 투영, `tilegrid.Grid`).
    열쇠는 브라우저가 `/wms/` 로 보내는 변수 그대로다 (`views.wms`).

    `zooms` 는 화면이 그 레이어를 그리는 **화면 줌**(카탈로그 행의 `minZoom`·`lastZoom`)이다. 512 px 격자의 줌은 화면 줌보다
    하나 작다 — 화면 줌 13 에서 512 px 타일은 줌 12 다. 화면은 반 단계 넉넉히 보이고(`makeLayer`) OpenLayers 는 가까운 줌을
    고르므로, 격자 줌으로 `처음 - 2` 부터 `마지막` 까지만 받는다. 그 밖은 화면이 묻지 않는 타일이다"""
    remote = True

    def block(self, meta):
        return meta

    def __init__(self, name, upstream, grid=None, zooms=(None, None)):
        self.name, self.upstream, self.grid = name, upstream, grid
        self.first, self.last = zooms
        self.get_map = views._Door(upstream).get_map

    def params(self, z, x, y):
        if self.grid:
            return self.grid.wms_params(self.name, z, x, y)
        return tilegrid.wms_params(self.name, z, x, y)

    def extent(self, z, x, y):
        return (self.grid.tile_extent if self.grid else tilegrid.tile_extent)(z, x, y)

    def seconds(self, rate, meta):
        return max(1 / rate, SECONDS_PER_CALL[meta])

    def tiles_for(self, bbox, z):
        if (self.first and z < self.first - 2) or (self.last and z > self.last):
            return iter(())
        return (self.grid.tiles_for if self.grid else tilegrid.tiles_for)(bbox, z)

    def key(self, z, x, y):
        return views.map_cache_key(kigam.clean_params(self.params(z, x, y)))

    def _last(self, z):
        return self.grid.last(z) if self.grid else (2 ** z - 1, 2 ** z - 1)

    def _bbox_text(self, extent):
        return self.grid.bbox_text(extent) if self.grid else ",".join(tilegrid.js_number(v) for v in extent)

    def fetch_block(self, z, bx, by, meta):
        """블록 하나를 큰 그림으로 받아 잘라 담는다. 담은 타일 수를 돌려준다."""
        last_x, last_y = self._last(z)
        x0, y0 = bx * meta, by * meta
        x1, y1 = min(x0 + meta - 1, last_x), min(y0 + meta - 1, last_y)
        nx, ny = x1 - x0 + 1, y1 - y0 + 1
        if nx == 1 and ny == 1:
            content, _ = self.get_map(self.params(z, x0, y0))
            pieces = {(0, 0): content}
        else:
            sw, ne = self.extent(z, x0, y1), self.extent(z, x1, y0)
            params = dict(self.params(z, x0, y0), width=str(512 * nx), height=str(512 * ny),
                          bbox=self._bbox_text((sw[0], sw[1], ne[2], ne[3])))
            content, _ = self.get_map(params)
            pieces = _crop(content, nx, ny, 512)
        for (dx, dy), data in pieces.items():
            tilecache.put(self.key(z, x0 + dx, y0 + dy), data)
        return len(pieces)


class IngemmetPlan:
    """페루 INGEMMET — 상류의 REST 캐시 z/x/y 를 한 장씩 (`views.ingemmet_tile`, wetherilli 195). 캐시가 있는 줌까지만.
    캐시 밖(바다·나라 밖)은 빈 타일로 담는다 — 화면이 부를 때와 같다"""
    remote = True
    upstream = "ingemmet"

    def block(self, meta):
        return 1

    def __init__(self, name):
        self.name = name

    def seconds(self, rate, meta):
        return max(1 / rate, 2.0 if ingemmet.first_zoom(self.name) else 1.5)   # 캐시 1.3–1.8 초, 단층·습곡 export 1.5–2 초 (2026-10-04)

    def tiles_for(self, bbox, z):
        first = ingemmet.first_zoom(self.name)     # 단층·습곡은 화면이 그리는 줌부터 (wetherilli 222)
        if z > ingemmet.max_zoom(self.name) or (first and z < first):
            return iter(())
        return tilegrid.tiles_for(bbox, z)        # 칸 수(2^z)로 세므로 256 px z/x/y 에도 맞는다 — 일본과 같다

    def key(self, z, x, y):
        return views.ingemmet_tile_key(self.name, z, x, y)

    def fetch_block(self, z, x, y, meta):
        png = ingemmet.get_tile(self.name, z, x, y)
        tilecache.put(self.key(z, x, y), png if png is not None else views.tiles.blank_tile(256, 256))
        return 1


class GsjPlan:
    """GSJ — z/x/y 타일을 한 장씩 (`views.gsj_tile`). 줌 밖은 묻지 않는다."""
    remote = True
    upstream = "gsj"

    def block(self, meta):
        return 1

    def __init__(self, name):
        self.name = name
        self.spec = gsj.LAYERS[name]

    def seconds(self, rate, meta):
        return 1 / rate

    def tiles_for(self, bbox, z):
        if not (self.spec["min"] <= z <= self.spec["max"]):
            return iter(())
        return tilegrid.tiles_for(bbox, z)

    def key(self, z, x, y):
        return views.gsj_tile_key(self.name, z, x, y)

    def fetch_block(self, z, x, y, meta):
        tilecache.put(self.key(z, x, y), gsj.get_tile(self.name, z, x, y))
        return 1


class GeomapPlan:
    """남극 GeoMAP — 상류가 없다. 화면이 부를 256 px 타일을 미리 굽는다 (`views.geomap_tile`)."""
    remote = False
    upstream = "geomap"

    def block(self, meta):
        return 1

    def __init__(self, name):
        if not geomap.available():
            raise CommandError("GeoMAP 자료가 서버에 없다")
        self.name = name

    def seconds(self, rate, meta):
        return 0.3                 # 굽는 데 드는 초 남짓. 상류가 없어 쉬지 않는다

    def tiles_for(self, bbox, z):
        if z > geomap.MAX_ZOOM:
            return
        min_x, min_y, max_x, max_y = tilegrid.projected_bbox(bbox, "EPSG:3031")
        x0, y0 = geomap.tile_of(z, min_x, max_y)
        x1, y1 = geomap.tile_of(z, max_x, min_y)
        last = 2 ** z - 1
        for x in range(max(0, x0), min(last, x1) + 1):
            for y in range(max(0, y0), min(last, y1) + 1):
                yield z, x, y

    def key(self, z, x, y):
        return views.geomap_tile_key(self.name, z, x, y, geomap.TILE)

    def fetch_block(self, z, x, y, meta):
        png = geomap.render(self.name, geomap.tile_bbox(z, x, y), geomap.TILE, geomap.TILE)
        tilecache.put(self.key(z, x, y), png)
        return 1


class DemPlan:
    """3D 의 극지 지형 — PGC ArcticDEM·REMA 를 편 Terrarium 타일 (`views.dem_tile`, 034).
    서버가 부를 때처럼 4×4 네모를 한 번에 받는다(`elevation.polar_block`). 위도 60° 안쪽과
    줌 11 밑은 3D 가 AWS 를 곧장 부르므로 받지 않는다."""
    remote = True
    upstream = "pgc"

    def block(self, meta):
        return elevation.POLAR_BLOCK

    def seconds(self, rate, meta):
        return max(1 / rate, 5.0)  # 네모 하나에 5 초 남짓 (2026-09-29)

    def tiles_for(self, bbox, z):
        if not (elevation.POLAR_MIN_ZOOM <= z <= elevation.POLAR_MAX_ZOOM):
            return
        for _, x, y in tilegrid.tiles_for(bbox, z):
            if abs(elevation._tile_lat(z, y)) >= elevation.POLAR_LAT:
                yield z, x, y

    def key(self, z, x, y):
        return elevation.polar_key(z, x, y)

    def fetch_block(self, z, bx, by, block):
        return elevation.polar_block(z, bx * block, by * block)


class TrekPlan:
    """달·화성 — NASA Trek 의 지질도·표고를 그 몸의 경위도 격자로 한 장씩 (`views.moon_tile`·`moon_dem`·`mars_tile`·
    `mars_dem`, wetherilli 158). 격자는 줌 0 이 가로 2 장·세로 1 장, y 는 북쪽부터(`trek.valid_tile`). 열쇠는 뷰와 같은 함수다"""
    remote = True
    upstream = "trek"

    def __init__(self, key, fetch, max_zoom):
        self.key, self._fetch, self.max_zoom = key, fetch, max_zoom

    def block(self, meta):
        return 1

    def seconds(self, rate, meta):
        return 1 / rate

    def tiles_for(self, bbox, z):
        if z > self.max_zoom:
            return
        west, south, east, north = bbox
        span = 180.0 / 2 ** z
        # 끝이 칸 경계에 딱 걸리면 그 너머 칸은 넣지 않는다
        x0, x1 = max(0, int((west + 180) // span)), min(2 ** (z + 1) - 1, math.ceil((east + 180) / span) - 1)
        y0, y1 = max(0, int((90 - north) // span)), min(2 ** z - 1, math.ceil((90 - south) / span) - 1)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                yield z, x, y

    def fetch_block(self, z, x, y, meta):
        tilecache.put(self.key(z, x, y), self._fetch(z, x, y))
        return 1


def _moon_layer(layer):
    return lambda: TrekPlan(lambda z, x, y: views.moon_tile_key(layer, z, x, y),
                            lambda z, x, y: trek.get_tile(layer, z, x, y), trek.MAX_ZOOM)


#: 카탈로그의 레이어가 아닌데 미리 받을 수 있는 것. 달·화성은 Trek 을 거치는 것만 — 원도·크레이터는 우리 파일이라 받을 것이 없다
NOT_LAYERS = {
    "dem": DemPlan,
    **{f"moon:{layer}": _moon_layer(layer) for layer in trek.LAYERS},
    # 받는 함수는 부를 때 찾는다(`lambda`) — 미리 붙잡아 두면 시험이 바꿔 끼운 것을 못 보고 상류를 탄다
    "moon:dem": lambda: TrekPlan(views.moon_dem_key, lambda z, x, y: trek.dem_tile(z, x, y), trek.DEM_MAX_ZOOM),
    "mars:units": lambda: TrekPlan(lambda z, x, y: views.mars_tile_key("units", z, x, y),
                                   lambda z, x, y: trek.mars_tile(z, x, y), trek.MARS_MAX_ZOOM),
    "mars:dem": lambda: TrekPlan(views.mars_dem_key, lambda z, x, y: trek.mars_dem_tile(z, x, y),
                                 trek.MARS_DEM_MAX_ZOOM),
}


#: 화면이 카탈로그 행의 투영으로 받는 유럽·북극 상류(`map.js` 의 `npolarSource`) — 투영과 그리는 줌은 `views._layer_extra` 가 정한다
#: (wetherilli 182). 같은 상류도 판마다(IGME 1:100만 4326·MAGNA 3857), 레이어군마다(EMODnet 북극해 3413·유럽 바다 3857) 다르다.
#: PGC 경사·등고선(wetherilli 099)도 같은 길이다 — 182 가 "더하면 된다" 고 남긴 것 (wetherilli 203)
PROJECTED = ("pgc", "emodnet", "ngu", "gtk", "bgs", "brgm", "egdi", "bgr", "igme", "gsi", "gsni", "sgc", "sgb", "segemar", "dinamige",
             "iige", "mrdata", "sgm", "cgmw", "aga", "bumigeb", "irgm", "nrcan", "ogs", "sigeom", "ygs", "skgs", "nsgs", "ga", "gsq", "gsv", "gssa", "ispra", "lneg", "swisstopo", "sgu", "natt", "gns", "mris", "gsiindia", "sgs", "esdm", "jmg", "mgb", "dmr", "bcgs", "calgs", "geosphere", "pig", "tno", "dov", "spw")


def _projected_plan(name, upstream):
    layer = Layer.objects.select_related("group").filter(name=name, upstream=upstream).first()
    if layer is None or layer.kind in ("vector", "points"):
        return None
    extra = views._layer_extra(layer)
    crs = extra.get("projection")
    if crs not in tilegrid.EXTENT and crs != "EPSG:3857":
        return None
    # 3857 은 화면의 `createXYZ` 가 `wmsSource` 와 같은 격자다 — KIGAM 과 같은 셈을 탄다
    grid = None if crs == "EPSG:3857" else tilegrid.Grid(crs)
    return WmsPlan(name, upstream, grid, (extra.get("minZoom"), extra.get("lastZoom")))


def plan_for(name, upstream):
    """레이어 하나를 어떻게 받나. 타일이 아니면(점·모양·연구실 타일) None."""
    if upstream in ("kigam", "geus", "vworld"):
        row = Layer.objects.filter(name=name).values_list("kind", flat=True).first()
        return None if row in ("vector", "points") else WmsPlan(name, upstream)
    if upstream == "npolar" and npolar.knows(name):
        return WmsPlan(name, upstream, tilegrid.Grid(npolar.TILES[name]["projection"]))
    if upstream == "kopri" and kopri.knows_wms(name):
        # KPDC 지도 서버(057) — NPI 처럼 지역의 투영으로 받는다(`views._layer_extra` 의 `kopri.wms_projection`) (wetherilli 158)
        return WmsPlan(name, upstream, tilegrid.Grid(kopri.wms_projection(name)))
    if upstream in PROJECTED:
        return _projected_plan(name, upstream)
    if upstream == "gsj" and gsj.knows(name):
        return GsjPlan(name)
    if upstream == "ingemmet" and ingemmet.knows_tiles(name):
        return IngemmetPlan(name)
    if upstream == "geomap" and name in geomap.LAYERS:
        return GeomapPlan(name)
    return None
