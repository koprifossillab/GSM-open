"""5만 지질도의 자세 기호 — 받아 둔 파일에서 자리와 값을 읽는다 (jikhanjung 004)."""
import gzip
import json
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from viewer import kigam50k


def _write(folder: Path, kind: str, features):
    folder.mkdir(parents=True, exist_ok=True)
    with gzip.open(folder / f"{kind}.geojson.gz", "wt", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)


def _pt(lon, lat, **props):
    return {"type": "Feature", "geometry": {"type": "MultiPoint", "coordinates": [[lon, lat]]},
            "properties": props}


class Kigam50k(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.override = override_settings(KIGAM50K_DIR=str(self.root))
        self.override.enable()
        kigam50k._cache.update(folder=None, rows=None)

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()
        kigam50k._cache.update(folder=None, rows=None)

    def test_파일이_없으면_빈_것이고_뷰어는_돈다(self):
        self.assertFalse(kigam50k.available())
        r = self.client.get("/GSM/kigam50k/attitudes/", {"bbox": "128,36,129,37"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["points"], [])

    def test_가장_새_날짜_폴더를_읽는다(self):
        _write(self.root / "raw" / "20260101", "bedding", [_pt(128.5, 36.5, roangle=10, dipangle=5)])
        _write(self.root / "raw" / "20260930", "bedding", [_pt(128.5, 36.5, roangle=258, dipangle=20)])
        rows, cut = kigam50k.within(128, 36, 129, 37)
        self.assertEqual([r["dipdir"] for r in rows], [258])
        self.assertFalse(cut)
        self.assertEqual(kigam50k.fetched_on(), "2026-09-30")

    def test_값을_읽는_법(self):
        _write(self.root / "raw" / "20260930", "bedding", [
            _pt(128.5, 36.5, type="층리", roangle=258, dipangle=20, strike="NW", dip="SW",
                mapname="천지", mapidx="HF32"),
            _pt(128.6, 36.6, type="층리", roangle=370, dipangle=-99),      # 경사 미상, 각은 한 바퀴 넘게
            {"type": "Feature", "geometry": None, "properties": {"roangle": 1}},   # 좌표 없음
        ])
        _write(self.root / "raw" / "20260930", "joint", [_pt(128.7, 36.7, type="수직절리", roangle=90, dipangle=90)])
        rows, _ = kigam50k.within(128, 36, 129, 37)
        self.assertEqual(len(rows), 3)
        first = rows[0]
        self.assertEqual((first["kind"], first["dipdir"], first["dip"], first["quad"], first["sheet"]),
                         ("bedding", 258, 20, "NW/SW", "천지"))
        self.assertEqual(kigam50k.strike_of(first["dipdir"]), 168)
        self.assertEqual((rows[1]["dipdir"], rows[1]["dip"]), (10, None))
        self.assertEqual(rows[2]["kind"], "joint")

    def test_범위_밖은_주지_않고_많으면_자른다(self):
        _write(self.root / "raw" / "20260930", "foliation",
               [_pt(128.0 + i / 1000, 36.5, roangle=1, dipangle=1) for i in range(10)] + [_pt(130, 36.5)])
        rows, cut = kigam50k.within(127.9, 36, 128.2, 37, limit=4)
        self.assertEqual(len(rows), 4)
        self.assertTrue(cut)
        r = self.client.get("/GSM/kigam50k/attitudes/", {"bbox": "129.5,36,130.5,37"})
        self.assertEqual(len(r.json()["points"]), 1)

    def test_bbox_가_없으면_400(self):
        self.assertEqual(self.client.get("/GSM/kigam50k/attitudes/").status_code, 400)

    def test_자료가_있으면_상류의_자세_칸을_팝업에서_뺀다(self):
        from viewer import views
        fid = "l_50k_geology_bedding_latest.511"
        self.assertFalse(views._is_noise(fid))          # 자료가 없으면 상류 것을 그대로 둔다
        self.assertFalse(views._is_noise("l_50k_geology_litho_latest.1"))
        _write(self.root / "raw" / "20260930", "bedding", [_pt(128.5, 36.5, roangle=1, dipangle=1)])
        self.assertTrue(views._is_noise(fid))
        self.assertFalse(views._is_noise("l_50k_geology_litho_latest.1"))
        self.assertTrue(views._is_noise("admin_boundary_SGG_201907_NGII.267"))


class Rose(TestCase):
    """도폭 하나·고른 범위의 장미도 (wetherilli 197, jikhanjung P01 §5)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.override = override_settings(KIGAM50K_DIR=str(self.root))
        self.override.enable()
        kigam50k._cache.update(folder=None, rows=None)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.override.disable)
        self.addCleanup(kigam50k._cache.update, folder=None, rows=None)
        day = self.root / "raw" / "20260930"
        _write(day, "bedding", [
            _pt(127.30, 36.30, roangle=100, dipangle=30, mapname="대전", mapidx="GF11"),   # 주향 10°
            _pt(127.31, 36.31, roangle=280, dipangle=35, mapname="대전", mapidx="GF11"),   # 주향 190° → 축으로 10°
            _pt(127.32, 36.32, roangle=95, dipangle=-99, mapname="대전", mapidx="GF11"),   # 경사 미상
            _pt(127.60, 36.60, roangle=0, dipangle=80, mapname="옥천", mapidx="GF12"),
        ])
        _write(day, "joint", [_pt(127.33, 36.33, roangle=45, dipangle=89, mapname="대전", mapidx="GF11")])

    def test_칸으로_센다(self):
        data = kigam50k.rose(kigam50k.in_sheet("GF11"))
        self.assertEqual(data["n"], {"bedding": 3, "joint": 1})
        self.assertEqual(data["strike"]["bedding"][1], 2)          # 10–20° 칸에 주향 10° 둘(190° 는 축이라 10°)
        self.assertEqual(data["strike"]["bedding"][0], 1)          # 주향 5°
        self.assertEqual(data["dipdir"]["bedding"][10], 1)          # 100°
        self.assertEqual(data["dipdir"]["bedding"][28], 1)          # 280°
        self.assertEqual(data["dip"]["bedding"][3], 2)              # 30·35°
        self.assertEqual(data["nodip"]["bedding"], 1)
        self.assertEqual(data["dip"]["joint"][8], 1)                # 89° 는 마지막 칸

    def test_누른_자리의_도폭(self):
        r = self.client.get("/GSM/kigam50k/rose/", {"lat": 36.305, "lon": 127.305})
        data = r.json()
        self.assertEqual(data["sheet"], {"no": "GF11", "name": "대전"})
        self.assertEqual(data["n"]["bedding"], 3)
        self.assertEqual(data["fetched"], "2026-09-30")

    def test_고른_범위(self):
        data = self.client.get("/GSM/kigam50k/rose/", {"bbox": "127.5,36.5,127.7,36.7"}).json()
        self.assertIsNone(data["sheet"])
        self.assertEqual(data["n"], {"bedding": 1})

    def test_기호가_먼_자리는_빈_것(self):
        data = self.client.get("/GSM/kigam50k/rose/", {"lat": 35.0, "lon": 129.0}).json()
        self.assertEqual((data["sheet"], data["n"]), (None, {}))

    def test_파일이_없으면_503(self):
        kigam50k._cache.update(folder=None, rows=None)
        with override_settings(KIGAM50K_DIR=tempfile.mkdtemp()):
            self.assertEqual(self.client.get("/GSM/kigam50k/rose/", {"lat": 36.3, "lon": 127.3}).status_code, 503)


class FetchCommand(TestCase):
    """`fetch_kigam50k` (jikhanjung P01 §4, wetherilli 199) — 상류는 바꿔 끼운다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.override = override_settings(KIGAM50K_DIR=str(self.root))
        self.override.enable()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.override.disable)
        self.counts = {name: 1 for name in kigam50k.FETCH}
        self.version = "a"

    def body(self, name):
        return json.dumps({"type": "FeatureCollection", "v": self.version,
                           "features": [_pt(127.0, 36.0, mapidx="GF11", mapname="대전")] * self.counts[name]}).encode()

    def run_at(self, day):
        from unittest import mock
        from django.core.management import call_command
        from django.utils import timezone
        import datetime
        when = timezone.make_aware(datetime.datetime.fromisoformat(day + "T09:00:00"))
        with mock.patch("viewer.kigam.wfs_count", side_effect=lambda n: 1), \
                mock.patch("viewer.kigam.wfs_features", side_effect=lambda n: (self.body(n), f"https://x/wfs?{n}")), \
                mock.patch("viewer.management.commands.fetch_kigam50k.timezone.localtime", return_value=when), \
                mock.patch("viewer.management.commands.fetch_kigam50k.time.sleep"):
            call_command("fetch_kigam50k", stdout=open("/dev/null", "w"))

    def days(self):
        return sorted(p.name for p in (self.root / "raw").iterdir())

    def test_받아_적고_같으면_새_폴더를_만들지_않는다(self):
        self.run_at("2026-11-02")
        self.assertEqual(self.days(), ["20261102"])
        manifest = json.loads((self.root / "raw/20261102/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["layers"]), set(kigam50k.FETCH))
        self.assertEqual(manifest["layers"]["frame"]["received"], 1)
        with gzip.open(self.root / "raw/20261102/frame.geojson.gz", "rt", encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["v"], "a")
        self.run_at("2026-12-07")
        self.assertEqual(self.days(), ["20261102"])
        manifest = json.loads((self.root / "raw/20261102/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["checked"]), 1)

    def test_바뀌면_새_폴더_옛것은_남긴다(self):
        self.run_at("2026-11-02")
        self.version = "b"
        self.run_at("2026-12-07")
        self.assertEqual(self.days(), ["20261102", "20261207"])
        self.assertEqual(kigam50k.latest().name, "20261207")

    def test_받은_수가_모자라면_아무것도_적지_않는다(self):
        from django.core.management.base import CommandError
        self.counts["fault"] = 0
        with self.assertRaises(CommandError):
            self.run_at("2026-11-02")
        self.assertFalse((self.root / "raw").exists() and self.days())


class WfsDoor(TestCase):
    @override_settings(KIGAM_KEY="SECRET")
    def test_센_수를_읽고_키는_싣지_않는다(self):
        from unittest import mock
        from viewer import kigam
        xml = b'<wfs:FeatureCollection numberMatched="196" numberReturned="0" xmlns:wfs="x"/>'
        resp = mock.Mock(status_code=200, content=xml, url="https://data.kigam.re.kr/mgeo/geoserver/wfs?x")
        with mock.patch("viewer.kigam.requests.get", return_value=resp) as get:
            self.assertEqual(kigam.wfs_count("fossil"), 196)
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/mgeo/geoserver/wfs"))
        self.assertEqual(params["typeNames"], "Geology_map:l_50k_geology_fossil_latest")
        self.assertNotIn("key", params)


def _poly(w, s, e, n, **props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[w, s], [e, s], [e, n], [w, n], [w, s]]]]}}


class Layers(TestCase):
    """화석산지·시료·광산·도폭 틀 레이어 (wetherilli 199, jikhanjung P01 §5 의 3·4 단계)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.override = override_settings(KIGAM50K_DIR=str(self.root), TILE_CACHE_SECONDS=0)
        self.override.enable()
        kigam50k._cache.update(folder=None, rows=None)
        kigam50k._frame_cache.update(folder=None, rows=None)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.override.disable)
        self.day = self.root / "raw" / "20260930"
        _write(self.day, "fossil", [_pt(129.4, 35.8, type="유공충", comt="채집지", mapname="감포", mapidx="IE14"),
                                    _pt(129.0, 36.0, type="화석산지", comt=None, mapname="대율", mapidx="HF20")])
        _write(self.day, "frame", [
            _poly(127.25, 36.25, 127.5, 36.5, mapidx="GF12", mapname="유성", surveyor="홍길동", suryear="1979",
                  doi="https://doi.org/10.22747/data.1"),
            _poly(127.0, 36.25, 127.25, 36.5, mapidx="GF11", mapname="대전", doi="javascript:alert(1)"),
        ])
        # 유성 틀 안이지만 가장 가까운 기호는 대전 도폭의 것
        _write(self.day, "bedding", [_pt(127.26, 36.30, roangle=90, dipangle=20, mapname="대전", mapidx="GF11"),
                                     _pt(127.45, 36.45, roangle=180, dipangle=30, mapname="유성", mapidx="GF12")])

    def read(self, name):
        return json.loads(kigam50k.layer_body(name))

    def test_화석산지는_갈래의_색으로(self):
        data = self.read("kigam50k:fossil")
        self.assertEqual([f["properties"]["code"] for f in data["features"]], ["foram", "fossil"])
        self.assertEqual(data["features"][0]["geometry"], {"type": "Point", "coordinates": [129.4, 35.8]})
        self.assertEqual(data["features"][0]["properties"]["mapname"], "감포")
        self.assertNotIn("comt", data["features"][1]["properties"])
        self.assertEqual([l["code"] for l in data["legend"]], ["foram", "fossil"])

    def test_도폭_틀은_DOI_링크만_http(self):
        data = self.read("kigam50k:frame")
        first, second = (f["properties"] for f in data["features"])
        self.assertEqual((first["surveyor"], first["suryear"], first["doi"]), ("홍길동", "1979", "https://doi.org/10.22747/data.1"))
        self.assertNotIn("doi", second)
        self.assertEqual(data["links"], ["doi"])
        self.assertEqual(data["features"][0]["geometry"]["type"], "MultiPolygon")

    def test_점_레이어_길과_파일이_없을_때(self):
        r = self.client.get("/GSM/points/", {"layer": "kigam50k:fossil"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["features"]), 2)
        r = self.client.get("/GSM/points/", {"layer": "kigam50k:mine"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_kigam50k", r.json()["error"])

    def test_장미도의_도폭은_틀로_고른다(self):
        self.assertEqual(kigam50k.sheet_at(127.27, 36.30), ("GF12", "유성"))      # 가장 가까운 기호는 대전이다
        data = self.client.get("/GSM/kigam50k/rose/", {"lat": 36.30, "lon": 127.27}).json()
        self.assertEqual(data["sheet"]["no"], "GF12")
        self.assertEqual(data["n"], {"bedding": 1})

    def test_카탈로그에_선다(self):
        from django.core.management import call_command
        from viewer import views
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: (g, l) for g in views._catalog("ko") for l in g["layers"]}
        group, layer = rows["kigam50k:frame"]
        self.assertEqual((group["region"], group["name"]), ("korea", "지질 구조 (5만)"))
        self.assertEqual((layer["kind"], layer["style"], layer["upstream"]), ("points", "class", "kigam50k"))
        self.assertIn("CC BY-NC", layer["sourceLabel"])


def _line(*pts, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "MultiLineString", "coordinates": [list(pts)]}}


class LinesAndZones(TestCase):
    """단층·습곡·광종·변질대·변성대 (wetherilli 202)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.override = override_settings(KIGAM50K_DIR=str(self.root), TILE_CACHE_SECONDS=0)
        self.override.enable()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.override.disable)
        day = self.root / "raw" / "20260930"
        _write(day, "fault", [
            _line([128.0, 36.0], [128.1234567, 36.1], type="추정단층", dipangle=0, dipazi=None, mapidx="HE01"),
            _line([128.2, 36.0], [128.3, 36.1], type="드러스트", dipangle=40, dipazi=135, fault_kr="양산단층"),
            _line([128.4, 36.0], [128.5, 36.1], type="소단층", dipangle=80),
        ])
        _write(day, "fold", [_line([127.0, 37.0], [127.1, 37.1], type="배사")])
        _write(day, "oretype", [_pt(129.0, 36.0, type="금", **{"광종": "Au"}), _pt(129.1, 36.1, type="형석")])
        _write(day, "alterationzone", [_poly(127.0, 36.0, 127.1, 36.1, type="열수광화대", lithoname="마동층", age="백악기")])
        _write(day, "metamorphismzone", [_poly(127.2, 36.0, 127.3, 36.1, type="접촉변성대")])

    def read(self, name):
        return json.loads(kigam50k.layer_body(name))

    def test_단층은_갈래마다_굵기와_끊김(self):
        data = self.read("kigam50k:fault")
        codes = [f["properties"]["code"] for f in data["features"]]
        self.assertEqual(codes, ["fault_q", "thrust", "fault"])          # 소단층은 단층 칸
        legend = {l["code"]: l for l in data["legend"]}
        self.assertEqual(legend["fault_q"]["dash"], [5, 4])
        self.assertEqual((legend["thrust"]["shape"], legend["thrust"]["width"]), ("stroke", 1.8))
        first, second = data["features"][0]["properties"], data["features"][1]["properties"]
        self.assertNotIn("dipangle", first)                               # 0 은 적지 않은 것
        self.assertEqual((second["dipangle"], second["dipazi"], second["fault_kr"]), ("40", "135", "양산단층"))
        self.assertEqual(data["features"][0]["geometry"]["coordinates"][0][1], [128.12346, 36.1])   # 소수 다섯 자리

    def test_변질대와_변성대는_한_레이어(self):
        data = self.read("kigam50k:zones")
        self.assertEqual([f["properties"]["code"] for f in data["features"]], ["hydrothermal", "contact_meta"])
        self.assertEqual(data["features"][0]["properties"]["lithoname"], "마동층")

    def test_광종과_습곡(self):
        self.assertEqual([f["properties"]["code"] for f in self.read("kigam50k:oretype")["features"]], ["precious", "other"])
        self.assertEqual(self.read("kigam50k:fold")["legend"][0]["code"], "anticline")

    def test_단층은_한_장으로_굽는다(self):
        from django.core.management import call_command
        from viewer import views
        call_command("seed_catalog", stdout=open("/dev/null", "w"))
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        self.assertEqual(rows["kigam50k:fault"]["render"], "image")
        self.assertNotIn("render", rows["kigam50k:oretype"])


