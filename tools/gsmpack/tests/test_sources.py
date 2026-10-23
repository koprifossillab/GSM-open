"""혼자 굽는 쪽의 소스와 명령 (wetherilli 407) — GSM 경유는 가짜 GSM(로컬 HTTP)으로, 곧장은 `net.get` 을 갈아 끼워 본다. 밖을 부르지 않는다."""
import contextlib
import io
import json
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from PIL import Image

from gsmpack import bake, cli, format, grid, net
from gsmpack.sources import direct, via_gsm

from .helpers import png

BOX = {"tiny": {"title": "작은 박스", "region": "korea", "bbox": [129.0, 37.0, 129.05, 37.05],
                "layers": {"L_50K_Geology_Map": [10, 12], "vworld:Base": [10, 11]}, "units": ["L_50K_Geology_Map"]}}
SPECS = {
    "L_50K_Geology_Map": {"title": "5만 지질도", "attribution": "KIGAM", "kind": "kigam", "tile_size": 512, "zoom_offset": -1,
                          "type": "image/png", "url": "wms/?layers=L_50K_Geology_Map&bbox={bbox}"},
    "vworld:Base": {"title": "VWorld Base", "attribution": "VWorld", "kind": "vworld:Base", "tile_size": 256, "zoom_offset": 0,
                    "type": "image/png", "url": "vworld/Base/{z}/{y}/{x}.png"},
}
UNITS = {"type": "FeatureCollection", "types": ["geoOpen:l_50k_geology_litho_latest"], "features": [
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[129, 37], [129.01, 37], [129.01, 37.01], [129, 37]]]},
     "properties": {"props": {"지층": "화절층"}, "props_en": {"Unit": "Hwajeol"}}}]}


class FakeGsm(BaseHTTPRequestHandler):
    """`offline/plan/`·`offline/units/`·`wms/`·`vworld/` 만 아는 GSM. `hit` 이면 캐시에서 낸 척, `notice` 면 안내 타일."""
    seen, hit, notice, status = [], False, False, 200

    def log_message(self, *args):
        pass

    def send(self, status, body, ctype, **head):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in head.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        FakeGsm.seen.append(self.path)
        if url.path == "/GSM/offline/plan/":
            spec = SPECS.get(q.get("layer"))
            return self.send(200 if spec else 404, json.dumps(spec or {"error": "없다"}).encode(), "application/json")
        if url.path == "/GSM/offline/units/":
            return self.send(200, json.dumps(UNITS).encode(), "application/json")
        head = {"X-GSM-Cache": "hit" if FakeGsm.hit else "miss"}
        if FakeGsm.notice:
            head["X-GSM-Notice"] = "1"
        size = 512 if url.path == "/GSM/wms/" else 256
        return self.send(FakeGsm.status, png(size=size), "image/png", **head)


class Base(unittest.TestCase):
    def setUp(self):
        FakeGsm.seen, FakeGsm.hit, FakeGsm.notice, FakeGsm.status = [], False, False, 200
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGsm)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.gsm = f"http://127.0.0.1:{self.server.server_port}/GSM"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.boxes = self.root / "boxes.json"
        self.boxes.write_text(json.dumps(BOX), encoding="utf-8")
        self.sleeps = []
        patch = mock.patch("time.sleep", self.sleeps.append)        # 굽는 고리도 곧장 소스의 지층 면도 같은 time 을 쓴다
        patch.start()
        self.addCleanup(patch.stop)

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["bake", str(self.boxes), "tiny", "--out", str(self.root / "out"), *args])
        return out.getvalue()


class ViaGsm(Base):
    def test_굽고_다시_읽기(self):
        out = self.run_cli("--via", self.gsm)
        pack = next((self.root / "out").glob("tiny-*.gsmpack"))
        header, _ = format.read_header(pack)
        self.assertEqual(header["layers"]["L_50K_Geology_Map"]["zooms"], [9, 11])          # 512 px 는 화면 줌 − 1
        self.assertEqual(header["layers"]["vworld:Base"]["zooms"], [10, 11])
        self.assertEqual(header["units"]["L_50K_Geology_Map"]["types"], UNITS["types"])
        self.assertIn("gsmpack", header)
        self.assertIn("타일", out)
        self.assertFalse(list((self.root / "out").glob(".*.parts.sqlite")))               # 다 구우면 지운다
        wms = [p for p in FakeGsm.seen if p.startswith("/GSM/wms/")]
        z, x, y = 11, *grid.tiles_for(BOX["tiny"]["bbox"], 11)[0]
        self.assertIn(grid.bbox_text(grid.cell_extent(z, x, y)), [urllib.parse.unquote(p).split("bbox=")[1] for p in wms])
        self.assertTrue(self.sleeps)                                                       # 상류를 탄 것은 쉰다

    def test_캐시에서_나온_것은_쉬지_않는다(self):
        FakeGsm.hit = True
        self.run_cli("--via", self.gsm)
        self.assertEqual([s for s in self.sleeps if s > 0], [])

    def test_안내_타일은_실패다(self):
        FakeGsm.notice = True
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("--via", self.gsm)
        self.assertIn("연달아 3 번", str(caught.exception))
        self.assertFalse(list((self.root / "out").glob("tiny-*.gsmpack")))

    def test_쉬는_중이면_곧장_멈춘다(self):
        FakeGsm.status = 503
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("--via", self.gsm)
        self.assertIn("차단 조짐", str(caught.exception))
        self.assertEqual(len([p for p in FakeGsm.seen if p.startswith(("/GSM/wms/", "/GSM/vworld/"))]), 1)

    def test_굽지_못하는_레이어는_건너뛴다(self):
        BOX2 = {"tiny": dict(BOX["tiny"], layers={"L_50K_Geology_Map": [10, 10], "L_없다": [10, 10]})}
        self.boxes.write_text(json.dumps(BOX2), encoding="utf-8")
        self.run_cli("--via", self.gsm, "--dry-run")
        self.assertFalse((self.root / "out").exists())                                     # 어림만 — 아무것도 만들지 않는다


