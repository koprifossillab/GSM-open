"""뷰의 남은 빈 곳 (wetherilli 368) — 349 다음 차례. coverage 로 찾았다.

범례 길(캐시 적중·키가 없을 때·상류가 못 줄 때 옛것·자료를 파는 상류), 3D 의 편 타일(자료가 없을 때·펴지 못할 때),
퀘벡 보는 범위 범례, 화성 표고·범례, 세계 암상 타일. 상류는 부르지 않는다 — 문·파일 함수를 갈아 끼운다.
타일 캐시는 시험마다 빈 임시 디렉터리다(`gsmweb.testrunner`, wetherilli 354).
"""
import json
import os
import time
from unittest import mock

from django.test import SimpleTestCase, override_settings

from viewer import admap, cgs, glim, i18n, ibcso, kigam, sigeom, tilecache, trek, views, warp

PNG = b"\x89PNG-new"
OLD = b"\x89PNG-old"


def age(key, suffix=".png", days=4000):
    """담아 둔 것을 늙힌다 — 다시 묻게"""
    past = time.time() - days * 86400
    os.utime(tilecache._path(key, suffix), (past, past))


class Legend(SimpleTestCase):
    """`/GSM/legend/` — 범례 그림도 타일처럼 담고, 상류가 못 주면 옛것"""

    def key(self, layer):
        return tilecache.key_for("legend", {"layer": layer})

    def get(self, layer="L_250K_Geology_Map", upstream="kigam"):
        with mock.patch.object(views, "_upstream_of", return_value=upstream):
            return self.client.get("/GSM/legend/", {"layer": layer} if layer else {})

    def test_레이어가_없으면_400(self):
        self.assertEqual(self.get(layer="").status_code, 400)

    def test_담아_둔_것은_상류에_묻지_않는다(self):
        tilecache.put(self.key("L_250K_Geology_Map"), OLD)
        with mock.patch.object(kigam, "get_legend") as get:
            r = self.get()
        get.assert_not_called()
        self.assertEqual((r.content, r["X-GSM-Cache"]), (OLD, "hit"))

    @override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=False)
    def test_키가_없고_담은_것도_없으면_503(self):
        with mock.patch.object(kigam, "get_legend") as get:
            r = self.get()
        get.assert_not_called()
        self.assertEqual(r.status_code, 503)

    @override_settings(KIGAM_KEY="k", DEV_DIRECT_WMS=False)
    def test_상류가_못_주면_옛것을_한_시간만(self):
        tilecache.put(self.key("L_250K_Geology_Map"), OLD)
        age(self.key("L_250K_Geology_Map"))
        with mock.patch.object(kigam, "get_legend", side_effect=kigam.UpstreamError("down")):
            r = self.get()
        self.assertEqual((r.content, r["X-GSM-Cache"], r["Cache-Control"]), (OLD, "stale", "public, max-age=3600"))

    @override_settings(KIGAM_KEY="k", DEV_DIRECT_WMS=False)
    def test_옛것도_없으면_502(self):
        with mock.patch.object(kigam, "get_legend", side_effect=kigam.UpstreamError("down")):
            self.assertEqual(self.get().status_code, 502)

    @override_settings(KIGAM_KEY="k", DEV_DIRECT_WMS=False)
    def test_받은_것은_담는다(self):
        with mock.patch.object(kigam, "get_legend", return_value=(PNG, "image/png")):
            r = self.get()
        self.assertEqual(r.content, PNG)
        self.assertEqual(tilecache.get(self.key("L_250K_Geology_Map")), PNG)

    def test_자료를_파는_상류는_담지_않는다(self):
        with mock.patch.object(cgs, "get_legend", return_value=(PNG, "image/png")):
            r = self.get("cgs:geology", upstream="cgs")
        self.assertEqual(r.content, PNG)
        self.assertIsNone(tilecache.get(self.key("cgs:geology")))


