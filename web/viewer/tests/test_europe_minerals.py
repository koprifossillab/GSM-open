"""유럽 나라별 광물 (wetherilli 296) — 프랑스 BD Gîtes·광산, 스페인 BDMIN, 독일 KOR250·BSK1000, 포르투갈 광상·자력·중력·방사능.
상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import arcwms, bgr, brgm, igme, lneg

WEB = {"crs": "EPSG:3857", "bbox": "-860000,4870000,-850000,4880000", "width": 256, "height": 256}
LNEG_PLAIN = ("@Dimensão do Depósito Mineral - Substâncias Úteis OBJECTID;Shape;Nº;Siorminp;Nome;Tipo;Substâncias;Dimensão;Produção Minério In Situ;"
              " 2260;Point;1513;1268ZnPb;Ceiroco;Depósito mineral de zinco e chumbo de dimensão pequena;Zn, Pb;Pequena;- / -; ")


def answer(body=b"\x89PNG", ctype="image/png"):
    r = mock.Mock(status_code=200, content=body, url="…", text=body.decode("utf-8", "replace") if isinstance(body, bytes) else body,
                  headers={"content-type": ctype})
    return r


class Plain(SimpleTestCase):
    def test_ArcGIS_text_plain(self):
        rows = arcwms.fields_plain(LNEG_PLAIN)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["OBJECTID"], rows[0]["Nome"], rows[0]["Substâncias"]), ("2260", "Ceiroco", "Zn, Pb"))   # 레이어 이름의 빈칸


class Doors(SimpleTestCase):
    def setUp(self):
        for mod in (bgr, igme, lneg):
            for name, value in (("record", None), ("paused", 0)):
                p = mock.patch.object(mod.usage, name, return_value=value)
                p.start()
                self.addCleanup(p.stop)

    def test_포르투갈은_판이_서비스를_고른다(self):
        with mock.patch.object(lneg.requests, "get", return_value=answer(LNEG_PLAIN.encode("utf-8"), "text/plain")) as get:
            got = lneg.get_feature_info(dict(WEB, layers="lneg:dep200k:4", query_layers="lneg:dep200k:4", i=10, j=10))
        self.assertIn("/CartaDepositosMinerais200k/MapServer/WMSServer", get.call_args.kwargs.get("url", "") or get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["info_format"], "text/plain")
        props = lneg.friendly(got["features"][0]["properties"])
        self.assertEqual((props["이름"], props["광종"]), ("Ceiroco", "Zn, Pb"))
        self.assertNotIn("생산량", props)
        with mock.patch.object(lneg.requests, "get", return_value=answer()) as get:
            lneg.get_map(dict(WEB, layers="lneg:500k:2"))
        self.assertIn("/CGP500k/", get.call_args.args[0])
        self.assertEqual(lneg.friendly({"Stretch.PixelValue": "-43.077026", "_raster": "lneg:mag:"}), {"자력 이상 (nT)": "-43.1"})

    def test_독일_원료는_rohstoffe_폴더(self):
        with mock.patch.object(bgr.requests, "get", return_value=answer()) as get:
            bgr.get_map(dict(WEB, layers="bgr:kor250:2+3+4"))
        self.assertEqual(get.call_args.args[0], "https://services.bgr.de/wms/rohstoffe/kor250/")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "2,3,4")

    def test_스페인_광물_산지는_BasesDatos(self):
        with mock.patch.object(igme.requests, "get", return_value=answer()) as get:
            igme.get_map(dict(WEB, layers="igme:bdmin:0+1"))
        self.assertEqual(get.call_args.args[0], "https://mapas.igme.es/gis/services/BasesDatos/IGME_BDMIN_Indicios/MapServer/WMSServer")
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "0,1")


class Friendly(SimpleTestCase):
    def test_속성(self):
        fr = brgm.friendly({"nom_gite": "Margnac", "c_substance": "U", "production": "4300", "potentiel": "4300", "unite": "t", "reserves": ""})
        self.assertEqual((fr["이름"], fr["광종"], fr["생산량"]), ("Margnac", "U", "4300 t"))
        es = igme.friendly({"NombreMina": "Los Cuchillares", "Sustancia": " Pirita, Cobre", "EdadInferior": "DEVONICO SUPERIOR", "EdadSuperior": "CARBONIFERO"})
        self.assertEqual((es["이름"], es["광종"], es["지질시대 (원문)"]), ("Los Cuchillares", "Pirita, Cobre", "Devonico superior - Carbonifero"))
        de = bgr.friendly({"Rohstoffgruppe": "Kiese, Sande und Mürbsandsteine", "Rohstoffkategorie": "Lagerstätte", "Rohstoff 1": "Kiese und Sande"})
        self.assertEqual((de["원료"], de["갈래"]), ("Kiese und Sande", "Lagerstätte"))
