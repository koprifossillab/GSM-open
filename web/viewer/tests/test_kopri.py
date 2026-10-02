"""극지연구소 — 암석 시료·KPDC 자료·운석·기지·해안선 (053–057).

상류를 부르지 않는다. 받은 쪽(HTML·JSON)을 흉내 내 읽는 틀과, 모아 둔 파일을 화면에 내는 길을 본다.
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import kopri
from viewer.models import Layer, LayerGroup

ROCK_PAGE = """<table><tbody>
 <tr><td class="active"><a href='/rock/0714'>0714</a></td><td>2020-01-01</td><td>Antarctica Victoria Land</td>
 <td>plutonic</td><td></td><td>Cambrian</td><td>-74.4773,165.3399</td> </tr>
 <tr><td class="active"><a href='/rock/073001'>073001</a></td><td>2014-07-30</td><td>Arctic areas Svalbard</td>
 <td>Sedimentary</td><td>Wordiekammen Fm.</td><td>Carboniferous</td><td>78.65,16.4</td> </tr>
 <tr><td class="active"><a href='/rock/9'>9</a></td><td></td><td></td><td>IGNEOUS</td><td></td><td></td><td>0,0</td></tr>
</tbody></table>"""

LIST_PAGE = """<tbody>
<tr class="item result-item" data-id="55e44fc3-7bf0-487b-b1cb-cdf5b5850af4"
    data-title="Box Core &amp; more" data-coord="[[1,2]]">
 <td>1</td><td class="lt_title"><a href="/search/55e44fc3-7bf0-487b-b1cb-cdf5b5850af4">
 <span class="entry_id">[KOPRI-KPDC-00003172]</span>Box Core</a></td></tr>
</tbody>"""

DETAIL_PAGE = """
<dl><dt>Entry ID</dt><dd>KOPRI-KPDC-00003172</dd></dl>
<dl><dt>DOI</dt><dd>https://dx.doi.org/doi:10.22663/KOPRI-KPDC-00003172</dd></dl>
<dl><dt>Science Keyword</dt><dd>EARTH SCIENCE        &gt; OCEANS    &gt; MARINE SEDIMENTS  &gt; SEDIMENTATION</dd></dl>
<dl><dt>Research period</dt><dd>2019-01-01 ~ 2019-01-31</dd></dl>
<dl><dt>Location</dt><dd>OCEAN   &gt; SOUTHERN OCEAN  &gt; ROSS SEA   </dd></dl>
<dl class="dview_map_list"><dt>Spatial Coverage</dt><dd>
 <div class="point-block"><p class="point-header">POINT</p><ul class="point-list">
  <li><span class="text-muted">lat:</span>-75.088668, <span class="text-muted">lon:</span>-165.056272</li>
 </ul></div>
 <div class="point-block"><p class="point-header">POLYGON</p><ul class="point-list">
  <li><span class="text-muted">lat:</span>-72.0, <span class="text-muted">lon:</span>150.0</li>
  <li><span class="text-muted">lat:</span>-77.0, <span class="text-muted">lon:</span>170.0</li>
 </ul></div>