class Warp(SimpleTestCase):
    """3D 의 편 타일 — 자료가 없으면 안내 타일(브라우저가 들지 않게), 펴지 못하면 안내 타일"""
    SOUTH = "3/4/7"            # 줌 3 의 맨 아래 줄 — 남위 60° 남쪽

    def test_자력_이상_자료가_없으면_안내(self):
        with mock.patch.object(admap, "available", return_value=False):
            r = self.client.get(f"/GSM/warp/admap/anomaly/{self.SOUTH}.png")
        self.assertEqual((r.status_code, r["Cache-Control"]), (200, "no-store"))

    def test_자료_출처_자료가_없으면_안내(self):
        with mock.patch.object(ibcso, "tid_available", return_value=False):
            r = self.client.get(f"/GSM/warp/ibcso/tid/{self.SOUTH}.png")
        self.assertEqual(r["Cache-Control"], "no-store")
        r = self.client.get("/GSM/warp/ibcso/tid/3/4/1.png")         # 북쪽 — 빈 타일
        self.assertNotEqual(r["Cache-Control"], "no-store")

    def test_펴지_못하면_안내하고_담지_않는다(self):
        with mock.patch.object(admap, "available", return_value=True), \
             mock.patch.object(warp, "render", side_effect=OSError("broken")):
            r = self.client.get(f"/GSM/warp/admap/anomaly/{self.SOUTH}.png")
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertEqual(tilecache.stats()["count"], 0)

    def test_모르는_것과_범위_밖은_404(self):
        self.assertEqual(self.client.get("/GSM/warp/ibcso/nothing/5/1/1.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/warp/admap/anomaly/1/0/0.png").status_code, 404)      # 줌 2 아래


