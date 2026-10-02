"""중국 주룽(祝融) 로버의 착륙 지점과 주행 경로 (devlog 066). **문이 아니다** — 저장소의 파일을 읽는다.

Mars Trek 에는 주룽이 없다(058). 경로는 논문이 CC BY 4.0 으로 내놓은 자료에서 뽑았다.

- 솔 20–325 — Zhang 외(2026, Scientific Data, doi:10.1038/s41597-026-07034-4)가 figshare
  (doi:10.6084/m9.figshare.29946872)에 올린 NaTeCam 2CL 메타데이터 1 309 개. 한 장마다 로버의 자리가
  `LANDING_SITE_COORDINATE_SYSTEM` 의 x(동)·y(북)·z(위) 미터로 적혀 있다. 자리가 바뀐 것만 남긴다
- 솔 8–18 — 그 앞은 사진 메타데이터가 없다. Ding 외(2022, Nature Geoscience, doi:10.1038/s41561-022-00905-6)
  원자료 Fig. 2a 의 로버 자리(같은 좌표계 — 솔 22·23 이 소수 셋째 자리까지 같다)

**경위도는 우리가 붙인다.** 메타데이터에도 경위도(`MARS_COORDINATE_SYSTEM`)가 있지만 임무의 좌표계라
착륙선이 (109.9085°E, 25.0833°N)에 선다 — HiRISE 로 잡은 착륙 지점(109.925°E, 25.066°N, Liu 외 2022·Ding 외
2022)과 1.4 km 어긋난다. 우리 배경(Viking·THEMIS·MOLA)은 MOLA 에 맞춘 것이라 HiRISE 쪽이 맞다. 그래서 미터
좌표를 그 착륙 지점에 붙여 평균 반지름의 구(`trek.MARS_RADIUS`)로 옮긴다. 몇 km 안이라 평면으로 옮겨도 cm 다.

파일은 `manage.py build_zhurong <2CL 디렉터리>` 가 굽는다. 원본(rar)은 NAS 의 `sources/mars/` 에 둔다.
"""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from . import trek

MISSION = "Zhurong"
CREDIT = ("Zhurong traverse: Zhang et al. 2026 (Sci. Data, CC BY 4.0) · Ding et al. 2022 (Nat. Geosci.) · "
          "Tianwen-1 NaTeCam (CNSA/GRAS)")

#: 솔 8–18 의 로버 자리 (x 동, y 북, m) — Ding 외 2022 원자료 Fig. 2a. 솔 20 부터는 사진 메타데이터다
EARLY = ((8, 5.563, 0.085), (11, 2.390, -5.584), (14, 3.195, -8.723), (16, 5.128, -10.920),
         (18, -0.266, -5.123))
#: 자리가 이보다 적게 움직이면 같은 자리다 — 같은 곳에서 찍은 사진 여러 장
SAME_STOP_M = 0.05


def to_lonlat(x: float, y: float, origin: tuple) -> tuple:
    """착륙 지점 기준 (동, 북) 미터 → 경위도. 몇 km 안이라 접평면으로 옮긴다."""
    lon0, lat0 = origin
    k = 180 / (math.pi * trek.MARS_RADIUS)
    return lon0 + x * k / math.cos(math.radians(lat0)), lat0 + y * k


def _num(block: str, tag: str) -> float:
    return float(re.search(rf"<{tag}[^>]*>\s*([^<\s]+)\s*<", block).group(1))


def read_2cl(text: str) -> dict | None:
    """2CL(PDS4 XML) 한 장 → `{"time", "sol", "x", "y", "z"}`. 로버 자리가 없으면 None."""
    xyz = re.search(r"<Rover_Location_xyz>(.*?)</Rover_Location_xyz>", text, re.S)
    time = re.search(r"<start_date_time>([^<]+)<", text)
    sol = re.search(r"<local_true_solar_time>\s*(\d+)", text)
    if not (xyz and time and sol) or "LANDING_SITE_COORDINATE_SYSTEM" not in xyz.group(1):
        return None
    block = xyz.group(1)
    return {"time": time.group(1), "sol": int(sol.group(1)),
            "x": _num(block, "x"), "y": _num(block, "y"), "z": _num(block, "z")}


def stops(records: list) -> list:
    """사진마다의 자리 → 멈춘 자리 `[[솔, x, y, z], …]`. 시각 순서로, 움직인 것만 남긴다."""
    out = [[sol, x, y, None] for sol, x, y in EARLY]
    for r in sorted(records, key=lambda r: r["time"]):
        if out and math.hypot(r["x"] - out[-1][1], r["y"] - out[-1][2]) <= SAME_STOP_M:
            continue
        out.append([r["sol"], round(r["x"], 3), round(r["y"], 3), round(r["z"], 3)])
    return out


@lru_cache(maxsize=1)
def load() -> dict:
    """저장소의 경로 파일. 없거나 깨졌으면 빈 것 — 화면은 주룽만 빠진 채 선다."""
    try:
        data = json.loads(Path(settings.MARS_ZHURONG_FILE).read_text(encoding="utf-8"))
        origin = tuple(data["landing"])
        return {"origin": origin, "stops": data["stops"]}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def landings() -> list:
    """`trek.mars_landings` 와 같은 꼴 — 착륙 지점과 마지막으로 찍힌 자리."""
    data = load()
    if not data:
        return []
    lon, lat = data["origin"]
    sol, x, y, _ = data["stops"][-1]
    end = to_lonlat(x, y, data["origin"])
    return [
        {"name": "Zhurong Landing Site", "mission": MISSION, "kind": "rover", "lon": lon, "lat": lat},
        {"name": f"Zhurong, sol {sol}", "mission": MISSION, "kind": "rover",
         "lon": round(end[0], 6), "lat": round(end[1], 6)},
    ]


def traverse() -> dict | None:
    """`trek.mars_traverses` 의 한 항목 꼴 — 착륙 지점에서 마지막 자리까지 한 줄."""
    data = load()
    if not data:
        return None
    line = [list(data["origin"])]
    for _, x, y, _ in data["stops"]:
        lon, lat = to_lonlat(x, y, data["origin"])
        line.append([round(lon, 6), round(lat, 6)])
    return {"mission": MISSION, "paths": [line]}


def place() -> list:
    """지명 찾기에 넣을 한 줄 — `data/mars_places.json` 의 꼴(`[이름, 갈래, 경도, 위도]`)."""
    data = load()
    return [["Zhurong Landing Site", "Landing site", *data["origin"]]] if data else []
