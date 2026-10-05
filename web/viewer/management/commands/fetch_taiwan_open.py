"""대만 지질운의 열린자료를 한 번 받아 `TAIWAN_OPEN_DIR` 에 둔다 (wetherilli 305).

    manage.py fetch_taiwan_open                    # 갈래 일곱 모두 (몇 분)
    manage.py fetch_taiwan_open --api RockFall     # 하나만
    manage.py fetch_taiwan_open --sensitive        # 지질 민감구역 면만 (290 번 남짓, 13 분쯤, 83 MB, wetherilli 336)
    manage.py fetch_taiwan_open --holes            # 받아 둔 파일의 구멍(holes)만 더 잘게 나눠 다시 받아 보탠다 (wetherilli 328)

탄층·토석류(퇴적·선상·유동구)·낙석·GPS 상시 관측소·암체 강도 등급 — 지질운에 WMS 그림이 없는 것이다. 문(`gsmma.fetch_open`)이 섬 전체
네모로 묻고, 상류가 끊으면 넷으로 나눠 다시 묻는다. 네 번 나눠도 끊기는 네모는 건너뛰고 파일의 `holes` 에 적는다. 묻는 사이 2 초. 화면이 부를 때는 상류를 타지 않는다(`twopen.py`).
사람이 부르는 명령이다 — cron 에 두지 않는다. 자료가 바뀌면(드물다) 다시 부른다.
"""
import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import gsmma, twopen

#: 구멍만 다시 받을 때 더 나누는 횟수 — 0.08° 를 세 번 나누면 0.01°(1 km 남짓)다
HOLE_SPLITS = 3


class Command(BaseCommand):
    help = "대만 지질운의 열린자료(WMS 가 없는 것)를 받아 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--api", default="", help="이 갈래만 (쉼표로 여럿)")
        parser.add_argument("--gap", type=float, default=2.0, help="상류에 묻는 사이 초 (기본 2)")
        parser.add_argument("--sensitive", action="store_true", help="지질 민감구역 면만 받아 sensitive.sqlite 에 (누르기용)")
        parser.add_argument("--holes", action="store_true", help="받아 둔 파일의 구멍만 다시 받아 보탠다")
        parser.add_argument("--splits", type=int, default=HOLE_SPLITS, help=f"구멍을 몇 번 더 넷으로 나누나 (기본 {HOLE_SPLITS})")

    def handle(self, *args, **o):
        if o["sensitive"]:
            return self.sensitive(o["gap"])
        apis = [a.strip() for a in o["api"].split(",") if a.strip()] or list(gsmma.OPEN_APIS)
        unknown = [a for a in apis if a not in gsmma.OPEN_APIS]
        if unknown:
            raise CommandError(f"모르는 갈래: {', '.join(unknown)} — {', '.join(gsmma.OPEN_APIS)}")
        folder = Path(settings.TAIWAN_OPEN_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        if o["holes"]:
            self._holes(folder, apis, o)
            twopen.forget()
            return
        for api in apis:
            started = time.time()
            holes = []
            try:
                features = gsmma.fetch_open(api, gap=o["gap"], log=self.stdout.write, holes=holes)
            except gsmma.GsmmaError as exc:
                raise CommandError(str(exc)) from exc
            tmp = folder / f"{api}.geojson.part"
            tmp.write_text(json.dumps({"type": "FeatureCollection", "fetched": time.strftime("%Y-%m-%d"),
                                       **({"holes": holes} if holes else {}), "features": features},
                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            tmp.replace(folder / f"{api}.geojson")
            self.stdout.write(self.style.SUCCESS(f"{api} — {len(features):,} 개 ({time.time() - started:.0f} 초)"))
            if holes:
                self.stdout.write(self.style.WARNING(f"  받지 못한 네모 {len(holes)} — 파일의 holes 에 적었다: {holes}"))
        twopen.forget()

    def sensitive(self, gap):
        """민감구역 — 끊기면 쉬었다 다시 묻고, 그래도 못 받은 묻기는 건너뛰어 적는다. 다시 부르면 `.part` 에서 잇는다 (wetherilli 346)"""
        folder = Path(settings.TAIWAN_OPEN_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / twopen.SENSITIVE_FILE
        started = time.time()
        db, done, missing = twopen.open_sensitive(path)
        if done:
            self.stdout.write(f"이어 받는다 — 받은 묻기 {len(done)}, 앞서 못 받은 것 {len(missing)}")
        # 이번에 다시 물을 것이니 앞서 못 받은 목록은 비우고 이번 것만 적는다
        missing = []
        try:
            for key, areas in gsmma.fetch_sensitive(gap=gap, log=self.stdout.write, done=done, missing=missing):
                twopen.add_sensitive(db, key, areas)
        except gsmma.GsmmaError as exc:
            db.close()
            raise CommandError(f"{exc} — 받은 것은 {path.with_suffix('.part')} 에 남았다. 다시 부르면 잇는다") from exc
        except KeyboardInterrupt:
            db.close()
            raise
        n = twopen.close_sensitive(db, path, missing)
        self.stdout.write(self.style.SUCCESS(f"민감구역 — 면 조각 {n:,} 개 ({time.time() - started:.0f} 초)"))
        if missing:
            self.stdout.write(self.style.WARNING(f"  못 받은 묻기 {len(missing)} — 파일에 적었다. 다시 부르면 그것만 묻는다:"))
            for key, reason in missing:
                self.stdout.write(f"    {key} — {reason}")

    def _holes(self, folder: Path, apis: list, o: dict):
        """구멍(0.08° 네모)마다 `splits` 번 더 나눠 묻는다. 새로 받은 것만 보태고, 남은 작은 구멍을 다시 적는다.
        구멍에는 상류를 멈추게 하는 자료가 든 듯하다 — 1 km 네모로도 끊기는 자리가 남는다(wetherilli 328)"""
        for api in apis:
            path = folder / f"{api}.geojson"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            old = data.get("holes") or []
            if not old:
                continue
            seen = {json.dumps(f, sort_keys=True, ensure_ascii=False) for f in data.get("features") or []}
            added, left = 0, []
            for box in old:
                try:
                    got = gsmma.fetch_open(api, tuple(box), gap=o["gap"], log=self.stdout.write, holes=left, splits=o["splits"])
                except gsmma.GsmmaError as exc:
                    raise CommandError(str(exc)) from exc
                for f in got:
                    key = json.dumps(f, sort_keys=True, ensure_ascii=False)
                    if key not in seen:
                        seen.add(key)
                        data["features"].append(f)
                        added += 1
            data["holes"] = left
            if not left:
                data.pop("holes")
            data["holes_refetched"] = time.strftime("%Y-%m-%d")
            tmp = folder / f"{api}.geojson.part"
            tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            tmp.replace(path)
            self.stdout.write(self.style.SUCCESS(f"{api} — 구멍 {len(old)} 에서 {added:,} 개를 보탰다, 남은 구멍 {len(left)}"))
