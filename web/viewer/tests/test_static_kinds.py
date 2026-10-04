"""정적 판의 극지 상류 — `static_tables.py` 와 `static-kinds.js` (wetherilli 161). 상류를 부르지 않는다.

JS 는 문자열과 꼴로 지킨다. node 가 있으면 JS 의 손질(지질시대 옮기기·NPI·EMODnet·GEUS 이름 표)을 파이썬의 것과 같은 입력으로
대조한다 — 두 벌이 갈라지면 깨진다. node 가 없으면(CI) 그 대조만 건너뛴다.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from viewer import emodnet, ga, geus, grportal, i18n, kopri, mrdata, npolar, sgc, sgu, static_tables, views

JS = Path(__file__).resolve().parents[1] / "static" / "viewer" / "static-kinds.js"


class Tables(SimpleTestCase):
    def setUp(self):
        self.t = static_tables.tables()

    def test_JSON_으로_뜬다(self):
        self.assertLess(len(json.dumps(self.t, ensure_ascii=False)), 200_000)

    def test_문의_표를_그대로(self):
        self.assertEqual(self.t["npolar"]["tiles"], npolar.TILES)
        self.assertEqual(self.t["npolar"]["friendly"], list(npolar.FRIENDLY.items()))
        self.assertEqual(self.t["geus"]["friendly"], geus.FRIENDLY)
        self.assertEqual(self.t["emodnet"]["friendly"], [list(p) for p in emodnet.FRIENDLY]
                         if isinstance(self.t["emodnet"]["friendly"][0], list) else list(emodnet.FRIENDLY))
        self.assertEqual(self.t["age"]["words"], i18n.AGE_WORDS_KO)
        self.assertEqual(self.t["maxFeatures"], views.MAX_FEATURES)

    def test_KPDC_지도_서버는_싣고_연구실_것은_싣지_않는다(self):
        self.assertEqual(set(self.t["kopri"]["wms"]), set(kopri.WMS))
        # 이름 표(`propEn`)는 글자뿐이다 — 레이어·주소가 든 자리만 본다
        text = json.dumps({k: v for k, v in self.t.items() if k not in ("propEn", "linkEn")}, ensure_ascii=False)
        for lab in ("geo3al", "phyloserver", "peninsula"):
            self.assertNotIn(lab, text)

    def test_점_명세에_주소와_열이_있다(self):
        portal = self.t["grportal"]["points"]["grportal:geochron"]
        self.assertTrue(portal["url"].endswith("/FeatureServer/0/query"))
        self.assertEqual(portal["fields"]["age"]["from"], "age_num")
        rock = self.t["npolar"]["points"]["npolar:rock_archive"]
        self.assertEqual((rock["oid"], rock["style"]), ("ObjectId", "rock"))


class Script(SimpleTestCase):
    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")
        # 주석을 뺀 코드 — 주석은 서버 판과 견주느라 서버 주소를 적는다
        self.code = re.sub(r"/\*.*?\*/|//[^\n]*", "", self.js, flags=re.S)

    def test_꼴(self):
        self.assertIn("window.GSM_STATIC_KINDS = KINDS", self.js)
        for up in ("geus", "npolar", "grportal", "pgc", "emodnet", "kopri", "sgc", "mrdata", "ga", "sgu"):
            self.assertIn(f"KINDS.{up} =", self.js)

    def test_서버를_부르지_않는다(self):
        for path in ('BASE + "wms"', "featureinfo/", "/GSM/", 'BASE + "points'):
            self.assertNotIn(path, self.code)

    def test_상류_주소를_박지_않는다(self):
        # 주소는 빌드가 서버의 문에서 떠 싣는 표에서 읽는다 — 상류가 바뀌면 문 하나만 고친다
        for host in ("geodata.npolar.no", "data.geus.dk", "arcgis.com", "emodnet-geology", "kpdcgeo", "sgc.gov.co", "mrdata.usgs.gov", "services.ga.gov.au", "sgu.se"):
            self.assertNotIn(host, self.code)

    def test_GEUS_는_정사각이_아닌_타일로(self):
        self.assertIn("tileSize: [512, 511]", self.js)
        self.assertIn("tileGrid: geusGrid()", self.js)
        self.assertIn('stored("gsm.key.geus")', self.js)

    def test_저장소는_try_로(self):
        self.assertIn("try { return localStorage.getItem(key)", self.js)


class SameAsPython(SimpleTestCase):
    """JS 와 파이썬이 같은 입력에 같은 답을 내는지 — node 가 있을 때만"""

    def test_손질이_같다(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 가 없다")
        ages = ["late Paleocene", "Early - Middle Triassic", "Carboniferous - Permian", "Neoproterozoic (?)",
                "Palaeoproterozoic", "Early Palaeozoic", "Cambrian and/or Ordovician", "Middle Jurassic ?",
                "Statherian 1 (1800-1770 Ma)", "? Oligocene - Miocene", "Early"]
        npi = [{"NAME": "Hecla Hoek", "AGE_PERIOD": "Neoproterozoic", "AGE_BASE": "Early Palaeozoic",
                "URL": "https://example.org/x", "Date": "20230910", "Length_km": "3,595676", "GEO_CODE": "  "},
               {"Stratigraphic Unit": "Billefjorden Group", "URL": "javascript:alert(1)", "AGE_TOP": "late Paleocene"}]
        emo = [{"label_litho": "limestone", "label_age": "Pennsylvanian - Permian", "scale": 5000000,
                "reference": "Reference: Asch 2005", "name": None},
               {"folk_7cl_txt": "4. Mixed sediment", "fault_name": "n/a", "scale": "2000000"}]
        plain = "Layer 'grl'\n  Feature 733: \n    gu_name = 'Rapakivi Suite'\n    ics_min_age_num = '1600.000000'\n    rgb = '1'\n"
        # 갈래 — 레이어마다 줄마다 그 줄에 맞는 값 하나, 그리고 아무 데도 안 맞는 빈 것
        classes = []
        for name, spec in grportal.LAYERS.items():
            c = spec.get("classes")
            if not c:
                continue
            samples = [{}]
            for row in c["table"]:
                heads = row[4]
                if isinstance(heads, dict) and "top" in heads:
                    samples.append({heads["top"]: 3, **{k: 1 for k in heads["of"] if k != heads["top"]}})
                elif isinstance(heads, dict):
                    samples.append({heads["gt0"]: 2})
                elif c.get("numeric"):
                    samples.append({c["by"]: heads[0]})
                else:
                    samples.append({c["by"]: (heads[0] if isinstance(heads, tuple) else heads) + "x"})
            classes.append([name, samples, [grportal.class_of(spec, p)[0] for p in samples]])
        # 콜롬비아 1:50만(wetherilli 201) — 에스파냐어 값은 그대로, "Null" 은 뺀다
        sgc_props = [{"OBJECTID": "5241", "Símbolo UC": "Q-ca", "Descripción": "Abanicos aluviales y depósitos coluviales",
                      "Edad": "Cuaternario", "Comentarios": "Null", "Codigo UC": "187"},
                     {"Símbolo UC": "  ", "Edad": "null", "Nombre": "Falla de Romeral", "Tipo": "Inversa"}]
        usgs_gml = ("<wfs:FeatureCollection><gml:featureMember><ms:Lithology><ms:state>CO</ms:state><ms:orig_label>Qa</ms:orig_label>"
                    "<ms:generalize>Unconsolidated</ms:generalize><ms:url>https://mrdata.usgs.gov/x?a=1&amp;b=2</ms:url>"
                    "<ms:src_url>ftp://no</ms:src_url></ms:Lithology></gml:featureMember></wfs:FeatureCollection>")
        # 스웨덴 SGU(wetherilli 213) — 1:100만은 영어 열, 5만은 스웨덴어, `Null:…` 칸은 뺀다
        sgu_props = [{"lithology": "Metagreywacke, mica schist", "tect_unit": "Svecokarelian orogen", "subunit": "Bergslagen",
                      "litologi": "Metagråvacka", "etikett": 625},
                     {"geo_enh_tx": "Svekokarelska orogenen, intrusivbergart", "lito_n_tx": "Null:okänt", "bergart_tx": "Granit",
                      "handel1_tx": "intrusionsprocess; orosirium 7 1820-1800 Ma; Null:okänt; Null:ej_tillämpligt", "partik1_tx": ""}]
        usgs_plain = [{"class": "102", "label": "", "state_unit": "Water", "age_range": "late Paleocene",
                       "url": "https://mrdata.usgs.gov/sim3340/show-sim3340.php?seq=A002"}]
        ga_props = [{"mapSymbol": "Cza", "name": "alluvium", "geologicHistory": "Cenozoic to Quaternary", "lithology": "regolith",
                     "resolutionScale": "2500000", "bodyMorphology": "Null"}, {"plotSymbol": "Ag", "geologicHistory": "Archean"}]
        expected = {"ages": [i18n.age_ko(a) for a in ages], "npi": [npolar.friendly(p, "ko") for p in npi],
                    "ga": [ga.friendly(p, "ko") for p in ga_props],
                    "sgc": [sgc.friendly(p, "ko") for p in sgc_props],
                    "sgu": [sgu.friendly(p, "ko") for p in sgu_props],
                    # 미국 USGS(wetherilli 205) — GML 읽기와 손질
                    "usgs": [mrdata.friendly(f["properties"], "ko") for f in mrdata.parse_gml(usgs_gml, "Lithology")]
                    + [mrdata.friendly(p, "ko") for p in usgs_plain],
                    "emo": [emodnet.friendly(p, "ko") for p in emo],
                    "plain": [geus.friendly(f["properties"]) for f in geus.parse_plain(plain)],
                    "classes": classes}
        harness = """
