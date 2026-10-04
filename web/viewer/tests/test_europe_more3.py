"""유럽 — 오스트리아 GeoSphere·폴란드 PIG·네덜란드 TNO·벨기에(플랑드르 DOV·왈로니아 SPW) (wetherilli 237). 상류는 바꿔 끼운다.

속성의 꼴은 2026-10-04 에 받아 본 그대로다.
"""
import json
import re
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from viewer import dov, geosphere, i18n, pig, spw, tno, views

WMS = {"crs": "EPSG:3857", "bbox": "1500000,6000000,1510000,6010000", "width": "256", "height": "256", "i": "10", "j": "20"}

HALLSTATT = {"OBJECTID": "619", "Beschreibung": "Kalkstein, Dolomit, Mergel, Mergelstein, Tonschiefer, Sandstein; Perm - frühe Kreide",
             "Tektonik": "Juvavisches Deckensystem", "GBANR": "3596.1100.2302"}
KRAKOW = {"Opis wydzielenia": "Wapienie, margle, mułowce, iłowce", "Litologia": "wapienie, margle, mułowce, iłowce",
          "Stratygrafia": "jura górna", "Geneza": "morska, szelfu węglanowego", "Klimatostratygrafia": "Null"}
UTRECHT = {"CODE": "b", "OMSCHRIJVI": "Zandige stroomgordelafzettingen", "LITHOSTRAT": "Formatie van Echteld-b",
           "OUDERDOM": "Holoceen", "NAAM1": "Formatie van Echteld", "VERWIJZING": "https://www.dinoloket.nl/…"}
LEUVEN = {"code": "Br", "formatie": "Formatie van Brussel", "lid": None, "beschrijving": "bleekgrijs fijn zand, kalkhoudend"}
NAMUR = {"Sigle": "AMO", "Nom de la formation": "Alluvions modernes", "Description générale": "Galets, graviers, sables, argiles et limons.",
         "Système": "Quaternaire", "Série": "Holocène", "Etage": "Null", "Numéro de planche": "47/3-4", "Nom de planche": "Namur - Champion",
         "Auteurs": "Delcambre B."}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class LocalAges(SimpleTestCase):
    def test_네_언어(self):
        self.assertEqual(i18n.age_local("Perm - frühe Kreide"), "Permian – Early Cretaceous")
        self.assertEqual(i18n.age_local("jura górna"), "Late Jurassic")
        self.assertEqual(i18n.age_local("kampan"), "Campanian")
        self.assertEqual(i18n.age_local("Holoceen"), "Holocene")
        self.assertEqual(i18n.age_local("Dévonien inférieur"), "Early Devonian")
        self.assertEqual(i18n.age_local("Mitteleozän x"), "")                    # 모르면 빈 글 — 원문을 보인다


