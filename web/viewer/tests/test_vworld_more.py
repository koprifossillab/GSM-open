"""VWorld — Capabilities 와 다시 견주어 더한 여섯 (wetherilli 350). 상류를 부르지 않는다 — 열의 꼴은 2026-10-05 에 받은 그대로다."""
import json

from django.conf import settings
from django.test import SimpleTestCase

from viewer import vworld

NEW = {"lt_c_gimslinea": "지질 참고", "lt_c_gimsstiff": "수질·지하수 측정망", "lt_l_gimsdirec": "수질·지하수 측정망",
       "lt_l_toisdepcntah": "지질 참고", "lt_c_wgisrecomp": "지질 참고", "lt_c_uq125": "재해·공역"}


class VWorldMore(SimpleTestCase):
    def test_씨앗(self):
        seed = {l["name"]: l["group"] for l in json.loads(settings.VWORLD_CATALOG_SEED.read_text(encoding="utf-8"))["레이어"]}
        self.assertEqual({n: seed.get(n) for n in NEW}, NEW)
        self.assertNotIn("lt_c_kfdrssigugrade", seed)          # 2014 년에 멈춘 예측
        self.assertEqual([vworld.MIN_ZOOM.get(n) for n in ("lt_c_gimslinea", "lt_c_gimsstiff", "lt_l_gimsdirec")], [11, 12, 12])

    def test_팝업(self):
        self.assertEqual(vworld.friendly({"regn_cd": "30000", "info": "1.0-1.5", "legend": "3", "sig_nam": "대전광역시"}, "lt_c_gimslinea"),
                         {"밀도 구간": "1.0-1.5", "시군구": "대전광역시"})
        self.assertEqual(vworld.friendly({"legend": None, "regn_cd": "30000", "sig_nam": "대전광역시"}, "lt_c_gimsstiff"), {"시군구": "대전광역시"})
        self.assertEqual(vworld.friendly({"label": "영흥도"}, "lt_l_toisdepcntah"), {"이름": "영흥도"})
        self.assertEqual(vworld.friendly({"name": "송도8공구(8-2)", "rec_co_seq": 23083}, "lt_c_wgisrecomp"), {"이름": "송도8공구(8-2)"})
        # 선(`lt_l_gimslinea`)의 `info` 는 여전히 수문지질단위다
        self.assertEqual(vworld.friendly({"info": "충적층"}, "lt_l_gimslinea"), {"수문지질단위": "충적층"})