def block_png(nx, ny):
    image = Image.new("RGBA", (512 * nx, 512 * ny), (0, 0, 0, 0))
    for dx in range(nx):
        for dy in range(ny):
            image.paste((10 * dx, 10 * dy, 99, 255), (512 * dx, 512 * dy, 512 * dx + 512, 512 * dy + 512))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class Direct(Base):
    def setUp(self):
        super().setUp()
        self.urls = []

        def fake_get(url, where="", secrets=()):
            self.urls.append(url)
            if url.startswith(direct.WMS_URL):
                q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
                return 200, {"content-type": "image/png"}, block_png(int(q["width"]) // 512, int(q["height"]) // 512)
            if url.startswith("https://api.vworld.kr/"):
                if "/10/" in url:
                    return 200, {"content-type": "text/xml"}, b"<xml/>"                    # 자료 밖
                return 200, {"content-type": "image/png"}, png(size=256)
            if "DescribeLayer" in url:
                return 200, {}, json.dumps({"layerDescriptions": [
                    {"owsType": "WFS", "typeName": "geoOpen:l_50k_geology_litho_latest"},
                    {"owsType": "WFS", "typeName": "geoOpen:l_50k_geology_fault_latest"}]}).encode()
            if "GetFeature" in url:
                return 200, {}, json.dumps({"features": [
                    {"geometry": UNITS["features"][0]["geometry"],
                     "properties": {"지층": "화절층", "도폭": '장성<a href="https://doi.org/x">수치</a>', "빈": None}}]}).encode()
            raise AssertionError(url)

        patch = mock.patch.object(net, "get", fake_get)
        patch.start()
        self.addCleanup(patch.stop)

    def test_키는_묶음에_없다(self):
        with mock.patch.dict("os.environ", {"GSM_KIGAM_KEY": "SECRET-KG", "GSM_VWORLD_KEY": "SECRET-VW"}):
            self.run_cli("--direct")
        pack = next((self.root / "out").glob("tiny-*.gsmpack"))
        raw = pack.read_bytes()
        self.assertNotIn(b"SECRET", raw)
        header, _ = format.read_header(pack)
        self.assertNotIn("vworld:Base/10/", " ".join(header["tiles"]))                     # 자료 밖은 넣지 않는다
        self.assertEqual(json.loads(format.read_tile(pack, "@units/L_50K_Geology_Map"))["features"][0]["properties"]["props"]["도폭"]["links"][0]["url"],
                         "https://doi.org/x")
        # 큰 그림 한 장으로 열여섯 칸 — 줌마다 KIGAM 에 묻는 것은 박스를 덮는 블록 수뿐
        kigam = [u for u in self.urls if u.startswith(direct.WMS_URL)]
        blocks = {(z, x // 4, y // 4) for z in (9, 10, 11) for x, y in grid.tiles_for(BOX["tiny"]["bbox"], z)}
        self.assertEqual(len(kigam), len(blocks))
        self.assertTrue(all("key=SECRET-KG" in u for u in kigam))
        self.assertFalse(any("SECRET" in u for u in self.urls if "geoserver" in u))         # 묻지 않는 곳에는 붙이지 않는다

    def test_자른_칸이_제자리다(self):
        parts = bake.Parts(self.root / "p.sqlite")
        src = direct.KigamDirect("L_50K_Geology_Map", "K", parts)
        src.fetch(11, 4 * 100 + 2, 4 * 50 + 3)
        color = Image.open(io.BytesIO(src.cached(11, 4 * 100 + 1, 4 * 50 + 3))).getpixel((5, 5))
        self.assertEqual(color[:2], (10, 30))

    def test_키가_없으면_굽지_않는다(self):
        with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(SystemExit) as caught:
            self.run_cli("--direct")
        self.assertIn("KIGAM 인증키가 없다", str(caught.exception))
        self.assertEqual(self.urls, [])

    def test_키_파일(self):
        key = self.root / "k"
        key.write_text("FROM-FILE\n", encoding="utf-8")
        with mock.patch.dict("os.environ", {"GSM_KIGAM_KEY_FILE": str(key)}, clear=True):
            self.assertEqual(direct.key_from_env("GSM_KIGAM_KEY"), "FROM-FILE")

    def test_엮은_레이어는_곧장_굽지_못한다(self):
        with self.assertRaises(ValueError):
            direct.KigamDirect("L_50K_Geology_Map_NoAttitude", "K", bake.NoParts())


class Redact(unittest.TestCase):
    def test_키를_지운다(self):
        self.assertEqual(net.redact("https://x/wms?a=1&key=ABC&b=2"), "https://x/wms?a=1&key=…&b=2")
        self.assertEqual(net.redact("https://api.vworld.kr/req/wmts/1.0.0/VWKEY/Base/1/2/3.png", "VWKEY"),
                         "https://api.vworld.kr/req/wmts/1.0.0/…/Base/1/2/3.png")


if __name__ == "__main__":
    unittest.main()