class QuebecLegend(SimpleTestCase):
    URL = "/GSM/sigeom/legend/"
    ROWS = [{"lithology": f"unit {n}", "color": "#ccc"} for n in range(sigeom.MAX_LEGEND + 5)]

    def test_변수가_틀리면(self):
        self.assertEqual(self.client.get(self.URL, {"layer": "sigeom:none", "bbox": "0,0,1,1"}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"layer": "sigeom:generale", "bbox": "0,0,1"}).status_code, 400)
        r = self.client.get(self.URL, {"layer": "sigeom:regionale", "bbox": "-74,45,-70,47"})        # 넓이 2° 를 넘는다
        self.assertEqual(r.status_code, 422)

    def test_한_번_세어_담고_칸_수를_자른다(self):
        q = {"layer": "sigeom:generale", "bbox": "-72.001,46.004,-71,47"}
        with mock.patch.object(sigeom, "extent_legend", return_value=self.ROWS) as count:
            first = self.client.get(self.URL, q).json()
            second = self.client.get(self.URL, dict(q, bbox="-72.004,46.001,-71,47")).json()    # 0.01° 로 맞추면 같은 열쇠
        self.assertEqual(count.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual((len(first["rows"]), first["more"]), (sigeom.MAX_LEGEND, 5))

    def test_상류가_못_주면_502(self):
        with mock.patch.object(sigeom, "extent_legend", side_effect=sigeom.SigeomError("down")):
            r = self.client.get(self.URL, {"layer": "sigeom:generale", "bbox": "-72,46,-71,47"})
        self.assertEqual((r.status_code, r.json()["rows"]), (502, []))


class MarsDem(SimpleTestCase):
    URL = "/GSM/mars/dem/3/2/2.png"

    def test_받아_담고_다음엔_꺼낸다(self):
        with mock.patch.object(trek, "mars_dem_tile", return_value=PNG) as get:
            first = self.client.get(self.URL)
            second = self.client.get(self.URL)
        self.assertEqual(get.call_count, 1)
        self.assertEqual((first["X-GSM-Cache"], second["X-GSM-Cache"]), ("miss", "hit"))

    def test_못_받으면_옛것_없으면_502(self):
        with mock.patch.object(trek, "mars_dem_tile", side_effect=trek.TrekError("down")):
            self.assertEqual(self.client.get(self.URL).status_code, 502)
        key = views.mars_dem_key(3, 2, 2)
        tilecache.put(key, OLD)
        age(key)
        with mock.patch.object(trek, "mars_dem_tile", side_effect=trek.TrekError("down")):
            r = self.client.get(self.URL)
        self.assertEqual(r.content, OLD)

    def test_줌_밖은_404(self):
        self.assertEqual(self.client.get(f"/GSM/mars/dem/{trek.MARS_DEM_MAX_ZOOM + 3}/0/0.png").status_code, 404)


class MarsLegend(SimpleTestCase):
    ITEMS = [{"name": "Early Noachian highland", "age": "Noachian", "color": "#a33"}]

    def test_시대만_한국어판에서_옮기고_담는다(self):
        with mock.patch.object(trek, "mars_legend", return_value=self.ITEMS) as get:
            ko = self.client.get("/GSM/mars/legend/").json()["items"]
            self.client.cookies[i18n.COOKIE] = "en"
            en = self.client.get("/GSM/mars/legend/").json()["items"]
        self.assertEqual(get.call_count, 1)
        self.assertEqual(ko[0]["age"], "노아키스기")
        self.assertEqual(ko[0]["name"], "Early Noachian highland")         # 이름은 상류 그대로
        self.assertEqual(en[0]["age"], "Noachian")                          # 영어판은 상류의 이름 그대로

    def test_못_받으면_502(self):
        with mock.patch.object(trek, "mars_legend", side_effect=trek.TrekError("down")):
            r = self.client.get("/GSM/mars/legend/")
        self.assertEqual((r.status_code, r.json()["items"]), (502, []))


class Glim(SimpleTestCase):
    def test_격자가_없으면_안내_타일(self):
        with mock.patch.object(glim, "grid", return_value=None):
            r = self.client.get("/GSM/earth/glim/tiles/0/0/0.png")
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertEqual(self.client.get("/GSM/earth/glim/tiles/0/5/5.png").status_code, 404)

    def test_그려_담고_다음엔_꺼낸다(self):
        with mock.patch.object(glim, "grid", return_value=object()), mock.patch.object(views, "glim_version", return_value="v1"), \
             mock.patch.object(glim, "render_tile", return_value=PNG) as render:
            first = self.client.get("/GSM/earth/glim/tiles/1/1/0.png")
            second = self.client.get("/GSM/earth/glim/tiles/1/1/0.png")
        self.assertEqual(render.call_count, 1)
        self.assertEqual((first["X-GSM-Cache"], second["X-GSM-Cache"]), ("miss", "hit"))

    def test_누른_자리(self):
        self.assertEqual(self.client.get("/GSM/earth/glim/at/", {"lat": "x"}).status_code, 400)
        with mock.patch.object(glim, "at", return_value=None):
            got = self.client.get("/GSM/earth/glim/at/", {"lat": "10", "lon": "20"}).json()
        self.assertIsNone(got["code"])
        with mock.patch.object(glim, "at", return_value=3), mock.patch.object(glim, "name", return_value="화산암"):
            got = self.client.get("/GSM/earth/glim/at/", {"lat": "10", "lon": "20"}).json()
        self.assertEqual(got["code"], 3)
        self.assertIn("화산암", got["text"])


class PlanetTiles(SimpleTestCase):
    """달 극 지질도·Trek 판 타일 — 상류가 못 주면 옛것, 옛것도 없으면 안내 타일(브라우저가 들지 않게)"""

    def check(self, url, patch_target, func, key):
        with mock.patch.object(patch_target, func, side_effect=trek.TrekError("down")):
            r = self.client.get(url)
        self.assertEqual((r.status_code, r["Cache-Control"]), (200, "no-store"))
        tilecache.put(key, OLD)
        age(key)
        with mock.patch.object(patch_target, func, side_effect=trek.TrekError("down")):
            r = self.client.get(url)
        self.assertEqual(r.content, OLD)
        with mock.patch.object(patch_target, func, return_value=PNG):
            r = self.client.get(url)
        self.assertEqual((r.content, r["X-GSM-Cache"]), (PNG, "miss"))      # 늙은 것은 다시 묻고 덮는다
        self.assertEqual(tilecache.get(key), PNG)

    def test_달_극_지질도(self):
        self.check("/GSM/moon/ptiles/s/units/2/1/1.png", trek, "get_polar_tile", tilecache.key_text("trek", "sp/units/2/1/1"))

    def test_Trek_판(self):
        with mock.patch.object(trek, "map_entry", return_value={"ms": "x"}):
            self.check("/GSM/trek/mars/map/geo/3/2/2.png", trek, "map_tile", tilecache.key_text("trek-map", "mars/geo/3/2/2"))
            self.assertEqual(self.client.get("/GSM/trek/mars/map/geo/2/9/9.png").status_code, 404)

    def test_Trek_극지_판(self):
        with mock.patch.object(trek, "polar_map", return_value="x"):
            self.check("/GSM/trek/moon/map/geo/p/n/2/1/1.png", trek, "map_polar_tile",
                       tilecache.key_text("trek-map-polar", "moon/geo/n/2/1/1"))
            self.assertEqual(self.client.get("/GSM/trek/moon/map/geo/p/n/2/9/9.png").status_code, 404)


class MexicoLegend(SimpleTestCase):
    URL = "/GSM/sgm/legend/"

    def test_변수가_틀리면(self):
        self.assertEqual(self.client.get(self.URL, {"layer": "sgm:none"}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"layer": "sgm:8", "bbox": "x"}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"layer": "sgm:8", "bbox": "-110,20,-90,30"}).status_code, 422)

    def test_상류가_못_주면_502(self):
        from viewer import sgm
        with mock.patch.object(sgm, "breaks", side_effect=sgm.SgmError("down")):
            self.assertEqual(self.client.get(self.URL, {"layer": "sgm:anom250:0"}).status_code, 502)
        with mock.patch.object(sgm, "extent_legend", side_effect=sgm.SgmError("down")):
            self.assertEqual(self.client.get(self.URL, {"layer": "sgm:8", "bbox": "-100,20,-99.9,20.1"}).status_code, 502)


