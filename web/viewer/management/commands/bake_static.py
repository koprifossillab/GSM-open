"""정적 판(GitHub Pages)에 실을 것을 미리 굽는다 — `manage.py bake_static <outdir>` (wetherilli 160, P11).

서버가 우리 파일에서 그때그때 그려 주는 것을 정적 파일로 떠 둔다. **출력 경로는 화면이 지금 부르는 주소 꼴과 같다** —
정적 판의 map.js 는 `BASE` 만 바꿔 그대로 읽는다. 다만 `?layer=` 처럼 물음이 붙는 주소는 파일이 될 수 없어 꼴을 바꾼다
(아래 `points`). 다 구우면 `<outdir>/manifest.json` 에 경로·크기·레이어마다의 마지막 줌을 적는다.

    geomap/<레이어>/<z>/<x>/<y>.png        남극 GeoMAP (3031 격자) — 자료가 없는 타일은 굽지 않는다(404 → 빈칸)
    legend/geomap/<레이어>.png              GeoMAP 범례
    ibcso/<bed|ice>/<z>/<x>/<y>.webp        IBCSO 해저·빙저 지형 — 잘라 둔 파일을 옮긴다
    ibcso/tid/<z>/<x>/<y>.png               IBCSO 자료 출처
    points/<상류>/<이름>.json               점 레이어 (`points/?layer=<상류>:<이름>` 의 답). 언어에 따라 답이 다른 것은
    points/<상류>/<이름>.en.json            영어판을 따로 — 얀마옌·극지연구소
    peninsula/<shaded|plain>/<z>/<x>/<y>.webp  한반도 지질도 음영판·민판 — `--with peninsula` 일 때만

자료는 서버와 같은 설정(`GSM_GEOMAP_DIR`·`GSM_IBCSO_DIR`·`GSM_NPOLAR_DIR`·`GSM_KOPRI_DIR`·`GSM_PENINSULA_DIR`)에서 읽고
**쓰지 않는다.** GeoMAP 은 캐시에 같은 타일이 있으면 그것을 읽기만 한다. 점 레이어는 서버와 같은 길(`views.point_features`)로
받는다 — 캐시에 없으면 상류(그린란드 포털·NPI)에 묻고 그 캐시(`GSM_TILE_CACHE_DIR`)에 담는다.
"""
import json
import shutil
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from viewer import geomap, grportal, ibcso, janmayen, kopri, npolar, peninsula, tilecache, views

#: GeoMAP 레이어마다 굽는 마지막 줌. 2026-10-02 에 쟀다(devlog wetherilli 160) — 면 레이어 하나가 줌 9 까지 1 만 장·30 MB,
#: 줌 10 까지 2 만 7 천 장·70 MB 남짓. 간추린 지질도만 10 까지
GEOMAP_ZOOMS = {
    "geomap_simple_geology": 10,
    "geomap_simple_lithology": 9,
    "geomap_chronostratigraphic": 9,
    "geomap_lithostratigraphic": 9,
    "geomap_faults": 9,
    "geomap_quality": 8,
}
PARTS = ("geomap", "ibcso", "points", "peninsula")
DEFAULT_PARTS = ("geomap", "ibcso", "points")
#: GitHub Pages — 파일 하나 100 MB, 사이트 1 GB 가 권장 한도다
FILE_LIMIT = 100 * 1024 * 1024
SITE_LIMIT = 1024 * 1024 * 1024


