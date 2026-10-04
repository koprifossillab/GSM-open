"""카탈로그의 레이어가 **실제로 그려지는지** 모든 상류에 한 장씩 대조한다 (KIGAM 은 devlog 006, 모든 상류는 wetherilli 298).

    manage.py verify_layers                       # 아직 확인하지 않은 것만
    manage.py verify_layers --redo                # 전부 다시
    manage.py verify_layers --upstream sgm,sgc    # 그 상류만
    manage.py verify_layers --only geology --redo
    manage.py verify_layers --redo --skip geus    # 멈춘 상류를 빼고 이어 간다

레이어마다 **그 레이어의 범위 한가운데 칸 하나**를 화면이 받는 꼴 그대로 문으로 받는다 — 꼴은 미리 데우기의 계획(`prewarm.plan_for`)을
빌린다(3857 WMS·지역 투영 WMS·GSJ z/x/y·INGEMMET 타일 캐시·우리가 굽는 GeoMAP). 받은 것을 셋으로 가른다.

- **그림** — 칠한 화소가 있다. `Layer.verified_at` 에 날짜를 남긴다(레이어 패널의 "대조 안 함" 표가 떨어진다)
- **빈 그림** — 다 투명하거나 흰 바탕뿐이다. 한가운데가 바다·빈 땅일 수도 있어 귀퉁이 쪽 넷을 더 본다. 다 비면 빈 그림으로 적는다
- **오류** — 문이 오류를 냈거나 그림이 아니다

타일이 아닌 레이어(점·모양·벡터, 화면이 상류를 곧장 부르는 것)는 **건너뜀**으로 센다. 끝에 상류마다 표를 낸다.

**천천히 간다 — 미리 데우기와 같은 규칙이다**(devlog 010). 한 장 사이 1 초(`--delay`), **차단 조짐이 보이면 곧장 멈춘다.** 한 상류가
연달아 세 번 오류면 그 상류의 남은 레이어는 묻지 않는다(다른 상류는 이어 간다). **사람이 부르는 명령이다 — cron 에 두지 않는다.**

KIGAM 만은 예전처럼 안 그려지면 `enabled=False` 로 내리고, 그려지면 다시 켠다 — 문서에 없는 주소에서 온 씨앗이라 그렇게 해 왔다.
다른 상류는 적기만 한다. 상류가 잠깐 아픈 것으로 목록에서 치우지 않는다.

끝에 한 번 더 — `/openapi/wms` 가 `GetFeatureInfo` 를 열었는지 찔러본다(`kigam.probe_openapi_feature_info`, 006). 키가 있을 때만.
`--probe-info` 는 대조를 건너뛰고 이것만 부른다.
"""
import io
import math
import time
from collections import Counter, defaultdict

from PIL import Image

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import gsj, ingemmet, kigam, tilegrid, usage, views
from viewer.models import Layer

from .prewarm import PREWARM_ERRORS, GeomapPlan, GsjPlan, IngemmetPlan, WmsPlan, plan_for

#: 속성을 찔러볼 상자와 레이어 — 한반도 한복판, 상자 한가운데에 면이 반드시 있는 것
PROBE_BBOX = "127.0,36.0,127.4,36.4"
PROBE_LAYER = "L_250K_Geology_Map"
WORLD = (-180.0, -85.0, 180.0, 85.0)
KINDS = ("그림", "빈 그림", "오류", "건너뜀")


def classify(content) -> str:
    """받은 바이트 → 그림·빈 그림·오류"""
    if content is None:
        return "빈 그림"                         # INGEMMET 캐시 밖 — 화면도 빈 칸을 그린다
    try:
        image = Image.open(io.BytesIO(content)).convert("RGBA")
    except (OSError, ValueError):
        return "오류"
    bands = image.getextrema()
    # 다 투명하거나, 투명을 무시하는 상류가 흰 바탕만 준 것. 한 색으로 칠한 칸은 그림이다 — 큰 지층 하나 안을 들여다본 칸일 수 있다
    if bands[3][1] == 0 or all(lo == hi == 255 for lo, hi in bands):
        return "빈 그림"
    return "그림"


def points(bbox) -> list:
    """물어볼 자리 — 한가운데, 비면 네 귀퉁이 쪽 넷(범위의 ¼·¾). 섬나라·해외 영토는 한가운데가 바다이기 쉽다"""
    w, s, e, n = bbox
    at = lambda fx, fy: (w + (e - w) * fx, s + (n - s) * fy)
    return [at(0.5, 0.5), at(0.3, 0.6), at(0.7, 0.4), at(0.3, 0.3), at(0.7, 0.7)]


def first_zoom(plan) -> int:
    """계획이 그리기 시작하는 격자 줌. WMS 는 화면 줌(`minZoom`)보다 하나 작은 512 px 격자다 — 그 밑은 상류가 그리지 않는
    축척일 수 있다(BGS 1:5만·GÜK250·IGME5000 의 축척별 레이어)"""
    if isinstance(plan, WmsPlan):
        return max(0, (plan.first or 0) - 1)
    if isinstance(plan, GsjPlan):
        return plan.spec["min"]
    if isinstance(plan, IngemmetPlan):
        return ingemmet.first_zoom(plan.name) or 0
    return 0


