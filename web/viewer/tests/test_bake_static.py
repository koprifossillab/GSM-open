"""정적 판 굽기 — `manage.py bake_static` (wetherilli 160).

GeoMAP gpkg·상류는 부르지 않는다. 잘라 둔 타일 폴더와 점 레이어의 받는 길만 가짜로 세운다.
"""
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from viewer import grportal, npolar
from viewer.management.commands import bake_static


def tiles(root: Path, folder: str, names):
    for name in names:
        f = root / folder / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 10)


class Bake(SimpleTestCase):
    def setUp(self):
        self.src = Path(tempfile.mkdtemp(prefix="gsm-bake-src-"))
        self.out = Path(tempfile.mkdtemp(prefix="gsm-bake-out-"))
        tiles(self.src / "ibcso", "tiles-bed", ["0/0/0.webp", "1/0/1.webp"])
        tiles(self.src / "ibcso", "tiles-ice", ["0/0/0.webp"])
        tiles(self.src / "ibcso", "tiles-tid", ["0/0/0.png"])
        tiles(self.src / "peninsula", "tiles", ["3/1/2.webp"])
        patch = override_settings(IBCSO_DIR=str(self.src / "ibcso"), PENINSULA_DIR=str(self.src / "peninsula"),
                                  NPOLAR_DIR=str(self.src / "npolar"), KOPRI_DIR=str(self.src / "kopri"))
        patch.enable()
        self.addCleanup(patch.disable)

    def run_bake(self, *args):
        out, err = io.StringIO(), io.StringIO()
        call_command("bake_static", str(self.out), *args, stdout=out, stderr=err)
        return json.loads((self.out / "manifest.json").read_text(encoding="utf-8")), err.getvalue()

    def test_IBCSO_는_화면이_부르는_주소_꼴로_옮긴다(self):
        manifest, _ = self.run_bake("--only", "ibcso")
        paths = {f[0] for f in manifest["files"]}
        self.assertEqual(paths, {"ibcso/bed/0/0/0.webp", "ibcso/bed/1/0/1.webp", "ibcso/ice/0/0/0.webp",
                                 "ibcso/tid/0/0/0.png"})
        self.assertEqual(manifest["parts"]["ibcso"]["bed"]["files"], 2)
        self.assertEqual(manifest["total_bytes"], 40)
        self.assertEqual(manifest["dirs"]["ibcso/bed"], 20)

    def test_한반도_음영판은_더할_때만(self):
        manifest, _ = self.run_bake("--only", "ibcso")
        self.assertNotIn("peninsula", manifest["parts"])
        manifest, _ = self.run_bake("--only", "ibcso", "--with", "peninsula")
        self.assertIn("peninsula/shaded/3/1/2.webp", {f[0] for f in manifest["files"]})

    def test_점_레이어는_상류_폴더에_이름으로(self):
        one = {"grportal:geochron": grportal.LAYERS["grportal:geochron"]}
        with mock.patch.dict(grportal.LAYERS, one, clear=True), mock.patch.dict(npolar.POINTS, {}, clear=True), \
             mock.patch("viewer.views.point_features", return_value=b"[]") as fetched, \
             mock.patch("viewer.janmayen.available", return_value=False):
            manifest, err = self.run_bake("--only", "points")
        fetched.assert_called_once_with("grportal:geochron")
        body = json.loads((self.out / "points/grportal/geochron.json").read_text(encoding="utf-8"))
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertIn("janmayen:units 자료가 없어", err)

    def test_모르는_몫(self):
        with self.assertRaises(CommandError):
            call_command("bake_static", str(self.out), "--only", "kigam", stdout=io.StringIO())

    def test_줌을_바꾸는_꼴(self):
        with self.assertRaises(CommandError):
            call_command("bake_static", str(self.out), "--geomap-zoom", "geomap_faults:5", stdout=io.StringIO())

    def test_점_경로(self):
        self.assertEqual(bake_static.Command._point_path("npolar:place_names"), "points/npolar/place_names.json")
        self.assertEqual(bake_static.Command._point_path("kopri:rock_antarctica", "en"),
                         "points/kopri/rock_antarctica.en.json")


class PolarFiles(SimpleTestCase):
    """받아 둔 파일에서 짓는 극지 덩이 (wetherilli 430) — 파일이 없으면 그 레이어만 빠지고 굽기는 돈다"""

    def bake(self, **ready):
        cmd = bake_static.Command(stdout=io.StringIO(), stderr=io.StringIO())
        cmd.out, cmd.files = Path(tempfile.mkdtemp(prefix="gsm-bake-polar-")), []
        with mock.patch("viewer.orda.available", return_value=ready.get("orda", False)), \
             mock.patch("viewer.orda.body", side_effect=lambda n, lang: f'{{"n":"{n}","lang":"{lang}"}}'.encode()), \
             mock.patch("viewer.gtnp.available", return_value=ready.get("gtnp", False)), \
             mock.patch("viewer.gtnp.body", return_value=b'{"same":1}'), \
             mock.patch("viewer.kgis.available", return_value=False), \
             mock.patch("viewer.aadc.available", return_value=ready.get("aadc", False)), \
             mock.patch("viewer.aadc.body", side_effect=ValueError("깨진 파일")):
            report = cmd.bake_polar_files()
        return cmd, report

    def test_있는_것만_굽는다(self):
        cmd, report = self.bake(gtnp=True)
        self.assertIn("gtnp:boreholes_arctic", report)
        self.assertIn("acc:fronts", report)                        # 저장소의 파일 — 늘 있다
        self.assertNotIn("orda:lakes_antarctica", report)
        self.assertIn("orda:lakes_antarctica 자료가 없어 건너뛴다", cmd.stderr.getvalue())

    def test_말마다_다르면_두_벌(self):
        cmd, report = self.bake(orda=True, gtnp=True)
        self.assertTrue(report["orda:lakes_antarctica"]["lang"])
        self.assertTrue((cmd.out / "points/orda/lakes_antarctica.en.json").is_file())
        self.assertNotIn("lang", report["gtnp:boreholes_arctic"])
        self.assertFalse((cmd.out / "points/gtnp/boreholes_arctic.en.json").exists())

    def test_깨진_파일은_그_레이어만_뺀다(self):
        cmd, report = self.bake(aadc=True)
        self.assertNotIn("aadc:aspa", report)
        self.assertIn("acc:fronts", report)

    def test_RAISED_는_싣지_않는다(self):
        """사본에 조건 칸이 없어 사람이 연구소 판에만 두기로 정했다 (wetherilli 420)"""
        self.assertFalse(any(name.startswith("raised:") for name, _, _ in bake_static.Command.POLAR_FILES))