class Attitudes(TestCase):
    """선구조·신장광물·습곡축·유동구조 — 방향 기호가 드는 점 (wetherilli 223). 값은 2026-09-30 에 받은 파일의 꼴 그대로다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(KIGAM50K_DIR=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.override.disable)
        kigam50k._body_cache.clear()
        self.addCleanup(kigam50k._body_cache.clear)
        day = Path(self.tmp.name) / "raw" / "20260930"
        _write(day, "lineation", [_pt(127.0, 36.0, type="2차선구조", roangle=135, tangle=30, mapname="청산", mapidx="GF32"),
                                  _pt(127.1, 36.1, type="파랑선", roangle=-135, tangle=-99, trend="NE", mapname="x", mapidx="y")])
        _write(day, "mineralarray", [_pt(126.9, 35.9, type="신장광물", roangle=-30, tangle=51, trend="NE", plunge="NW",
                                         comt="신장선구조의 방향과 경사", mapname="이리", mapidx="FE35"),
                                     _pt(126.8, 35.8, type="경사미상 신장광물", roangle=40, tangle=0, mapname="이리", mapidx="FE35")])
        _write(day, "foldaxis", [_pt(127.5, 37.7, type="소습곡축", roangle=53, tangle=30, mapname="청평", mapidx="GG14")])
        _write(day, "flowstructure", [_pt(126.5, 35.3, type="유동구조", roangle=86, dipangle=40, strike="NE", dip="SE",
                                          comt="유리의 주향과 경사", mapname="영광", mapidx="FE21")])

    def read(self, name):
        return json.loads(kigam50k.layer_body(name))

    def test_선구조는_침강_방향으로_돌린다(self):
        data = self.read("kigam50k:lineation")
        first, second = (f["properties"] for f in data["features"])
        self.assertEqual((first["code"], first["azimuth"], first["tangle"]), ("l2", 135, "30"))
        self.assertEqual((second["code"], second["azimuth"], second["roangle"]), ("other", 225, "225"))   # -135 → 225
        self.assertNotIn("tangle", second)                                                           # -99 는 미상
        self.assertEqual({l["shape"] for l in data["legend"]}, {"arrow"})

    def test_신장광물은_엽리의_주향에서_90도(self):
        first, second = (f["properties"] for f in self.read("kigam50k:mineralarray")["features"])
        self.assertEqual((first["azimuth"], first["plunge"]), (60, "NW"))       # -30 + 90 — 화살이 침강 방향을 가리킨다
        self.assertNotIn("tangle", second)                                       # "경사미상" 의 0 은 미상
        self.assertEqual(second["code"], "stretch_q")

    def test_습곡축과_유동구조(self):
        self.assertEqual(self.read("kigam50k:foldaxis")["features"][0]["properties"]["azimuth"], 53)
        data = self.read("kigam50k:flowstructure")
        props = data["features"][0]["properties"]
        self.assertEqual((props["azimuth"], props["dipangle"], props["code"]), (86, "40", "flow"))   # 경사 방향 그대로
        self.assertEqual(data["legend"][0]["shape"], "strike")
        self.assertEqual(data["labels"]["roangle"], "경사 방향")
