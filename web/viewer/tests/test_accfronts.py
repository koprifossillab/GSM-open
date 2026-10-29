"""남극순환류 전선 (wetherilli 429). 저장소의 파일만 읽는다 — 상류를 부르지 않는다."""
import json
import math
import struct
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import accfronts, doors


def netcdf(fronts: dict) -> bytes:
    """전선마다 (위도, 경도) 배열 둘을 든 NetCDF-3 고전판(CDF1) — 원본의 꼴(double, 차원 하나씩)"""
    def name(text):
        b = text.encode()
        return struct.pack(">i", len(b)) + b + b"\0" * (-len(b) % 4)
    codes = list(fronts)
    dims = b"".join(name(f"ACC_FRONT_{c}") + struct.pack(">i", len(fronts[c][0])) for c in codes)
    variables = [(f"{axis}{c}", i, fronts[c][k]) for i, c in enumerate(codes) for k, axis in ((0, "Lat"), (1, "Lon"))]

    def header(begin0):
        out = b"CDF\x01" + struct.pack(">i", 0) + struct.pack(">ii", 0x0A, len(codes)) + dims + struct.pack(">ii", 0, 0)
        out += struct.pack(">ii", 0x0B, len(variables))
        at = begin0
        for vname, dim, values in variables:
            out += name(vname) + struct.pack(">ii", 1, dim) + struct.pack(">ii", 0, 0) + struct.pack(">iii", 6, 8 * len(values), at)
            at += 8 * len(values)
        return out
    head = header(0)
    head = header(len(head))
    return head + b"".join(struct.pack(f">{len(v)}d", *v) for _, _, v in variables)


def ring(lat0):
    lons = [0.0625 + 0.125 * k for k in range(2880)]              # 0 → 180, −180 → 0 (원본처럼)
    lons = [l if l <= 180 else l - 360 for l in lons] + [math.nan]
    return [lat0 + math.sin(math.radians(l)) for l in lons[:-1]] + [math.nan], lons


class Bake(SimpleTestCase):
    def test_날짜변경선을_건너도_잇는다(self):
        doc = accfronts.convert(netcdf({c: ring(-40 - 4 * i) for i, (c, _, _) in enumerate(accfronts.FRONTS)}))
        nb = doc["fronts"]["NB"]
        self.assertEqual(len(nb), 2880 // accfronts.STEP + 1)
        steps = [b[0] - a[0] for a, b in zip(nb, nb[1:])]
        self.assertTrue(all(0 < s < 1 for s in steps))              # 경도가 한 방향으로만 간다 — 끊기지 않는다
        self.assertAlmostEqual(nb[-1][0] - nb[0][0], 360, places=3)    # 닫힌 고리
        self.assertEqual(nb[-1][1], nb[0][1])

    def test_전선이_빠지면_멈춘다(self):
        with self.assertRaises(accfronts.AccFrontsError):
            accfronts.convert(netcdf({"NB": ring(-40)}))


class Serve(TestCase):
    def test_저장소의_파일(self):
        doc = json.loads(accfronts.path().read_text(encoding="utf-8"))
        self.assertEqual(set(doc["fronts"]), {c for c, _, _ in accfronts.FRONTS})
        self.assertLess(accfronts.path().stat().st_size, 200_000)

    def test_남극_탭의_선(self):
        body = json.loads(self.client.get("/GSM/points/?layer=acc:fronts").content)
        self.assertEqual([f["properties"]["code"] for f in body["features"]], ["NB", "SAF", "PF", "SACCF", "SB"])
        self.assertEqual(body["features"][2]["properties"]["front"], "극 전선 (PF)")
        self.assertEqual(len(body["legend"]), 5)

    def test_파일이_없으면_503(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(ACC_FRONTS_FILE=Path(tmp) / "none.json"):
            self.assertEqual(self.client.get("/GSM/points/?layer=acc:fronts").status_code, 503)
            self.assertEqual(self.client.get("/GSM/earth/accfronts/tiles/0/0/0.png").status_code, 200)    # 빈 칸

    def test_경위도_타일(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TILE_CACHE_DIR=tmp):
            got = self.client.get("/GSM/earth/accfronts/tiles/1/1/1.png")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content[:4], b"\x89PNG")
        self.assertEqual(self.client.get("/GSM/earth/accfronts/tiles/8/0/0.png").status_code, 404)

    def test_문이_아니다(self):
        self.assertTrue(doors.specs()["acc"].local)
