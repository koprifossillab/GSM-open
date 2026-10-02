"""주룽 로버의 주행 경로를 NaTeCam 2CL 메타데이터에서 뽑아 `data/mars_zhurong.json` 에 적는다 (devlog 066).

원본은 Zhang 외(2026)가 figshare(doi:10.6084/m9.figshare.29946872)에 올린 rar 이다(254 MB, CC BY 4.0).
`Github/Camera/*.2CL` 만 풀어 그 디렉터리를 준다. 사진 1 309 장에서 멈춘 자리 백여 곳이 남는다.
경로는 끝난 임무의 것이라 **한 번 굽고 저장소에 담는다**(수 KB).
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import zhurong

#: HiRISE 로 잡은 착륙 지점 — Liu 외 2022(Nat. Astron.)·Ding 외 2022(Nat. Geosci.). 까닭은 `zhurong` 머리말
LANDING = (109.925, 25.066)


class Command(BaseCommand):
    help = "주룽 NaTeCam 2CL 디렉터리에서 주행 경로를 뽑아 data/mars_zhurong.json 에 적는다"

    def add_arguments(self, parser):
        parser.add_argument("camera_dir", help="rar 의 Github/Camera 를 푼 디렉터리")
        parser.add_argument("--out", default="")

    def handle(self, *args, **o):
        files = sorted(Path(o["camera_dir"]).glob("*.2CL"))
        records = [r for r in (zhurong.read_2cl(f.read_text(encoding="utf-8", errors="replace")) for f in files) if r]
        if len(records) < 1000:
            raise CommandError(f"로버 자리가 적힌 2CL 이 {len(records)} 장뿐이다 — 디렉터리가 맞나")
        stops = zhurong.stops(records)
        out = Path(o["out"] or settings.MARS_ZHURONG_FILE)
        out.write_text(json.dumps({
            "source": "Zhang et al. 2026, Sci. Data, doi:10.1038/s41597-026-07034-4 (figshare "
                      "doi:10.6084/m9.figshare.29946872, CC BY 4.0) — NaTeCam 2CL Rover_Location_xyz; "
                      "sols 8-18 from Ding et al. 2022, Nat. Geosci., doi:10.1038/s41561-022-00905-6, Fig. 2a",
            "landing": list(LANDING),
            "landing_source": "HiRISE-based: Liu et al. 2022 Nat. Astron.; Ding et al. 2022 Nat. Geosci.",
            "frame": "LANDING_SITE_COORDINATE_SYSTEM — x east, y north, z up (m)",
            "columns": ["sol", "x", "y", "z"],
            "stops": stops,
        }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        self.stdout.write(f"사진 {len(records)} 장에서 멈춘 자리 {len(stops)} 곳을 {out} 에 적었다 "
                          f"(솔 {stops[0][0]}–{stops[-1][0]})")
