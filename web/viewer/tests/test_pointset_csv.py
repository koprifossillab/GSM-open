"""점묶음 CSV 내려받기 (wetherilli 190) — 올린 속성에 우리 파일에서 읽는 값을 열로 붙인다.

화석 산지는 `fossils.build` 로 임시 폴더에 굽고, 지각 두께는 저장소의 `data/crust2_thickness.json` 을 읽는다.
GeoMAP·달 원도는 파일이 커서 저장소에 없으니 읽는 함수를 바꿔 끼운다.
"""
import csv
import io
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import fossils, pointvalues, views
from viewer.models import Point, PointSet
from viewer.tests.test_fossils import HEAD

FOSSILS = [
    '1,126.98,37.57,서울 산지,"Pyeongan Sup.",Changhsingian,Induan,254.1,249.9,KR,12,105.0,30.6,"marginal marine",Kim 2001\n',
    "3,-60.0,-75.0,남극 산지,,Maastrichtian,,72.1,66.0,AQ,3,,,marine,\n",
]


def gathered(folder):
    folder = Path(folder)
    (folder / "c.csv").write_text(HEAD + "".join(FOSSILS), encoding="utf-8")
    fossils.build(folder / "c.csv", folder / fossils.FILE, log=lambda *_: None)


def table(response) -> list:
    text = response.content.decode("utf-8")
    assert text.startswith("﻿"), "엑셀이 한글을 알아보게 BOM 이 붙는다"
    return list(csv.reader(io.StringIO(text[1:])))


@override_settings(IBCSO_DIR="/nonexistent")
class EarthCsv(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-csv-")
        patch = override_settings(EARTH_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        gathered(self.dir)
        self.ps = PointSet.objects.create(name="시료 / 2026", body="earth")
        Point.objects.create(pointset=self.ps, lat=37.6, lon=127.0, label="S1", props={"암상": "화강암", "번호": 7})
        Point.objects.create(pointset=self.ps, lat=-75.0, lon=-60.0, label="A1", props={"암상": "편마암"})
        geomap_hit = [{"properties": {"지질 단위": "Basement", "지질기호": "Pz", "연대 (Ma)": "541 – 251"}}]
        for target, value in (("viewer.geomap.available", True), ("viewer.geomap.query", geomap_hit)):
            p = mock.patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def get(self, **params):
        return self.client.get(reverse("viewer:pointset-csv", args=[self.ps.id]), params)

    def test_올린_속성과_우리_파일의_값(self):
        r = self.get()
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("filename*=UTF-8''%EC%8B%9C%EB%A3%8C%20_%202026.csv", r["Content-Disposition"])
        head, seoul, south = table(r)
        self.assertEqual(head[:5], ["이름표", "위도", "경도", "암상", "번호"])
        self.assertEqual(head[5:], list(pointvalues.columns("earth", ["geomap", "crust", "fossil"])))
        row = dict(zip(head, seoul))
        self.assertEqual((row["이름표"], row["암상"], row["번호"]), ("S1", "화강암", "7"))
        self.assertGreater(float(row["지각 두께 km(CRUST 2.0)"]), 20)
        self.assertEqual(row["가까운 화석 산지(PBDB)"], "서울 산지")
        self.assertAlmostEqual(float(row["산지까지 km(PBDB)"]), 3.6, delta=0.5)
        self.assertEqual(row["지질 단위(GeoMAP)"], "")                       # 남극 밖이다
        row = dict(zip(head, south))
        self.assertEqual((row["지질 단위(GeoMAP)"], row["지질기호(GeoMAP)"]), ("Basement", "Pz"))
        self.assertEqual(row["가까운 화석 산지(PBDB)"], "남극 산지")

    def test_붙이지_않거나_골라_붙인다(self):
        head = table(self.get(extras="none"))[0]
        self.assertEqual(head, ["이름표", "위도", "경도", "암상", "번호"])
        head = table(self.get(extras="crust"))[0]
        self.assertEqual(head[5:], ["지각 두께 km(CRUST 2.0)"])

    def test_점이_많으면_값을_읽지_않는다(self):
        with mock.patch.object(pointvalues, "LIMIT", 1):
            r = self.get()
            self.assertEqual(r.status_code, 413)
            self.assertIn("extras=none", r.json()["error"])
            self.assertEqual(self.get(extras="none").status_code, 200)

    def test_영어판은_열_이름을_옮긴다(self):
        self.client.cookies["gsm_lang"] = "en"
        head = table(self.get(extras="crust"))[0]
        self.assertEqual(head, ["Label", "Latitude", "Longitude", "암상", "번호", "Crustal thickness km (CRUST 2.0)"])

    def test_화석_산지_파일이_없으면_그_열을_뺀다(self):
        with override_settings(EARTH_DIR=tempfile.mkdtemp()):
            head = table(self.get())[0]
        self.assertNotIn("가까운 화석 산지(PBDB)", head)
        self.assertIn("지각 두께 km(CRUST 2.0)", head)


class MoonCsv(TestCase):
    def test_달_점에는_원도_단위(self):
        ps = PointSet.objects.create(name="착륙지", body="moon")
        Point.objects.create(pointset=ps, lat=0.67, lon=23.47, label="Apollo 11")
        hit = {"unit": "Im2", "name": "Imbrian mare", "epoch": "Imbrian", "citation": "I-703 · Wilhelms (1971)"}
        with mock.patch("viewer.moonmap.available", return_value=True), \
                mock.patch("viewer.moonmap.identify", return_value=hit):
            head, row = table(self.client.get(reverse("viewer:pointset-csv", args=[ps.id])))
        row = dict(zip(head, row))
        self.assertEqual((row["지질 단위(원도)"], row["원도"]), ("Im2", "I-703 · Wilhelms (1971)"))
        self.assertNotIn("지각 두께 km(CRUST 2.0)", head)                     # 지구의 값은 붙지 않는다


class Screens(TestCase):
    def test_다섯_화면의_단추와_상한이_서버와_같다(self):
        here = Path(views.__file__).parent / "static/viewer"
        for name in ("map.js", "earth.js", "moon.js", "mars.js", "mercury.js"):
            js = (here / name).read_text(encoding="utf-8")
            self.assertIn('"/csv/?extras="', js, name)
            self.assertEqual(set(re.findall(r"ps\.count \|\| 0\) > (\d+)", js)), {str(pointvalues.LIMIT)}, name)
