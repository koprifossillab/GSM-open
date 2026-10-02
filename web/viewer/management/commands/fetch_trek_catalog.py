"""Trek 의 판 목록을 받아 `data/<몸>_trek_layers.json` 씨앗에 적는다 (devlog 060).

색인(`searchItems`)에서 판을 받고, 판마다 `WMTSCapabilities.xml` 을 한 번 물어 포맷·줌 끝을 적는다. Capabilities 가
있어도 줌 0 타일 한 장을 받아 보고, 없으면(404) WMTS 가 없는 판으로 친다(wetherilli 090). WMTS 가 없으면 ArcGIS
MapServer 를 찾아 적는다(`kind: map` — 우리 문이 타일을 굽는다).
**1 초에 한 번**이고 달은 1 200 남짓이라 40 분쯤 걸린다(판마다 둘). 한 번 물은 판은 다시 묻지 않는다(`--reprobe` 로 다시).
실패가 잇따르면 멈추고 그때까지 물은 것을 적는다 — 다시 부르면 이어서 묻는다.

끝에 극지 짝(`<판>_SP`·`_NP`)을 찾는다 — 서비스 목록 셋에서 이름으로 모으고, 짝이 있는 판만 극 WMTS 를 묻는다
(달은 70 판 남짓, wetherilli 085). 이것도 한 번 물은 판은 다시 묻지 않는다.

씨앗의 `ko`(한글 제목)·`hide`(목록에서 숨김)는 **사람이 손질하는 칸**이라 다시 받아도 지키지 않는다 — 없을 때만
채운다. 상류에서 사라진 판은 씨앗에서도 지운다. 사람이 가끔 부른다.
"""
import json
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import trek

#: 사람이 손질하는 칸 — 다시 받아도 지킨다
KEPT = ("ko", "hide")
#: 잇따른 실패가 이만큼이면 멈춘다 — 막힌 것일 수 있다
MAX_FAILS = 5


