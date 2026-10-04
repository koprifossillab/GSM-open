"""동남아 — 인도네시아 ESDM·말레이시아 JMG·필리핀 MGB·태국 DMR, 묶음 (wetherilli 228). 상류는 바꿔 끼운다.

응답의 꼴은 2026-10-04 에 받아 본 그대로다 — 인도네시아·필리핀은 ESRI XML, 태국은 geojson(태국어 열), 말레이시아는 REST identify.
"""
import json
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import arcwms, dmr, esdm, i18n, jmg, mgb, views

WMS = {"crs": "EPSG:3857", "bbox": "11970000,-770000,11990000,-750000", "width": "256", "height": "256", "i": "10", "j": "20"}

ID_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<FeatureInfoResponse xmlns="http://www.esri.com/wms" xmlns:esri_wms="http://www.esri.com/wms">
 <FIELDS OBJECTID="20278" KodeUnsur="IA03040120" NotasiFormasi="Qyt" NamaFormasi="Pumiceous Tuff" UmurFormasi="Kuarter"
  Keterangan="Tuff Berbatuapung" Metadata="GEOLOGIINDONESIA_AR_100K_2018.xml" Shape="Polygon"/>
</FeatureInfoResponse>'''
PH_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<FeatureInfoResponse xmlns:esri_wms="http://www.esri.com/wms" xmlns="http://www.esri.com/wms">
<FIELDS OBJECTID="6363" Shape="Polygon" TagKey="S-N1" Age="Oligocene - Miocene" GeneralLithology="Sedimentary and Metamorphic Rocks"
 Lithology="Sandstone,shales,reef limestone" Lithologydescription="Extensive mixed shelf marine deposits" DetailedDescription="Null"/>
</FeatureInfoResponse>'''
TH_PROPS = {"OBJECTID": "18542", dmr.SYMBOL: "Qa", dmr.YEAR: "2003"}
TH_LEGEND = {"layers": [{"layerId": 0, "legend": [
    {"label": "Qa ตะกอนที่ราบลุ่มน้ำ", "imageData": "QA", "contentType": "image/png"},
    {"label": "Trm", "imageData": "TR", "contentType": "image/png"},
    {"label": "Water body", "imageData": "WB", "contentType": "image/png"}]}]}
MY_KL = {"AGE": "Caroboniferous - Permian", "GAM": "Permian", "GAX": "CARBONIFEROUS", "GLS": "Arenaceous", "GLN": "Null",
         "GFD": "Mainly schist, phyllite, slate …", "STATE": "WP Kuala Lumpur"}
MY_SARAWAK = {"GLN": "Tuang formation", "GAM": "Early Triassic", "GAX": "Early Pennsylvanian", "GLS": "Regional", "GLL": "PzTg",
              "NAM": "Sarawak"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://x/",
                     json=lambda: body)


class Shared(SimpleTestCase):
    def test_ESRI_XML(self):
        rows = arcwms.fields_xml(PH_XML)
        self.assertEqual(rows[0]["TagKey"], "S-N1")
        self.assertNotIn("DetailedDescription", rows[0])                 # Null 은 뺀다

    def test_영어_시대_다듬기(self):
        self.assertEqual(i18n.age_tidy("Quaternary [Holocene]"), "Holocene")
        self.assertEqual(i18n.age_tidy("Upper Miocene - Pliestocene"), "Late Miocene – Pleistocene")
        self.assertEqual(i18n.age_tidy("CRETACEOUS, JURASSIC"), "Jurassic – Cretaceous")        # 젊은, 오랜
        self.assertEqual(i18n.age_tidy("Pre-Jurassic"), "Pre-Jurassic")


class Indonesia(SimpleTestCase):
    def test_XML_속성과_인도네시아어_시대(self):
        with mock.patch("viewer.esdm.requests.get", return_value=response(content=ID_XML, ctype="text/xml")) as get:
            data = esdm.get_feature_info(dict(WMS, layers="esdm:geology", query_layers="esdm:geology"))
        self.assertEqual(get.call_args[1]["params"]["layers"], "0")
        out = esdm.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["이름"], out["지질시대"]), ("Qyt", "Pumiceous Tuff", "제4기"))
        self.assertEqual(esdm.age("Permo Karbon", "en"), "Carboniferous – Permian")
        self.assertEqual(esdm.age("Pra Tersier"), "Pra Tersier")                                 # 옮기지 못하면 원문