class Command(BaseCommand):
    help = "정적 판에 실을 GeoMAP·IBCSO·점 레이어(·한반도 음영판)를 굽는다 (wetherilli 160)"

    def add_arguments(self, parser):
        parser.add_argument("outdir", help="구운 것을 둘 곳 (없으면 만든다)")
        parser.add_argument("--only", default=",".join(DEFAULT_PARTS),
                            help=f"굽는 몫, 쉼표로 ({', '.join(PARTS)}). 기본 {','.join(DEFAULT_PARTS)}")
        parser.add_argument("--with", dest="extra", default="", help="기본 몫에 더할 것 — 예: peninsula")
        parser.add_argument("--geomap-zoom", action="append", default=[], metavar="레이어=줌",
                            help="GeoMAP 레이어의 마지막 줌을 바꾼다 (여러 번). 줌 0 이면 그 레이어를 굽지 않는다")
        parser.add_argument("--measure", action="store_true",
                            help="굽지 않고 GeoMAP 의 줌마다 자료가 있는 타일 수만 센다")

    def handle(self, *args, **opts):
        parts = [p for p in (opts["only"] + "," + opts["extra"]).split(",") if p]
        unknown = set(parts) - set(PARTS)
        if unknown:
            raise CommandError(f"모르는 몫이다: {', '.join(sorted(unknown))}")
        zooms = dict(GEOMAP_ZOOMS)
        for item in opts["geomap_zoom"]:
            layer, _, z = item.partition("=")
            if layer not in geomap.LAYERS or not z.isdigit():
                raise CommandError(f"--geomap-zoom 은 레이어=줌 꼴이다: {item}")
            zooms[layer] = int(z)
        if opts["measure"]:
            self.measure(zooms)
            return
        out = Path(opts["outdir"])
        out.mkdir(parents=True, exist_ok=True)
        self.out, self.files, self.started = out, [], time.time()
        manifest = {"made": time.strftime("%Y-%m-%d %H:%M"), "parts": {}}
        for part in PARTS:
            if part in parts:
                manifest["parts"][part] = getattr(self, f"bake_{part}")(zooms)
        total = sum(size for _, size in self.files)
        # 폴더(둘째 마디까지)마다의 합을 앞에 — 9 만 줄을 읽지 않고 크기를 본다
        dirs = {}
        for path, size in self.files:
            head = "/".join(path.split("/")[:2])
            dirs[head] = dirs.get(head, 0) + size
        manifest["total_bytes"] = total
        manifest["dirs"] = dict(sorted(dirs.items()))
        # 파일은 [경로, 바이트] — 9 만 줄이라 짧게 적는다
        manifest["files"] = [[p, s] for p, s in sorted(self.files)]
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                                           encoding="utf-8")
        self.stdout.write(f"{len(self.files):,} 파일 · {total / 1e6:.1f} MB · {time.time() - self.started:.0f} 초 → {out}")
        big = [p for p, s in self.files if s > FILE_LIMIT]
        if big:
            self.stderr.write(f"100 MB 를 넘는 파일이 있다 (Pages 가 받지 않는다): {', '.join(big)}")
        if total > SITE_LIMIT:
            self.stderr.write(f"모두 {total / 1e9:.2f} GB — Pages 의 사이트 한도(1 GB)를 넘는다")

    # ── 적기 ───────────────────────────────────────────────────────

    def write(self, rel: str, data: bytes):
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.files.append((rel, len(data)))

    def copy_tree(self, src: Path, rel: str) -> int:
        """잘라 둔 타일 폴더(`z/x/y.확장자`)를 그대로 옮긴다. 옮긴 파일 수."""
        n = 0
        for f in sorted(src.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                target = f"{rel}/{f.relative_to(src).as_posix()}"
                (self.out / target).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, self.out / target)
                self.files.append((target, f.stat().st_size))
                n += 1
        return n

    # ── GeoMAP ─────────────────────────────────────────────────────

    @staticmethod
    def _has_data(layer, z, x, y) -> bool:
        """그 타일에 기하가 하나라도 걸치나 (R*Tree). 걸쳐도 그려 보면 빌 수 있다 — 그건 그린 뒤에 거른다."""
        conn, meta = geomap._table(geomap.style_of(layer).table)
        x0, y0, x1, y1 = geomap.tile_bbox(z, x, y)
        return conn.execute(f'SELECT 1 FROM "{meta["rtree"]}" WHERE maxx >= ? AND minx <= ? AND maxy >= ? AND miny <= ? '
                            "LIMIT 1", (x0, x1, y0, y1)).fetchone() is not None

    def measure(self, zooms):
        if not geomap.available():
            raise CommandError("GeoMAP 자료가 없다 (GSM_GEOMAP_DIR)")
        for layer in geomap.LAYERS:
            level, counts = [(0, 0)], []
            for z in range(0, max(zooms.values()) + 1):
                level = [(x, y) for x, y in level if self._has_data(layer, z, x, y)]
                counts.append(len(level))
                level = [(2 * x + dx, 2 * y + dy) for x, y in level for dx in (0, 1) for dy in (0, 1)]
            self.stdout.write(f"{layer}: " + " ".join(f"z{z}={n:,}" for z, n in enumerate(counts)))

    def bake_geomap(self, zooms):
        """레이어마다 줌 0 부터 내려가며 굽는다. 자료가 없거나 그려 보니 빈 타일은 굽지 않고 그 아래로도 내려가지 않는다.
        캐시에 같은 타일이 있으면 그것을 쓴다(쓰지는 않는다)."""
        from PIL import Image
        import io

        if not geomap.available():
            self.stderr.write("GeoMAP 자료가 없어 건너뛴다 (GSM_GEOMAP_DIR)")
            return {"skipped": "no data"}
        report = {}
        for layer, last in zooms.items():
            if last <= 0:
                continue
            level, made, empty, cached = [(0, 0)], 0, 0, 0
            for z in range(0, last + 1):
                keep = []
                for x, y in level:
                    if not self._has_data(layer, z, x, y):
                        continue
                    png = tilecache.get(views.geomap_tile_key(layer, z, x, y, geomap.TILE))
                    if png is None:
                        png = geomap.render(layer, geomap.tile_bbox(z, x, y), geomap.TILE, geomap.TILE)
                    else:
                        cached += 1
                    if Image.open(io.BytesIO(png)).getextrema()[3][1] == 0:
                        empty += 1
                        continue
                    self.write(f"geomap/{layer}/{z}/{x}/{y}.png", png)
                    made += 1
                    keep.append((x, y))
                level = [(2 * x + dx, 2 * y + dy) for x, y in keep for dx in (0, 1) for dy in (0, 1)]
                self.stdout.write(f"  {layer} z{z}: {len(keep):,} 장")
            legend, _ = geomap.get_legend(layer)
            self.write(f"legend/geomap/{layer}.png", legend)
            report[layer] = {"max_zoom": last, "tiles": made, "empty_skipped": empty, "from_cache": cached}
        return report

    # ── IBCSO ──────────────────────────────────────────────────────

    def bake_ibcso(self, zooms):
        report = {}
        for name, sheet in ibcso.SHEETS.items():
            kind = name.split(":", 1)[1]
            if not sheet.available():
                self.stderr.write(f"IBCSO {kind} 타일이 없어 건너뛴다 (GSM_IBCSO_DIR)")
                continue
            report[kind] = {"files": self.copy_tree(sheet.tiles_dir(), f"ibcso/{kind}"), "max_zoom": ibcso.MAX_ZOOM}
        if ibcso.tid_available():
            report["tid"] = {"files": self.copy_tree(ibcso.tid_tiles_dir(), "ibcso/tid"), "max_zoom": ibcso.MAX_ZOOM}
        else:
            self.stderr.write("IBCSO 자료 출처 타일이 없어 건너뛴다")
        return report

    # ── 점 레이어 ──────────────────────────────────────────────────

    @staticmethod
    def _point_path(name: str, lang: str = "") -> str:
        upstream, _, rest = name.partition(":")
        return f"points/{upstream}/{rest}{'.' + lang if lang else ''}.json"

    def bake_points(self, zooms):
        report = {}
        # 그린란드 포털·NPI — 언어와 상관없는 덩이. 캐시에 없으면 상류에 묻는다(장 사이에 쉰다)
        for module, names in ((grportal, list(grportal.LAYERS)), (npolar, list(npolar.POINTS))):
            for name in names:
                try:
                    body = module.body(name, views.point_features(name))
                except views.POINT_ERRORS as exc:
                    self.stderr.write(f"{name} 을 받지 못했다: {exc}")
                    continue
                self.write(self._point_path(name), body)
                report[name] = {"bytes": len(body)}
                self.stdout.write(f"  {name}: {len(body) / 1e3:.0f} KB")
        # 얀마옌·극지연구소 — 팝업 이름·갈래가 언어마다 다르다. 아라온호 항적은 매시간 자라고 연구실 안에서만이라 빼낸다
        langed = [(janmayen, n, janmayen.available(n)) for n in janmayen.LAYERS]
        langed += [(kopri, n, True) for n in kopri.LAYERS if kopri.knows_file(n) and kopri.file_of(n) != "araon"]
        for module, name, ok in langed:
            if not ok:
                self.stderr.write(f"{name} 자료가 없어 건너뛴다")
                continue
            try:
                for lang in ("ko", "en"):
                    body = janmayen.body(name, lang) if module is janmayen else kopri.file_body(name, lang)
                    self.write(self._point_path(name, "" if lang == "ko" else lang), body)
            except (FileNotFoundError, OSError, ValueError, janmayen.JanMayenError) as exc:
                self.stderr.write(f"{name} 을 읽지 못했다: {exc}")
                continue
            report[name] = {"bytes": len(body), "lang": True}
            self.stdout.write(f"  {name}: {len(body) / 1e3:.0f} KB (언어 둘)")
        return report

    # ── 한반도 음영판·민판 ─────────────────────────────────────────

    def bake_peninsula(self, zooms):
        """연구실 내부용(`views.LAB_ONLY`)이었다. 기본으로는 굽지 않고 `--with peninsula` 일 때만."""
        report = {}
        for name, sheet in peninsula.SHEETS.items():
            kind = name.split(":", 1)[1]
            if not sheet.available():
                self.stderr.write(f"{name} 타일이 없어 건너뛴다 (GSM_PENINSULA_DIR)")
                continue
            report[kind] = {"files": self.copy_tree(sheet.tiles_dir(), f"peninsula/{kind}")}
        return report
