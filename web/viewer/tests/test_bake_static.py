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