class Philippines(SimpleTestCase):
    def test_속성(self):
        with mock.patch("viewer.mgb.requests.get", return_value=response(content=PH_XML, ctype="text/xml")):
            data = mgb.get_feature_info(dict(WMS, layers="mgb:geology", query_layers="mgb:geology"))
        out = mgb.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["지질시대"]), ("S-N1", "올리고세~마이오세"))


class Thailand(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-sea-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_기호에서_시대(self):
        self.assertEqual(dmr.age_of("Trm"), "Triassic")
        self.assertEqual(dmr.age_of("KTpk"), "Cretaceous – Tertiary")
        self.assertEqual(dmr.age_of("SDCtn"), "Silurian – Carboniferous")
        self.assertEqual(dmr.age_of("PE"), "Precambrian")
        self.assertEqual(dmr.age_of("Png3"), "Permian")
        self.assertEqual(dmr.age_of("Water body"), "")

    def test_속성에_범례의_이름을_붙인다(self):
        def fake(url, params=None, **kw):
            return response(TH_LEGEND if url.endswith("/legend") else {"features": [{"properties": dict(TH_PROPS)}]})
        with mock.patch("viewer.dmr.requests.get", side_effect=fake):
            data = dmr.get_feature_info(dict(WMS, layers="dmr:rock_units", query_layers="dmr:rock_units"))
        out = dmr.friendly(data["features"][0]["properties"])
        self.assertEqual((out["기호"], out["이름"], out["지질시대"], out["편집 연도"]), ("Qa", "ตะกอนที่ราบลุ่มน้ำ", "제4기", "2003"))

    def test_목록_범례(self):
        with mock.patch("viewer.dmr.requests.get", return_value=response(TH_LEGEND)):
            got = self.client.get("/GSM/list/legend/", {"layer": "dmr:rock_units"}).json()
        self.assertEqual([(r["symbol"], r["age"]) for r in got["rows"]], [("Qa", "제4기"), ("Trm", "트라이아스기")])
        self.assertEqual(self.client.get("/GSM/list/legend/", {"layer": "mgb:geology"}).status_code, 400)


class Malaysia(SimpleTestCase):
    def test_주_열다섯을_한_장으로(self):
        with mock.patch("viewer.jmg.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            jmg.get_map(dict(WMS, layers="jmg:lithology", format="image/png"))
        path, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(path.endswith("/MapServer/export"))
        self.assertEqual(params["layers"], "show:" + ",".join(str(i) for i in range(0, 30, 2)))

    def test_반도와_보르네오의_속성(self):
        self.assertEqual(jmg.friendly(MY_KL)["지질시대"], "석탄기~페름기")              # GAM·GAX 에서 — AGE 의 오탈자를 피한다
        out = jmg.friendly(MY_SARAWAK)
        self.assertEqual((out["이름"], out["주"]), ("Tuang formation", "Sarawak"))
        self.assertTrue(out["지질시대"].endswith("트라이아스기 전기"))


class Catalog(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_나라_탭과_묶음(self):
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        for name, region in (("esdm:geology", "indonesia"), ("jmg:lithology", "malaysia"), ("mgb:geology", "philippines"),
                             ("dmr:rock_units", "thailand")):
            group, layer = rows[name]
            self.assertEqual((group["region"], layer["projection"]), (region, "EPSG:3857"), name)
        self.assertEqual(rows["esdm:geology"][1]["maxZoom"], esdm.LAST_ZOOM)
        self.assertEqual(rows["dmr:rock_units"][1]["legendUrl"], "list/legend/")
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        sea = re.search(r'southeast_asia: \{ title: "동남아".*?includes: \[([^\]]*)\]', js, re.S).group(1)
        for key in ("thailand", "malaysia", "indonesia", "philippines"):
            self.assertIn(f'"{key}"', sea)
        js3d = (Path(views.__file__).parent / "static/viewer/map3d.js").read_text(encoding="utf-8")
        self.assertIn('southeast_asia: ["thailand", "malaysia", "indonesia", "philippines"]', js3d)

    def test_미리_데우기와_3D(self):
        from viewer.management.commands import prewarm
        for name, up in (("esdm:geology", "esdm"), ("jmg:lithology", "jmg"), ("mgb:geology", "mgb"), ("dmr:rock_units", "dmr")):
            self.assertIsNotNone(prewarm.plan_for(name, up), name)
            self.assertIn(up, views.MAP3D_WMS)