</dd></dl>
<dd><a href="https://koreamet.kopri.re.kr/db/178" target="_blank">x</a></dd>
"""


class Parse(SimpleTestCase):
    def test_암석_목록(self):
        rows = kopri.parse_rock_page(ROCK_PAGE)
        self.assertEqual([r["sample"] for r in rows], ["0714", "073001", "9"])
        self.assertEqual(rows[1]["strat"], "Wordiekammen Fm.")
        self.assertEqual(kopri.rock_coord(rows[0]["coord"]), (-74.4773, 165.3399))
        self.assertIsNone(kopri.rock_coord(rows[2]["coord"]))      # 0,0 은 좌표가 없는 것

    def test_암석_갈래는_접어서(self):
        self.assertEqual(kopri.rock_class("IGNEOUS"), "plutonic")
        self.assertEqual(kopri.rock_class("Sediment"), "sedimentary")
        self.assertEqual(kopri.rock_class(""), "other")

    def test_마지막_장을_되풀이하면_멈춘다(self):
        pages = []

        def fake(url, params=None, **kw):
            pages.append(params["page"])
            return mock.Mock(text=ROCK_PAGE)                       # 상류는 늘 같은 장을 준다
        with mock.patch.object(kopri, "_get", fake):
            rows = kopri.harvest_rock(pause=0)
        self.assertEqual(len(rows), 3)
        self.assertEqual(pages, [0, 1])

    def test_목록(self):
        self.assertEqual(kopri.parse_list_page(LIST_PAGE), [{
            "uuid": "55e44fc3-7bf0-487b-b1cb-cdf5b5850af4", "id": "KOPRI-KPDC-00003172", "title": "Box Core & more"}])

    def test_상세(self):
        d = kopri.parse_detail(DETAIL_PAGE)
        self.assertEqual(d["keywords"], ["EARTH SCIENCE > OCEANS > MARINE SEDIMENTS > SEDIMENTATION"])
        self.assertEqual(d["location"], ["OCEAN > SOUTHERN OCEAN > ROSS SEA"])
        self.assertEqual(d["period"], "2019-01-01 ~ 2019-01-31")
        self.assertEqual(d["shapes"], [["POINT", [(-75.088668, -165.056272)]],
                                       ["POLYGON", [(-72.0, 150.0), (-77.0, 170.0)]]])
        self.assertEqual(d["link"], "https://koreamet.kopri.re.kr/db/178")


class Shapes(SimpleTestCase):
    def test_주제(self):
        self.assertEqual(kopri.topic_of(["EARTH SCIENCE > OCEANS > MARINE SEDIMENTS > X"]), "sediment")
        self.assertEqual(kopri.topic_of(["EARTH SCIENCE > OCEANS > SALINITY"]), "ocean")
        self.assertEqual(kopri.topic_of(["Earth Science > Solid Earth > Rocks"]), "solid")
        self.assertEqual(kopri.topic_of([]), "other")

    def test_모서리_둘은_위선을_따라_휜_네모(self):
        g = kopri._shape_geometry("POLYGON", [(-72.0, 150.0), (-77.0, 170.0)])
        ring = g["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertGreater(len(ring), 20)                         # 네 점이 아니다
        self.assertTrue(all(150 <= x <= 170 and -77 <= y <= -72 for x, y in ring))

    def test_날짜변경선을_넘는_네모(self):
        ring = kopri._shape_geometry("POLYGON", [(-72.0, 170.0), (-75.0, -170.0)])["coordinates"][0]
        self.assertTrue(all(x >= 170 or x <= -170 for x, _ in ring))

    def test_넓은_범위는_그리지_않는다(self):
        self.assertIsNone(kopri._shape_geometry("POLYGON", [(-85.0, 0.5), (-60.0, 180.0)]))
        self.assertEqual(kopri._shape_geometry("POINT", [(-85.0, 0.5), (-60.0, 180.0)])["type"], "MultiPoint")

    def test_기지(self):
        row = kopri._station({"geometry": {"type": "Point", "coordinates": [164.2008, -74.6153]},
                              "properties": {"facility_n": "Jang Bogo", "nationa_01": "KOR",
                                             "current_st": "Year-round", "notes": None}})
        self.assertEqual(row["properties"]["code"], "korea")
        self.assertNotIn("notes", row["properties"])
        row = kopri._station({"geometry": {"type": "Point", "coordinates": [0, -70]},
                              "properties": {"facility_n": "X", "current_st": "Seasonal"}})
        self.assertEqual(row["properties"]["code"], "season")


class Files(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.enterContext(override_settings(KOPRI_DIR=self.dir.name))
        kopri.save("rock", {"rows": kopri.parse_rock_page(ROCK_PAGE)})
        detail = kopri.parse_detail(DETAIL_PAGE)
        kopri.save("kpdc", {"records": {
            "u1": dict(detail, c="KPDC", id="KOPRI-KPDC-1", title="Box core"),
            "u2": dict(detail, c="KPDC", keywords=["EARTH SCIENCE > ATMOSPHERE > X"],
                       shapes=[["POLYGON", [(-85.0, 0.5), (-60.0, 180.0)]]]),
            "u3": dict(detail, c="KoreaMet", title="Thiel Mountains 06004",
                       shapes=[["POINT", [(-85.1572, -94.5418)]]]),
        }})

    def test_암석은_지역마다_갈라_싣는다(self):
        south = json.loads(kopri.file_body("kopri:rock_antarctica"))
        north = json.loads(kopri.file_body("kopri:rock_svalbard"))
        self.assertEqual([f["id"] for f in south["features"]], ["0714"])
        self.assertEqual([f["id"] for f in north["features"]], ["073001"])
        self.assertEqual(south["style"], "class")
        self.assertEqual(south["features"][0]["properties"]["age"], "캄브리아기")
        en = json.loads(kopri.file_body("kopri:rock_antarctica", "en"))
        self.assertEqual(en["features"][0]["properties"]["age"], "Cambrian")

    def test_KPDC_는_주제마다(self):
        sed = json.loads(kopri.file_body("kopri:kpdc_sediment"))
        self.assertEqual(sorted(f["geometry"]["type"] for f in sed["features"]), ["Point", "Polygon"])
        props = sed["features"][0]["properties"]
        self.assertEqual(props["page"], "https://kpdc.kopri.re.kr/search/u1")
        self.assertIn("page", sed["links"])
        atmo = json.loads(kopri.file_body("kopri:kpdc_atmo"))
        self.assertEqual((len(atmo["features"]), atmo["wide"]), (0, 1))

    def test_운석(self):
        met = json.loads(kopri.file_body("kopri:meteorites"))
        self.assertEqual(len(met["features"]), 1)
        self.assertEqual(met["features"][0]["properties"]["db"], "https://koreamet.kopri.re.kr/db/178")
        self.assertEqual(met["legend"][0]["count"], 1)


class View(TestCase):
    def setUp(self):
        group = LayerGroup.objects.create(name="극지연구소 시료", region="antarctica")
        Layer.objects.create(name="kopri:rock_antarctica", title="암석 시료", group=group, upstream="kopri")
        Layer.objects.create(name="kopri:coast_change", title="해안선 변화", group=group, upstream="kopri")
        Layer.objects.create(name="kopri:historic", title="역사 유적", group=group, upstream="kopri")
        north = LayerGroup.objects.create(name="KPDC 기본도", region="greenland")
        Layer.objects.create(name="kopri:greenland_ice_contours", title="빙상 등고선", group=north, upstream="kopri")

    def test_모으지_않았으면_503(self):
        with tempfile.TemporaryDirectory() as d, override_settings(KOPRI_DIR=d):
            r = self.client.get("/GSM/points/?layer=kopri:rock_antarctica")
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_kopri", r.json()["error"])

    def test_모아_둔_것을_낸다(self):
        with tempfile.TemporaryDirectory() as d, override_settings(KOPRI_DIR=d):
            kopri.save("rock", {"rows": kopri.parse_rock_page(ROCK_PAGE)})
            r = self.client.get("/GSM/points/?layer=kopri:rock_antarctica")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(json.loads(r.content)["features"]), 1)

    def test_카탈로그(self):
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual(rows["kopri:rock_antarctica"]["kind"], "points")
        self.assertEqual(rows["kopri:rock_antarctica"]["style"], "class")
        self.assertEqual(rows["kopri:coast_change"]["projection"], "EPSG:3031")
        # 북극 것은 3413 으로 받는다 — KPDC 는 3995 만 적어 두지만 GeoServer 가 그려 준다 (wetherilli 095)
        self.assertEqual(rows["kopri:greenland_ice_contours"]["projection"], "EPSG:3413")
        self.assertEqual(rows["kopri:historic"]["projection"], "EPSG:3031")

    def test_밖에_열면_내린다(self):
        with override_settings(PUBLIC=True):
            names = [l["name"] for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]]
            self.assertNotIn("kopri:rock_antarctica", names)
            self.assertEqual(self.client.get("/GSM/points/?layer=kopri:rock_antarctica").status_code, 404)

    def test_WMS_는_레이어명만_바꿔_넘긴다(self):
        sent = {}

        def fake(url, params=None, **kw):
            sent.update(params, url=url)
            return mock.Mock(content=b"\x89PNG", headers={"content-type": "image/png"})
        with mock.patch.object(kopri, "_get", fake), override_settings(TILE_CACHE_DIR=tempfile.mkdtemp()):
            r = self.client.get("/GSM/wms/", {"layers": "kopri:coast_change", "bbox": "0,0,1,1", "width": 256,
                                              "height": 256, "srs": "EPSG:3031", "request": "GetMap"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sent["layers"], "kpdc:antarctic_coastline_coast_change")
        self.assertTrue(sent["url"].endswith("/geoserver/kpdc/wms"))


class WmsProps(SimpleTestCase):
    """KPDC 지도 서버 속성 이름 (073) — 상류 열을 팝업 이름으로, 빈 값·편집자는 뺀다."""

    def test_해안선_변화(self):
        from viewer import kopri
        got = kopri._wms_props({"editor": "acook", "revdate": "19570101", "coast_type": 22011, "year": 1957,
                                "reliabilit": 1, "source_inf": None, "reference": 303},
                               kopri.WMS_PROPS["kopri:coast_change"])
        self.assertEqual(got, {"연도": 1957, "신뢰도": 1, "고친 날": "19570101"})

    def test_이름표가_없으면_그대로(self):
        from viewer import kopri
        self.assertEqual(kopri._wms_props({"fid": 1, "a": 2}, ()), {"a": 2})


class Arctic(SimpleTestCase):
    """KPDC 자료의 북극 — 스발바르·그린란드 탭에 주제마다 한 벌 (075)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.enterContext(override_settings(KOPRI_DIR=self.dir.name))
        atmo = ["EARTH SCIENCE > ATMOSPHERE > AEROSOLS"]
        kopri.save("kpdc", {"records": {
            # 다산기지 — 스발바르에만
            "ny": {"c": "KPDC", "title": "Aerosol at Dasan", "keywords": atmo,
                   "shapes": [["POINT", [(78.92, 11.93)]]]},
            # 남극과 스발바르 두 곳 — 스발바르 탭에는 스발바르의 것만 그린다
            "both": {"c": "KPDC", "title": "Both poles", "keywords": atmo,
                     "shapes": [["POINT", [(-62.22, -58.79)]], ["POINT", [(78.9, 11.9)]]]},
            # 축치해 항해 — 북극해 탭에만 (076)
            "chukchi": {"c": "KPDC", "title": "ARAON Chukchi", "keywords": atmo,
                        "shapes": [["POINT", [(73.0, -168.0)]]]},
            # 날짜변경선을 넘는 베링해 네모 — 3413 에서는 이어진 한 덩이다
            "bering": {"c": "KPDC", "title": "Bering box", "keywords": atmo,
                       "shapes": [["BOX", [(58.0, 175.0), (62.0, -175.0)]]]},
            # 그린란드 북부
            "nord": {"c": "KPDC", "title": "Sirius Passet", "keywords": ["EARTH SCIENCE > PALEOCLIMATE > X"],
                     "shapes": [["POINT", [(82.79, -42.23)]]]},
        }})

    def ids(self, name):
        return sorted(f["id"] for f in json.loads(kopri.file_body(name))["features"])

    def test_탭마다_제_범위만(self):
        self.assertEqual(self.ids("kopri:kpdc_atmo_svalbard"), ["both#0", "ny#0"])
        both = [f for f in json.loads(kopri.file_body("kopri:kpdc_atmo_svalbard"))["features"]
                if f["id"] == "both#0"][0]
        self.assertEqual(both["geometry"]["coordinates"], [11.9, 78.9])     # 남극의 점은 싣지 않는다
        self.assertEqual(self.ids("kopri:kpdc_atmo_greenland"), [])
        self.assertEqual(self.ids("kopri:kpdc_paleo_greenland"), ["nord#0"])

    def test_북극해는_두_탭을_뺀_북극(self):
        # 다산기지(스발바르)·그린란드는 제 탭에 있어 여기 없다. 남극의 점도 없다
        self.assertEqual(self.ids("kopri:kpdc_atmo_arctic_ocean"), ["bering#0", "chukchi#0"])
        self.assertEqual(self.ids("kopri:kpdc_paleo_arctic_ocean"), [])
        bering = [f for f in json.loads(kopri.file_body("kopri:kpdc_atmo_arctic_ocean"))["features"]
                  if f["id"] == "bering#0"][0]
        lons = {round(x) for x, _ in bering["geometry"]["coordinates"][0]}
        self.assertTrue(lons <= set(range(175, 181)) | set(range(-180, -174)), lons)

    def test_남극은_그대로(self):
        south = json.loads(kopri.file_body("kopri:kpdc_atmo"))["features"]
        self.assertEqual([f["geometry"]["coordinates"] for f in south], [[-58.79, -62.22]])

    def test_씨앗의_레이어는_코드가_안다(self):
        from django.conf import settings
        for path in settings.KOPRI_CATALOG_SEEDS:
            for row in json.loads(path.read_text(encoding="utf-8"))["레이어"]:
                self.assertTrue(kopri.knows(row["name"]) or kopri.knows_wms(row["name"]), row["name"])


