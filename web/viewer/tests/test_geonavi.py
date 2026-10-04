"""지질도Navi 판 목록 (wetherilli 171). 상류를 타지 않는다."""
import json

from django.test import TestCase

from viewer import gsj

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1"
  xmlns:xlink="http://www.w3.org/1999/xlink" version="1.0.0"><Contents>
<Layer><ows:Title>5万分の1地質図幅_小倉(1998)</ows:Title><ows:Identifier>G50_14_034kokura</ows:Identifier>
<ows:WGS84BoundingBox><ows:LowerCorner>130.7476 33.83659</ows:LowerCorner><ows:UpperCorner>131.03096 34.01826</ows:UpperCorner></ows:WGS84BoundingBox>
<Style isDefault="true"><ows:Identifier>default</ows:Identifier>
<LegendURL format="image/jpeg" xlink:href="https://gbank.gsj.jp/geonavi/docdata/data/pict_data/orgsize_657_legend_755.jpg"/></Style>
<Format>image/png</Format><TileMatrixSetLink><TileMatrixSet>GoogleMapsCompatible_z14</TileMatrixSet></TileMatrixSetLink>
<ResourceURL format="image/png" resourceType="tile" template="https://tiles.gsj.jp/tiles/geomap/G50_14_034kokura/{TileMatrix}/{TileCol}/{TileRow}.png"/>
</Layer>
<Layer><ows:Title>重力図_青森地域重力図(1990)</ows:Title><ows:Identifier>GRAV_01</ows:Identifier>
<ows:WGS84BoundingBox><ows:LowerCorner>139 40</ows:LowerCorner><ows:UpperCorner>142 42</ows:UpperCorner></ows:WGS84BoundingBox>
<TileMatrixSetLink><TileMatrixSet>GoogleMapsCompatible_z11</TileMatrixSet></TileMatrixSetLink>
<ResourceURL format="image/png" resourceType="tile" template="https://tiles.gsj.jp/tiles/geomap/GRAV_01/{TileMatrix}/{TileCol}/{TileRow}.png"/>
</Layer>
<Layer><ows:Title>他所の判</ows:Title><ows:Identifier>ELSEWHERE</ows:Identifier>
<ows:WGS84BoundingBox><ows:LowerCorner>139 40</ows:LowerCorner><ows:UpperCorner>142 42</ows:UpperCorner></ows:WGS84BoundingBox>
<TileMatrixSetLink><TileMatrixSet>GoogleMapsCompatible_z11</TileMatrixSet></TileMatrixSetLink>
<ResourceURL format="image/png" resourceType="tile" template="https://example.org/{TileMatrix}/{TileCol}/{TileRow}.png"/>
</Layer>
</Contents></Capabilities>"""


class GeonaviTests(TestCase):
    def test_Capabilities_를_판으로(self):
        layers = gsj.parse_geonavi(XML)
        self.assertEqual([e["id"] for e in layers], ["G50_14_034kokura", "GRAV_01"])     # 다른 주소 꼴은 뺀다
        kokura = layers[0]
        self.assertEqual(kokura["max"], 14)
        self.assertEqual(kokura["legend"], "orgsize_657_legend_755.jpg")
        self.assertEqual(kokura["bbox"], [130.7476, 33.8366, 131.031, 34.0183])
        self.assertEqual(layers[1]["legend"], "")

    def test_제목은_시리즈와_도폭(self):
        self.assertEqual(gsj.split_title("5万分の1地質図幅_小倉(1998)"), ("5万分の1地質図幅", "小倉(1998)"))
        self.assertEqual(gsj.split_title("밑줄 없음"), ("", "밑줄 없음"))

    def test_씨앗은_시리즈마다_한글_이름이_있다(self):
        layers = gsj.load_geonavi()
        self.assertGreater(len(layers), 1000)
        known = {s[0] for s in gsj.GEONAVI_SERIES}
        self.assertFalse({gsj.split_title(e["title"])[0] for e in layers} - known)

    def test_목록_끝점은_시리즈로_묶고_말을_따른다(self):
        data = self.client.get("/GSM/gsj/geonavi/").json()
        self.assertTrue(data["tiles"].startswith("https://tiles.gsj.jp/"))
        first = data["series"][0]
        self.assertEqual(first["name"], "5만 지질도폭")                     # 축척 큰 지질도폭이 맨 앞
        layer_id, sheet, bbox, zmax, legend = first["layers"][0]
        self.assertEqual(len(bbox), 4)
        self.client.cookies["gsm_lang"] = "en"
        data = self.client.get("/GSM/gsj/geonavi/").json()
        self.assertEqual(data["series"][0]["name"], "1:50,000 geological sheets")

    def test_숨긴_판은_내리지_않는다(self):
        from unittest import mock
        rows = [{"id": "A", "title": "重力図_甲", "bbox": [0, 0, 1, 1], "max": 11, "legend": ""},
                {"id": "B", "title": "重力図_乙", "bbox": [0, 0, 1, 1], "max": 11, "legend": "", "hide": True}]
        with mock.patch.object(gsj, "load_geonavi", return_value=rows):
            data = gsj.client_geonavi("ko")
        self.assertEqual([[l[0] for l in s["layers"]] for s in data["series"]], [["A"]])
        self.assertEqual(data["series"][0]["name"], "중력도")

    def test_지도_화면에는_판_목록을_싣지_않는다(self):
        html = self.client.get("/GSM/map/").content.decode()
        self.assertNotIn("G50_14_034kokura", html)
        self.assertLess(len(html), 400_000)