class Command(BaseCommand):
    help = "Trek 의 판 목록(달, --body mars·mercury 면 화성·수성)을 받아 data/*_trek_layers.json 에 적는다"

    def add_arguments(self, parser):
        parser.add_argument("--body", choices=tuple(trek.BODIES), default="moon")
        parser.add_argument("--reprobe", action="store_true", help="이미 물은 판의 WMTS 도 다시 묻는다")
        parser.add_argument("--delay", type=float, default=1.0, help="WMTS 를 묻는 간격(초). 1 밑으로 두지 않는다")
        parser.add_argument("--limit", type=int, default=0, help="이번에 물을 판의 수 (0 이면 모두)")

    def handle(self, *args, **o):
        body = o["body"]
        delay = max(1.0, o["delay"])
        try:
            items = trek.catalog_items(body)
        except trek.TrekError as exc:
            raise CommandError(str(exc))
        # 수성은 판이 53 개다(2026-10-02) — 달 1 200·화성 240 남짓보다 훨씬 적다
        if len(items) < (40 if body == "mercury" else 100):
            raise CommandError(f"판이 {len(items)} 개뿐이다 — 상류가 이상하다. 적지 않는다")
        old = {e["id"]: e for e in trek.load_catalog(body)}
        today = timezone.localdate().isoformat()
        layers = []
        for item in items:
            prev = old.get(item["id"], {})
            entry = dict(item)
            entry["ko"] = prev.get("ko", "")
            entry["hide"] = prev["hide"] if "hide" in prev else trek.hidden_by_default(body, item)
            for key in ("kind", "ms", "ext", "max", "z0", "probed", "polar"):
                if key in prev:
                    entry[key] = prev[key]
            layers.append(entry)
        gone = len(set(old) - {e["id"] for e in layers})

        # WMTS 가 없던 판 가운데 MapServer 를 아직 안 찾아본 것 — 먼저 받은 씨앗을 이어 채운다
        todo = [e for e in layers if o["reprobe"] or "probed" not in e
                or (e.get("kind") is None and "ms" not in e)]
        if o["limit"]:
            todo = todo[:o["limit"]]
        self.stdout.write(f"판 {len(layers)} 개 (사라진 것 {gone}) — WMTS 를 물을 것 {len(todo)} 개, "
                          f"{delay:g} 초 간격이면 {len(todo) * 2 * delay / 60:.0f} 분 남짓")
        fails = 0
        for i, entry in enumerate(todo, 1):
            try:
                if o["reprobe"] or "probed" not in entry:
                    info = trek.wmts_info(body, entry["id"])
                    # Capabilities 만 있고 타일이 404 인 판이 있다 — 한 장 받아 보고 적는다 (wetherilli 090)
                    if info:
                        time.sleep(delay)
                        if not trek.tile_exists(body, entry["id"], info, entry.get("bbox"), delay):
                            info = None
                else:
                    info = None
                ms = "" if info else trek.find_mapserver(body, entry.get("uuid", ""), entry["id"])
            except trek.TrekError as exc:
                fails += 1
                self.stderr.write(f"  {entry['id']}: {exc}")
                if fails >= MAX_FAILS:
                    self.stderr.write(f"실패가 {fails} 번 잇따랐다 — 멈춘다. 다시 부르면 이어서 묻는다")
                    break
                time.sleep(delay)
                continue
            fails = 0
            entry["kind"] = "tile" if info else "map" if ms else None
            entry["ms"] = ms
            entry["ext"] = info["ext"] if info else None
            entry["max"] = info["max"] if info else None
            entry["z0"] = info["z0"] if info else None
            entry["probed"] = today
            if i % 50 == 0:
                self._write(body, layers, today)
                self.stdout.write(f"  {i}/{len(todo)}")
            time.sleep(delay)
        self._write(body, layers, today)
        if fails < MAX_FAILS:
            self._polar(body, layers, today, delay, o["reprobe"])
        tiles = sum(1 for e in layers if e.get("kind") == "tile")
        maps = sum(1 for e in layers if e.get("kind") == "map")
        shown = sum(1 for e in layers if e.get("kind") in ("tile", "map") and not e["hide"])
        waiting = sum(1 for e in layers if "probed" not in e)
        self.stdout.write(f"{trek.catalog_file(body)} — WMTS {tiles} 개·MapServer {maps} 개(목록에 {shown}), "
                          f"둘 다 없음 {len(layers) - tiles - maps - waiting} 개, 아직 안 물음 {waiting} 개")

    def _polar(self, body, layers, today, delay, reprobe):
        """극지 짝을 찾아 `polar` 칸에 적는다. 짝이 없는 판에는 칸을 두지 않는다."""
        try:
            twins = trek.polar_twins(body, delay)
            time.sleep(delay)
        except trek.TrekError as exc:
            self.stderr.write(f"극지 짝의 서비스 목록을 받지 못했다: {exc}")
            return
        for entry in layers:
            if entry["id"] not in twins:
                entry.pop("polar", None)
        todo = [e for e in layers if e["id"] in twins and (reprobe or "polar" not in e)]
        self.stdout.write(f"극지 짝이 있는 판 {sum(1 for e in layers if e['id'] in twins)} 개 — 물을 것 {len(todo)} 개")
        fails = 0
        for entry in todo:
            try:
                entry["polar"] = trek.probe_polar(body, twins[entry["id"]], delay)
            except trek.TrekError as exc:
                fails += 1
                self.stderr.write(f"  {entry['id']} (극): {exc}")
                if fails >= MAX_FAILS:
                    self.stderr.write(f"실패가 {fails} 번 잇따랐다 — 멈춘다. 다시 부르면 이어서 묻는다")
                    break
            else:
                fails = 0
            time.sleep(delay)
        self._write(body, layers, today)
        found = sum(len(e.get("polar") or {}) for e in layers)
        self.stdout.write(f"  극지 판 {found} 개")

    def _write(self, body, layers, today):
        def order(e):
            return trek.category(e["cat"])[2], e["coverage"] != "Global", e["title"].lower()
        # 판 하나가 한 줄이다 — 다시 받았을 때 git 의 차이가 판 단위로 읽힌다
        head = json.dumps({"source": f"NASA {trek.BODIES[body][0]} Trek index (searchItems) + WMTSCapabilities, "
                                     "ArcGIS MapServer", "fetched": today}, ensure_ascii=False)
        rows = ",\n".join(json.dumps(e, ensure_ascii=False, separators=(",", ":"))
                          for e in sorted(layers, key=order))
        trek.catalog_file(body).write_text(f'{head[:-1]}, "layers": [\n{rows}\n]}}\n', encoding="utf-8")
