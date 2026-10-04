"""페루 INGEMMET 의 지화학 지도첩·산업 광물 (wetherilli 303). 상류를 부르지 않는다 — 꼴은 2026-10-05 에 받은 그대로다."""
from unittest import mock

from django.test import SimpleTestCase

from viewer import ingemmet


def answer(body=None, ctype="image/png"):
    r = mock.Mock(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": ctype})
    r.json = lambda: body
    return r


class Atlas(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(ingemmet.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_그림은_분산도와_이상점을_함께(self):
        with mock.patch.object(ingemmet.requests, "get", return_value=answer()) as get:
            ingemmet.get_tile("ingemmet:gq_cu", 6, 18, 33)
        self.assertTrue(get.call_args.args[0].endswith("/SERV_ATLAS_GEOQUIMICO/MapServer/export"))
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "show:8,7")

    def test_누르면_이상점을_묻는다(self):
        body = {"features": [{"attributes": {"Anomalía": "Pupahuay", "Commodity": "Cu", "Concentrac": "518", "Depósito": "-"},
                              "geometry": {"x": -75.9, "y": -11.6}}]}
        with mock.patch.object(ingemmet.requests, "get", return_value=answer(body, "application/json")) as get:
            rows = ingemmet.resource_attributes("ingemmet:gq_cu", -11.6, -75.9, 0.02)
        self.assertIn("/SERV_ATLAS_GEOQUIMICO/MapServer/7/query", get.call_args.args[0])
        props = ingemmet.resource_friendly("ingemmet:gq_cu", rows[0])
        self.assertEqual((props["이상"], props["함량"]), ("Pupahuay", "518"))
        self.assertNotIn("광상", props)                                   # "-" 는 뺀다

    def test_리튬(self):
        props = ingemmet.resource_friendly("ingemmet:lithium", {"NOMBRE": "Fundición", "SUSTANCIA": "Litio", "VA_LITIO": "219.0"})
        self.assertEqual(props["리튬 (ppm)"], "219.0")
        self.assertTrue(ingemmet.valid_tile("ingemmet:gq_zn", 5, 9, 16))