def tile_at(plan, bbox, lon, lat):
    """그 자리를 품은 칸 — 범위의 대략 절반이 한 칸에 드는 줌부터(그리기 시작하는 줌 밑으로는 내려가지 않는다)"""
    width = max(bbox[2] - bbox[0], (bbox[3] - bbox[1]) * 1.5, 1e-3)
    start = max(first_zoom(plan), min(18, round(math.log2(360.0 / width)) + 1))
    tiny = (lon - 1e-6, lat - 1e-6, lon + 1e-6, lat + 1e-6)
    for z in range(start, 19):
        for tile in plan.tiles_for(tiny, z):
            return tile
    return None


def plan_of(layer):
    """미리 데우기의 계획. 거기 없는 문 WMS(GSJ 의 다른 WMS·대만·GEUS ArcGIS·남아공·나미비아 — 미리 데우지 않는 것)는 카탈로그 행의
    투영으로 WmsPlan 을 지어 같은 `/wms/` 꼴로 묻는다. 점 레이어·화면이 곧장 부르는 타일(`tiles`)은 None"""
    plan = plan_for(layer.name, layer.upstream)
    if plan is not None or layer.kind != "wms" or layer.upstream not in views._Door.MODULES or layer.upstream == "geomap":
        return plan
    extra = views._layer_extra(layer)
    crs = extra.get("projection") or "EPSG:3857"      # 적지 않으면 화면의 3857 격자다
    if extra.get("tiles") or views._point_fields(layer) or crs not in (*tilegrid.EXTENT, "EPSG:3857"):
        return None
    return WmsPlan(layer.name, layer.upstream, None if crs == "EPSG:3857" else tilegrid.Grid(crs),
                   (extra.get("minZoom"), extra.get("lastZoom")))


def fetch(plan, z, x, y):
    """칸 하나를 화면이 받는 꼴로 — 캐시를 거치지 않고 문에서 곧장. 담지 않는다"""
    if isinstance(plan, WmsPlan):                # 메타타일 상류도 칸 하나만 묻는다
        content, _ = plan.get_map(kigam.clean_params(plan.params(z, x, y)))
        return content
    if isinstance(plan, GsjPlan):
        return gsj.get_tile(plan.name, z, x, y)
    if isinstance(plan, IngemmetPlan):
        return ingemmet.get_tile(plan.name, z, x, y)
    if isinstance(plan, GeomapPlan):
        return views._geomap_png(plan.name, z, x, y)[0]
    raise ValueError("이 계획은 대조하지 못한다")