const fs = require('fs'); const inp = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
global.window = {GSM_STATIC_TABLES: inp.tables}; global.document = {documentElement: {lang: 'ko'}};
global.localStorage = {getItem: () => null}; global.sessionStorage = {getItem: () => null}; global.ol = {};
eval(fs.readFileSync(process.argv[3], 'utf8')); const H = window.GSM_STATIC_HELPERS;
const P = inp.tables.grportal.points;
console.log(JSON.stringify({ages: inp.ages.map(H.ageKo), npi: inp.npi.map(H.npiFriendly), emo: inp.emo.map(H.emodFriendly),
  sgc: inp.sgc.map(H.sgcFriendly), sgu: inp.sgu.map(H.sguFriendly), ga: inp.ga.map(H.gaFriendly),
  usgs: H.usgsGml(inp.usgsGml, "Lithology").map(f => H.usgsFriendly(f.properties)).concat(inp.usgsPlain.map(H.usgsFriendly)),
  plain: H.parsePlain(inp.plain).map(f => H.geusFriendly(f.properties)),
  classes: inp.classes.map(([n, samples]) => [n, samples, samples.map(p => H.classOf(P[n].classes, p)[0])])}));
"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "in.json").write_text(json.dumps({"tables": static_tables.tables(), "ages": ages, "npi": npi,
                                                        "emo": emo, "plain": plain, "classes": classes,
                                                        "sgc": sgc_props, "sgu": sgu_props, "usgsGml": usgs_gml, "usgsPlain": usgs_plain, "ga": ga_props},
                                                       ensure_ascii=False), "utf-8")
            Path(tmp, "h.js").write_text(harness, "utf-8")
            out = subprocess.run([node, str(Path(tmp, "h.js")), str(Path(tmp, "in.json")), str(JS)],
                                 capture_output=True, text=True, timeout=60, check=True).stdout
        self.assertEqual(json.loads(out), json.loads(json.dumps(expected, ensure_ascii=False)))
