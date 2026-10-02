"""시료 고도를 알려진 높이와 견준다 (P03 §7, wetherilli 170).

    manage.py check_elevation

`data/ngii_benchmarks.json` 의 국가기준점(통합기준점, 직접수준측량 표고)을 시료 고도를 채우는 길(`elevation.elevations`)
그대로 읽어 차를 적는다. 점 둘레(±60 m 네 자리)의 기복도 함께 적는다 — 30 m 칸의 DEM 은 비탈에서 벗어나는 것이 당연해서,
벗어난 점이 비탈 탓인지 가르려는 것이다. 타일은 캐시에 있으면 상류를 타지 않는다.
"""
import json
import math

from django.conf import settings
from django.core.management.base import BaseCommand

from viewer import elevation

#: P03 §7 의 잣대 — SRTM 의 알려진 오차 수준
TOLERANCE = 15.0
#: 둘레 기복이 이보다 작으면 평지로 센다
FLAT_RELIEF = 10.0
#: 둘레를 읽는 거리(m) — z12 의 두 칸쯤
RING = 60.0


def ring(lat: float, lon: float, metres: float = RING) -> list:
    """한 점의 북·남·동·서 metres 자리."""
    dlat = metres / 111320.0
    dlon = dlat / max(math.cos(math.radians(lat)), 1e-6)
    return [(lat + dlat, lon), (lat - dlat, lon), (lat, lon + dlon), (lat, lon - dlon)]


def summarize(rows: list) -> dict:
    """[(차, 기복), …] → 셈. 평지는 기복이 FLAT_RELIEF 밑인 것."""
    def stats(diffs):
        n = len(diffs)
        if not n:
            return {"n": 0}
        return {"n": n, "within": sum(abs(d) <= TOLERANCE for d in diffs),
                "mean": sum(diffs) / n, "rms": math.sqrt(sum(d * d for d in diffs) / n),
                "worst": max(diffs, key=abs)}
    return {"all": stats([d for d, _ in rows]), "flat": stats([d for d, r in rows if r < FLAT_RELIEF])}


class Command(BaseCommand):
    help = "시료 고도를 국가기준점의 표고와 견준다"

    def handle(self, *args, **options):
        path = settings.REPO_DIR / "data" / "ngii_benchmarks.json"
        points = json.loads(path.read_text(encoding="utf-8"))["points"]
        query = {}
        for p in points:
            query[p["no"]] = (p["lat"], p["lon"])
            for i, ll in enumerate(ring(p["lat"], p["lon"])):
                query[f"{p['no']}#{i}"] = ll
        got = elevation.elevations(query)
        rows = []
        for p in points:
            if p["no"] not in got:
                self.stdout.write(f"{p['no']:8} 읽지 못했다")
                continue
            value, source = got[p["no"]]
            around = [got[f"{p['no']}#{i}"][0] for i in range(4) if f"{p['no']}#{i}" in got] + [value]
            diff, relief = value - p["height"], max(around) - min(around)
            rows.append((diff, relief))
            self.stdout.write(f"{p['no']:8} {p['sheet']:4} 기준 {p['height']:8.2f}  DEM {value:8.2f}  차 {diff:+7.2f}  "
                              f"기복 {relief:5.1f}  {source}")
        for name, label in (("all", "전부"), ("flat", f"평지(기복 {FLAT_RELIEF:g} m 밑)")):
            s = summarize(rows)[name]
            if not s["n"]:
                continue
            self.stdout.write(f"{label}: ±{TOLERANCE:g} m 안 {s['within']}/{s['n']} · 평균 {s['mean']:+.2f} · "
                              f"RMS {s['rms']:.2f} · 가장 큰 차 {s['worst']:+.2f}")
