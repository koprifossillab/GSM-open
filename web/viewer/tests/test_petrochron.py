"""PetroChron Antarctica (wetherilli 419) — 받아 굽기, 남극 탭의 점 레이어. 상류는 부르지 않는다."""
import gzip
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import i18n, petrochron

HEAD = ("reference,sample_name,sampling,basement_terrane,lithostrat_name,geographic_coordinate_information,latitude,longitude,"
        "geolocation,rock_group,rock_type,rock_name,rock_description,age_ma,age_2sd_ma,mineral_isotope,age_significance,"
        "age_type,age_approach,technique_isotopes_analyses,sio2,tio2,al2o3,fe2o3_tot,fe2o3,feo,mgo,cao,na2o,k2o,"
        "mineral_geochemistry,spldata_id")
ROWS = [
    # 전암 화학이 있는 화강암 — 참고문헌의 제목이 .bib 와 맞는다
    '"Adams et al., 1995, Geochronology of Cretaceous granites, Marie Byrd Land",63082,outcrop,,Byrd Coast Granite,'
    "supplied in paper,-78.00014916,-155.0010655,Mount Paterson,igneous,plutonic,Granitic,,,,,,,,,"
    "72.1,0.3,14.2,,,,0.5,1.2,3.5,4.2,whole rock,1",
    # 연대만 있는 변성암
    '"Adachi et al., 2013, Timing of metamorphism in the central Sør Rondane Mountains",07121003D,moraine,SW Terrane,'
    "Unit D,not supplied - defined via SCAR Gazetteer,-72.075,24.1,Walnumfjella,metamorphic,metaplutonic,Gneiss,,"
    "546,4,zircon,Metamorphism (regional),U-Th-Pb (radiogenic),207Pb*/206Pb*,SHRIMP,,,,,,,,,,,,2",
    # 광물 분석 — 주성분은 그 광물의 것이라 분석 대상을 적는다
    '"Nobody, 2001, Unlisted paper",X1,outcrop,,,supplied in paper,-70,10,,igneous,volcanic,Basalt,,,,,,,,,'
    "50.2,,,,,,,,,,biotite,3",
    # 좌표가 없는 줄은 뺀다
    '"Nobody, 2001, Unlisted paper",X2,outcrop,,,,,,,not defined,not defined,,,,,,,,,,,,,,,,,,,,,4',
]
DB = ("﻿" + HEAD + "\n" + "\n".join(ROWS) + "\n").encode("utf-8")
BIB = """@article{Adams1995,
author = {Adams, C J},
doi = {10.1017/S095410209500037X},
title = {{Geochronology of Cretaceous granites, Marie Byrd Land}},
year = {1995}
}
@article{Adachi2013,
doi = {https://doi.org/10.1016/j.precamres.2012.11.011},
title = {Timing of metamorphism in the central S{\\o}r Rondane Mountains},
}
""".encode("utf-8")


class Build(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.features = {f["id"]: f["properties"] for f in petrochron.build(DB, BIB)["features"]}

    def test_좌표가_없는_줄은_뺀다(self):
        self.assertEqual(sorted(self.features), ["1", "2", "3"])

    def test_암석_갈래(self):
        self.assertEqual([self.features[k]["code"] for k in ("1", "2", "3")], ["plutonic", "metamorphic", "volcanic"])

    def test_주성분과_분석_대상(self):
        self.assertEqual(self.features["1"]["major"], "SiO₂ 72.1 · TiO₂ 0.3 · Al₂O₃ 14.2 · MgO 0.5 · CaO 1.2 · Na₂O 3.5 · K₂O 4.2")
        self.assertNotIn("target", self.features["1"])                # 전암이면 적지 않는다
        self.assertEqual(self.features["3"]["target"], "biotite")

    def test_연대와_방법(self):
        p = self.features["2"]
        self.assertEqual(p["age"], "546 ± 4 (2σ)")
        self.assertEqual(p["method"], "U-Th-Pb (radiogenic) · zircon · SHRIMP · 207Pb*/206Pb* · Metamorphism (regional)")
        self.assertNotIn("age", self.features["1"])

    def test_참고문헌의_DOI_는_제목으로_잇는다(self):
        self.assertEqual(self.features["1"]["doi"], "https://doi.org/10.1017/S095410209500037X")
        self.assertEqual(self.features["2"]["doi"], "https://doi.org/10.1016/j.precamres.2012.11.011")   # BibTeX 의 ø
        self.assertNotIn("doi", self.features["3"])


class Fetched(TestCase):
    """받기를 흉내 내고 명령으로 굽는다 — 원본은 날짜 폴더에, 점은 한 덩이로."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(PETROCHRON_DIR=tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        self.dir = Path(tmp.name)
        with mock.patch.object(petrochron, "_get", side_effect=[DB, BIB]) as got, \
                mock.patch.object(petrochron.time, "sleep") as slept:
            call_command("fetch_petrochron", stdout=io.StringIO())
        self.calls, self.slept = [c.args[0] for c in got.call_args_list], slept.call_count

    def test_파일_둘을_쉬며_받아_원본을_둔다(self):
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(self.calls[0].endswith("/PetroChron_Antarctica_db_0_1.csv/content"))
        self.assertEqual(self.slept, 1)
        folder = next((self.dir / "raw").glob("2*"))
        with gzip.open(folder / "db.csv.gz") as fh:
            self.assertEqual(fh.read(), DB)

    def test_점_레이어(self):
        r = self.client.get("/GSM/points/", {"layer": petrochron.LAYER})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["style"], "class")
        self.assertEqual(len(data["features"]), 3)
        self.assertEqual({row["code"]: row["count"] for row in data["legend"]}, {"volcanic": 1, "plutonic": 1, "metamorphic": 1})
        self.assertEqual({row["shape"] for row in data["legend"]}, {"diamond"})
        self.assertEqual(data["links"], ["doi"])

    def test_받지_않고_다시_굽는다(self):
        petrochron.path().unlink()
        call_command("fetch_petrochron", "--offline", stdout=io.StringIO())
        self.assertTrue(petrochron.available())


class NotFetched(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(PETROCHRON_DIR=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_503_으로_까닭을_말한다(self):
        r = self.client.get("/GSM/points/", {"layer": petrochron.LAYER})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_petrochron", r.json()["error"])


class Seed(SimpleTestCase):
    def test_씨앗과_팝업_이름에_영어가_있다(self):
        seed = json.loads(Path(settings.PETROCHRON_CATALOG_SEED).read_text(encoding="utf-8"))
        self.assertEqual(seed["_상류"], "petrochron")
        for name in seed["레이어군순서"]:
            self.assertIn(name, i18n.GROUP_EN)
        for layer in seed["레이어"]:
            self.assertTrue(petrochron.knows(layer["name"]))
            self.assertIn(layer["name"], i18n.LAYER_EN)
            self.assertIn(layer["name"], i18n.ABSTRACT_EN)
        for label in petrochron.LABELS.values():
            self.assertIn(label, i18n.PROP_EN)