class AlbertaPoints(SimpleTestCase):
    def test_한_덩이_또는_502(self):
        from viewer import ags
        with mock.patch.object(ags, "points_body", return_value=b'{"type":"FeatureCollection","features":[]}'):
            r = self.client.get("/GSM/points/", {"layer": ags.POINTS})
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/geo+json"))
        with mock.patch.object(ags, "points_body", side_effect=ags.AgsError("down")):
            self.assertEqual(self.client.get("/GSM/points/", {"layer": ags.POINTS}).status_code, 502)


class PeruInfo(SimpleTestCase):
    URL = "/GSM/ingemmet/info/"
    Q = {"layer": "ingemmet:50k", "lat": "-12.05", "lon": "-77.0"}

    def test_못_받으면_옛것_없으면_502(self):
        from viewer import ingemmet
        with mock.patch.object(ingemmet, "point_attributes", side_effect=ingemmet.IngemmetError("down")):
            self.assertEqual(self.client.get(self.URL, self.Q).status_code, 502)
        key = tilecache.key_text("ingemmet-info", "ingemmet:50k/-12.05000,-77.00000")
        tilecache.put(key, json.dumps({"row": None}).encode(), ".json")
        age(key, ".json")
        with mock.patch.object(ingemmet, "point_attributes", side_effect=ingemmet.IngemmetError("down")):
            r = self.client.get(self.URL, self.Q)
        self.assertEqual((r.status_code, r.json()), (200, {"features": []}))   # 옛것은 "그 자리에 아무것도 없다"

    def test_영어판은_속성_이름을_옮긴다(self):
        from viewer import ingemmet
        self.client.cookies[i18n.COOKIE] = "en"
        with mock.patch.object(ingemmet, "point_attributes", return_value={"x": 1}), \
             mock.patch.object(ingemmet, "friendly", return_value={"기호": "Ki-ca", "지질시대": "백악기"}):
            props = self.client.get(self.URL, self.Q).json()["features"][0]["props"]
        self.assertEqual(props, {"Symbol": "Ki-ca", "Geologic age": "Cretaceous"})