class Command(BaseCommand):
    help = "모든 상류의 레이어가 실제로 그려지는지 한 장씩 대조한다 (사람이 부른다)"

    def add_arguments(self, parser):
        parser.add_argument("--delay", type=float, default=1.0, help="한 장 사이에 쉬는 초 (기본 1)")
        parser.add_argument("--only", default="", help="이 글자가 든 레이어명만 본다")
        parser.add_argument("--upstream", default="", help="이 상류만 (쉼표로 여럿)")
        parser.add_argument("--skip", default="", help="이 상류는 빼고 (쉼표로 여럿)")
        parser.add_argument("--redo", action="store_true", help="이미 확인한 것도 다시 본다")
        parser.add_argument("--probe-info", action="store_true",
                            help="대조는 건너뛰고 /openapi/wms 의 GetFeatureInfo 만 찔러본다")

    def handle(self, *args, **o):
        if o["probe_info"]:
            if not kigam.has_key():
                self.stderr.write(self.style.ERROR("인증키가 없다. .env 의 GSM_KIGAM_KEY 를 채운다."))
                return
            self._probe_info()
            return

        layers = Layer.objects.order_by("upstream", "name")
        if o["upstream"]:
            layers = layers.filter(upstream__in=[u.strip() for u in o["upstream"].split(",") if u.strip()])
        if o["skip"]:
            layers = layers.exclude(upstream__in=[u.strip() for u in o["skip"].split(",") if u.strip()])
        if o["only"]:
            layers = layers.filter(name__icontains=o["only"])
        if not o["redo"]:
            layers = layers.filter(verified_at__isnull=True)
        layers = list(layers)
        if not kigam.has_key() and any(l.upstream == "kigam" for l in layers):
            self.stderr.write(self.style.ERROR("인증키가 없다 — KIGAM 레이어는 건너뛴다. .env 의 GSM_KIGAM_KEY 를 채운다."))
        if not layers:
            self.stdout.write("대조할 레이어가 없다.")
            self._probe_info()
            return
        self.stdout.write(f"{len(layers)}개를 대조한다 — 한 장 사이 {o['delay']:g} 초.")

        table = defaultdict(Counter)
        broken = []                                  # (상류, 레이어, 갈래, 까닭)
        in_a_row, given_up = Counter(), set()
        stopped = None
        for index, layer in enumerate(layers, start=1):
            up = layer.upstream
            kind, note, asked = self._one(layer, given_up, o["delay"])
            if kind == "오류":
                in_a_row[up] += 1
                if usage.paused() or "차단" in note:
                    stopped = note
                if in_a_row[up] >= 3:
                    given_up.add(up)
            elif asked:
                in_a_row[up] = 0
            self._save(layer, kind, note)
            table[up][kind] += 1
            if kind in ("빈 그림", "오류"):
                broken.append((up, layer.name, kind, note))
                self.stdout.write(self.style.WARNING(f"  [{index}/{len(layers)}] {up} {layer.name} — {kind}: {note}"))
            elif index % 25 == 0:
                self.stdout.write(f"  [{index}/{len(layers)}] …")
            if stopped:
                self.stderr.write(self.style.ERROR(f"차단 조짐 — 멈춘다: {stopped}"))
                break

        self._report(table, broken, given_up)
        if kigam.has_key():
            self._probe_info()

    def _one(self, layer, given_up, delay):
        """(갈래, 기록, 상류에 물었나)"""
        up = layer.upstream
        if up in given_up:
            return "건너뜀", "앞의 세 레이어가 연달아 오류라 묻지 않았다", False
        if up == "kigam" and not kigam.has_key():
            return "건너뜀", "인증키가 없다", False
        if views._lab_only(layer.name):
            return "건너뜀", "연구실 내부용 — 밖에 연 판이다", False
        try:
            plan = plan_of(layer)
        except CommandError as exc:                  # 우리가 굽는 것의 파일이 없다(GeoMAP 따위)
            return "건너뜀", str(exc), False
        if plan is None:
            return "건너뜀", "타일이 아니다(점·모양·벡터, 또는 화면이 곧장 부른다)", False
        bbox = tuple(layer.bbox) if layer.bbox else WORLD
        result = "빈 그림"
        for lon, lat in points(bbox):
            tile = tile_at(plan, bbox, lon, lat)
            if tile is None:
                return "건너뜀", "그리는 줌에 칸이 없다", False
            z, x, y = tile
            started = time.monotonic()
            try:
                content = fetch(plan, z, x, y)
            except PREWARM_ERRORS as exc:
                return "오류", f"{z}/{x}/{y} {str(exc)[:150]}", True
            finally:
                if plan.remote:
                    time.sleep(max(0.0, delay - (time.monotonic() - started)))
            result = classify(content)
            if result != "빈 그림":
                size = len(content) if content else 0
                return result, f"{z}/{x}/{y} {size:,} bytes" if result == "그림" else f"{z}/{x}/{y} 그림이 아니다", True
        return result, f"{z}/{x}/{y} 다섯 칸 모두 비었다", True

    def _save(self, layer, kind, note):
        layer.verify_note = f"{timezone.localdate():%Y-%m-%d} {kind} — {note}"[:200]
        fields = ["verify_note"]
        if kind == "그림":
            layer.verified_at = timezone.now()
            fields.append("verified_at")
        if layer.upstream == "kigam" and kind in ("그림", "오류"):
            layer.enabled = kind == "그림"            # KIGAM 만 예전처럼 내리고 켠다
            fields.append("enabled")
        layer.save(update_fields=fields)

    def _report(self, table, broken, given_up):
        total = Counter()
        rows = []
        for up in sorted(table):
            total.update(table[up])
            rows.append(f"| {up} | " + " | ".join(str(table[up][k]) for k in KINDS) + " |")
        self.stdout.write("\n| 상류 | " + " | ".join(KINDS) + " |\n|---|" + "---:|" * len(KINDS))
        self.stdout.write("\n".join(rows))
        self.stdout.write("| **모두** | " + " | ".join(str(total[k]) for k in KINDS) + " |\n")
        if broken:
            self.stdout.write("안 그려지는 것:")
            for up, name, kind, note in broken:
                self.stdout.write(f"- {up} `{name}` — {kind}: {note}")
        if given_up:
            self.stdout.write(f"연달아 오류라 남은 레이어를 묻지 않은 상류: {', '.join(sorted(given_up))}")
        self.stdout.write(self.style.SUCCESS(
            f"그림 {total['그림']}, 빈 그림 {total['빈 그림']}, 오류 {total['오류']}, 건너뜀 {total['건너뜀']}"))
        if total["오류"] and table.get("kigam", {}).get("오류"):
            self.stdout.write("KIGAM 의 안 되는 것은 enabled=False 로 내렸다. 까닭은 Layer.verify_note 에 있다.")

    def _probe_info(self):
        result = kigam.probe_openapi_feature_info(PROBE_LAYER, PROBE_BBOX)
        style = self.style.SUCCESS if result.startswith("열렸다") else self.style.NOTICE
        self.stdout.write(style(f"/openapi/wms 의 GetFeatureInfo: {result}"))