class Doors(SimpleTestCase):
    def test_오스트리아_두_서비스(self):
        with mock.patch("viewer.geosphere.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            geosphere.get_map(dict(WMS, layers="geosphere:faults", format="image/png"))
        self.assertIn("/tektonische_linien_1m/", get.call_args[0][0])
        self.assertEqual(get.call_args[1]["params"]["layers"], "0,6")
        out = geosphere.friendly(HALLSTATT)
        self.assertEqual(out["지질시대"], "페름기~백악기 전기")
        self.assertTrue(out["암석"].startswith("Kalkstein"))

    def test_폴란드_세_층을_겹친다(self):
        with mock.patch("viewer.pig.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            pig.get_map(dict(WMS, layers="pig:mgp500k", format="image/png"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "1,6,11")         # REST 번호가 아니다
        out = pig.friendly(KRAKOW)
        self.assertEqual(out["지질시대"], "쥐라기 후기")
        self.assertNotIn("빙하 층서", out)

    def test_네덜란드는_열을_골라(self):
        with mock.patch("viewer.tno.requests.get", return_value=response({"features": [{"properties": UTRECHT}]})) as get:
            data = tno.get_feature_info(dict(WMS, layers="tno:geology", query_layers="tno:geology"))
        self.assertIn("OUDERDOM", get.call_args[1]["params"]["propertyName"])     # 모양째 7 MB 를 피한다
        self.assertEqual(tno.friendly(data["features"][0]["properties"])["지질시대"], "홀로세")

    def test_플랑드르는_층마다_열이_다르다(self):
        with mock.patch("viewer.dov.requests.get", return_value=response({"features": [{"properties": LEUVEN}]})) as get:
            dov.get_feature_info(dict(WMS, layers="dov:tertiair_50k", query_layers="dov:tertiair_50k"))
        self.assertEqual(get.call_args[1]["params"]["propertyName"], "code,formatie,lid,beschrijving")
        self.assertEqual(dov.friendly(LEUVEN), {"기호": "Br", "이름": "Formatie van Brussel", "설명": "bleekgrijs fijn zand, kalkhoudend"})

    def test_왈로니아(self):
        out = spw.friendly(NAMUR)
        self.assertEqual((out["기호"], out["지질시대"], out["도폭"]), ("AMO", "홀로세", "47/3-4 Namur - Champion"))


class Catalog(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 카탈로그는 반마다 한 번 — 시험마다 넣으면 0.5 초씩 든다 (wetherilli 294)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_나라_탭과_유럽_묶음(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name, region in (("geosphere:geology", "austria"), ("pig:mgp500k", "poland"), ("tno:geology", "netherlands"),
                             ("dov:tertiair_50k", "belgium"), ("spw:geology", "belgium")):
            group, layer = rows[name]
            self.assertEqual((group["region"], layer["projection"]), (region, "EPSG:3857"), name)
        self.assertEqual(rows["pig:mgp500k"][1]["maxZoom"], pig.MAX_ZOOM)
        self.assertEqual(rows["spw:geology"][1]["minZoom"], spw.MIN_ZOOM)
        self.assertFalse(rows["pig:faults"][1]["queryable"])
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        europe = re.search(r'europe: \{ title: "유럽".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        for key in ("austria", "poland", "netherlands", "belgium"):
            self.assertIn(f'"{key}"', europe)

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        for name, up in (("geosphere:geology", "geosphere"), ("pig:mgp500k", "pig"), ("tno:geology", "tno"),
                         ("dov:tertiair_50k", "dov"), ("spw:geology", "spw")):
            self.assertIsNotNone(prewarm.plan_for(name, up), name)
            self.assertIn(up, views.MAP3D_WMS)


#: 오스트리아 1:5만 — 바트 이슐 도폭의 다흐슈타인 석회암 (wetherilli 239)
DACHSTEIN = {"geologicUnitName": "Dachsteinkalk", "description": "Dachsteinkalk, gebankt (Megalodontenfazies; Nor bis ?Rhät)",
             "lithology": "Kalkstein (Kalk)", "representativeAge": "Obertrias", "tectonicUnitName": "Oberostalpin",
             "collectionName": "Geologische Einheiten 1:50000, Blatt 96-Bad Ischl (Oberflächengeologie)"}
ZAKOPANE = {"Nr arkusza": "1060", "Wydzielenia": "Piaski, żwiry, bloki i głazy den dolinnych",
            "Geneza": "osady rzeczne (fluwialne, aluwialne)", "Stratygrafia": "Holocen"}


class FiftyK(SimpleTestCase):
    def test_오스트리아_1_5만은_REST(self):
        with mock.patch("viewer.geosphere.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            geosphere.get_map(dict(WMS, layers="geosphere:units50k", format="image/png"))
        self.assertTrue(get.call_args[0][0].endswith("/einheiten_50/MapServer/export"))
        with mock.patch("viewer.geosphere.requests.get", return_value=response({"results": [{"attributes": DACHSTEIN}]})) as get:
            data = geosphere.get_feature_info(dict(WMS, layers="geosphere:units50k", query_layers="geosphere:units50k"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "all:0")
        out = geosphere.friendly(data["features"][0]["properties"])
        self.assertEqual((out["이름"], out["지질시대"], out["지구조 구역"]), ("Dachsteinkalk", "트라이아스기 후기", "Oberostalpin"))
        with self.assertRaises(geosphere.GeosphereError):
            geosphere.get_legend("geosphere:units50k")

    def test_폴란드_1_5만은_다른_서비스(self):
        with mock.patch("viewer.pig.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            pig.get_map(dict(WMS, layers="pig:smgp50k", format="image/png"))
        self.assertIn("/smgp50k/", get.call_args[0][0])
        self.assertEqual(get.call_args[1]["params"]["layers"], "0")                       # REST 번호(5)가 아니다
        self.assertEqual(pig.friendly(ZAKOPANE), {"설명": "Piaski, żwiry, bloki i głazy den dolinnych",
                                                  "성인": "osady rzeczne (fluwialne, aluwialne)", "지질시대": "홀로세", "도폭": "1060"})



class FiftyKCatalog(TestCase):
    def test_가까이서만(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        self.assertEqual((rows["geosphere:units50k"]["minZoom"], rows["pig:smgp50k"]["minZoom"]), (11, 13))
        self.assertFalse(rows["pig:smgp50k_lines"]["queryable"])