ARAON_PAGE = """<div id="dashboard_show" style="position:relative;z-index:999; display:none;">
<td bgcolor="#00c0ee" class="data"><b>DATE &nbsp;:</b> Thu Oct 01<br><b>TIME &nbsp;:</b> 04:00 UTC<br><b>DELAY :</b> <font color='red'><b>04:59</b></font></td>
<td bgcolor="#01add7" class="head">TIME</td>
<td bgcolor="#0ca65a" class="data"><b>LAT :</b> -74.6241<br><b>LON :</b> 195.0348<br><br></td>
<td bgcolor="#f39c12" class="data"><b>SOG :</b> 12.6 kn<br><b>COG :</b> 218<br><b>HDG :</b> 218<br></td>
<td bgcolor="#f56954" class="data"><b>WIND :</b> 6553.5 m/s NNE<br><b>TEMP</b> : -20.9 ˚C<br><b>HUMI</b> : 64 %</td>
</div>
<script>var latlngs = [[35.7609,130.0348],[35.9382,130.1718]];</script>"""


class AraonTests(SimpleTestCase):
    """아라온호 위치 판 — 극지연구소 `live.kopri.re.kr/araon/`."""

    NOW = kopri.datetime(2026, 10, 1, 9, 0, tzinfo=kopri.timezone.utc)

    def test_parse(self):
        row = kopri.parse_araon(ARAON_PAGE, now=self.NOW)
        self.assertEqual(row, {"time": "2026-10-01T04:00Z", "lat": -74.6241, "lon": -164.9652,
                               "sog": 12.6, "cog": 218.0, "hdg": 218.0, "temp": -20.9, "humi": 64.0})

    def test_year_from_weekday(self):
        # 새해 첫날에 받은 지난해 12 월 31 일 — 2025-12-31 은 수요일이다
        page = ARAON_PAGE.replace("Thu Oct 01", "Wed Dec 31")
        row = kopri.parse_araon(page, now=kopri.datetime(2026, 1, 1, 2, 0, tzinfo=kopri.timezone.utc))
        self.assertEqual(row["time"], "2025-12-31T04:00Z")

    def test_no_dashboard(self):
        with self.assertRaises(kopri.KopriError):
            kopri.parse_araon("<html>점검 중</html>", now=self.NOW)

    def test_append_skips_same_time(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(KOPRI_DIR=tmp):
            row = kopri.parse_araon(ARAON_PAGE, now=self.NOW)
            self.assertTrue(kopri.append_araon(row))
            self.assertFalse(kopri.append_araon(dict(row, lat=0)))
            self.assertTrue(kopri.append_araon(dict(row, time="2026-10-01T05:00Z")))
            self.assertEqual([r["time"] for r in kopri.araon_track()], ["2026-10-01T04:00Z", "2026-10-01T05:00Z"])


class AraonTrackTests(SimpleTestCase):
    """아라온호 항적을 화면에 내는 것 (koprifossillab 006)."""

    def row(self, time, lat, lon, **extra):
        return dict({"time": time, "lat": lat, "lon": lon}, **extra)

    def test_dateline_split(self):
        rows = [self.row("2026-08-01T00:00Z", 70.0, 179.0), self.row("2026-08-01T01:00Z", 71.0, -179.0)]
        track, last = kopri.araon_features(rows, now=kopri.datetime(2026, 8, 1, 2, 0, tzinfo=kopri.timezone.utc))
        self.assertEqual(track["geometry"]["coordinates"],
                         [[[179.0, 70.0], [180.0, 70.5]], [[-180.0, 70.5], [-179.0, 71.0]]])
        self.assertEqual(last["geometry"]["coordinates"], [-179.0, 71.0])

    def test_long_gap_split(self):
        # 하루가 넘게 빈 사이는 잇지 않는다 — 두 날은 따로, 앞날의 끝에서 이어 시작하지도 않는다
        now = kopri.datetime(2026, 8, 2, 3, 0, tzinfo=kopri.timezone.utc)
        rows = [self.row("2026-08-01T00:00Z", 0.0, 0.0), self.row("2026-08-01T01:00Z", 0.0, 1.0),
                self.row("2026-08-02T01:00Z", 0.0, 5.0), self.row("2026-08-02T02:00Z", 0.0, 6.0)]
        older, newer, _ = kopri.araon_features(rows, now=now)
        self.assertEqual(older["geometry"]["coordinates"], [[[0.0, 0.0], [1.0, 0.0]]])
        self.assertEqual(newer["geometry"]["coordinates"], [[[5.0, 0.0], [6.0, 0.0]]])
        self.assertEqual((older["properties"]["fixes"], newer["properties"]["fixes"]), (2, 2))

    def test_days_join_and_ago(self):
        """하루 조각 (koprifossillab 017) — 이어진 날은 앞날의 끝에서 시작하고, 조각마다 며칠 전(가운데)이 붙는다."""
        now = kopri.datetime(2026, 8, 2, 23, 30, tzinfo=kopri.timezone.utc)   # 하루 경계는 08-01 23:30
        rows = [self.row("2026-08-01T22:00Z", 0.0, 0.0), self.row("2026-08-01T23:00Z", 0.0, 1.0),
                self.row("2026-08-02T00:00Z", 0.0, 2.0), self.row("2026-08-02T01:00Z", 0.0, 3.0)]
        older, newer, last = kopri.araon_features(rows, now=now)
        self.assertEqual(newer["geometry"]["coordinates"], [[[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]])
        self.assertEqual(older["properties"]["ago"], 1.04)
        self.assertEqual(newer["properties"]["ago"], 0.98)
        self.assertEqual(last["properties"]["ago"], 0)

    def test_past_ago_counts_from_now(self):
        """시각 없는 지난 항적의 며칠 전은 받은 때가 아니라 지금에서 센다 — 받은 뒤로 흐른 날을 더한다."""
        past = {"harvested": "2026-10-01T09:43Z", "nday": 365, "points": [[0, 0, 3], [0.1, 0, 3]]}
        now = kopri.datetime(2026, 10, 11, 9, 43, tzinfo=kopri.timezone.utc)
        (feature,) = kopri.araon_features([], past, now=now)
        self.assertEqual(feature["properties"]["ago"], 12.5)

    def test_single_fix_is_point_only(self):
        features = kopri.araon_features([self.row("2026-10-01T04:00Z", 35.76, 130.03, sog=12.6)])
        self.assertEqual([f["properties"]["code"] for f in features], ["last"])
        self.assertEqual(features[0]["properties"]["sog"], 12.6)

    def test_file_body(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(KOPRI_DIR=tmp):
            with self.assertRaises(FileNotFoundError):
                kopri.file_body("kopri:araon_antarctica")
            kopri.append_araon(self.row("2026-10-01T04:00Z", -74.6, 164.2))
            kopri.append_araon(self.row("2026-10-01T05:00Z", -74.7, 164.3))
            body = json.loads(kopri.file_body("kopri:araon_arctic_ocean"))
        self.assertEqual(body["style"], "class")
        self.assertEqual([r["code"] for r in body["legend"]], ["last", "track"])
        self.assertEqual(body["labels"]["sog"], "속력 (kn)")


class AraonViewTests(TestCase):
    def test_points_short_cache(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(KOPRI_DIR=tmp, PUBLIC=False):
            kopri.append_araon({"time": "2026-10-01T04:00Z", "lat": -74.6, "lon": 164.2})
            r = self.client.get("/GSM/points/", {"layer": "kopri:araon"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], f"public, max-age={kopri.ARAON_MAX_AGE}")

    def test_public_closes(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(KOPRI_DIR=tmp, PUBLIC=True):
            kopri.append_araon({"time": "2026-10-01T04:00Z", "lat": -74.6, "lon": 164.2})
            self.assertEqual(self.client.get("/GSM/points/", {"layer": "kopri:araon"}).status_code, 404)
            page = self.client.get("/GSM/earth/").content.decode()
        self.assertIn('"araon": false', page)


class AraonPastTests(SimpleTestCase):
    """날짜를 하루 단위로 붙인 지난 항적 (koprifossillab 009)."""

    def test_latlngs_and_lon_fold(self):
        page = "<script>var latlngs = [[77.7,192.33],[35.76,130.03]];\nvar polyline = 1;</script>"
        pairs = kopri._latlngs(page)
        self.assertEqual([kopri._lonlat(p) for p in pairs], [[-167.67, 77.7], [130.03, 35.76]])

    def test_counted_prefix_and_shift(self):
        base = [[3, 3], [2, 2], [1, 1]]
        self.assertEqual(kopri._counted(base, [[3, 3], [2, 2]]), 2)
        self.assertEqual(kopri._counted(base, [[4, 4], [3, 3], [2, 2]]), 2)     # 받는 사이에 새 자리가 붙었다
        self.assertEqual(kopri._counted(base, []), 0)
        with self.assertRaises(kopri.KopriError):
            kopri._counted(base, [[3, 3], [9, 9]])

    def test_fetch_assigns_days(self):
        # 새것부터 다섯 자리 — 1 일 창에 둘, 2 일 창에 넷(하나 더해 셋째·넷째), 3 일 창에 다섯
        base = [[5, 5], [4, 4], [3, 3], [2, 2], [1, 1]]
        sizes = {3: 5, 1: 2, 2: 4}

        def page(nday, nhour):
            pairs = base[:sizes[nday]]
            return ('<div id="dashboard_show"><b>DATE :</b> Thu Oct 01<br><b>TIME :</b> 04:00 UTC<br>'
                    '<b>LAT :</b> 5<br><b>LON :</b> 5<br></div><script>var latlngs = '
                    + json.dumps(pairs) + ";</script>")
        with mock.patch.object(kopri, "_araon_page", side_effect=page):
            data = kopri.fetch_araon_past(3, pause=0)
        self.assertEqual(data["counts"], [2, 4, 5])
        self.assertEqual([p[2] for p in data["points"]], [3, 2, 2, 1, 1])     # 오래된 것부터

    def test_days_join_and_window(self):
        past = {"harvested": "2026-10-01T09:43Z",
                "points": [[0, 0, 3], [0.1, 0, 3], [0.2, 0, 2], [0.3, 0, 2], [5, 0, 2], [5.1, 0, 2]]}
        days = kopri._araon_past_days(past)
        self.assertEqual([(ago, n) for ago, _, n in days], [(3, 2), (2, 4)])
        # 2 일 전은 앞날의 마지막 자리에서 이어 시작하고, 500 km 넘게 뛴 곳에서 끊긴다
        self.assertEqual(days[1][1], [[[0.1, 0], [0.2, 0], [0.3, 0]], [[5, 0], [5.1, 0]]])
        self.assertEqual(kopri._day_window("2026-10-01T09:43Z", 1), "2026-09-30 09:43Z ~ 2026-10-01 09:43Z")
        features = kopri.araon_features([], past)
        self.assertEqual([f["properties"]["code"] for f in features], ["past", "past"])
