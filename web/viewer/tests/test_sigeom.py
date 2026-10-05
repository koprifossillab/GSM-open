"""퀘벡 SIGÉOM 의 광물 산지 (wetherilli 323)."""
from django.test import SimpleTestCase

from viewer import sigeom


class Gites(SimpleTestCase):
    """퀘벡 광물 산지 (wetherilli 323) — 금속·비금속·석재의 열을 한 꼴로, 금속은 SIGÉOM 상세 링크"""
    def test_금속(self):
        props = {"NOM_CORPS_MINR": "Mine Sullivan", "ETAT_CORPS_MINR": "Mine fermée", "SUBST_PRINC": "Or", "AN_DECV": "1911",
                 "URL_NOM_CORPS_MINR": '<a href="https://sigeom.mines.gouv.qc.ca/signet/classes/I1103_index?l=F&amp;valr_crit=2453" target="_blank">Mine Sullivan</a>'}
        got = sigeom.friendly(props)
        self.assertEqual((got["이름"], got["상태"], got["광종"], got["발견 연도"]), ("Mine Sullivan", "Mine fermée", "Or", "1911"))
        self.assertEqual(got["상세"]["links"][0]["url"], "https://sigeom.mines.gouv.qc.ca/signet/classes/I1103_index?l=F&valr_crit=2453")

    def test_비금속과_석재(self):
        self.assertEqual(sigeom.friendly({"NOM_GISM": "Labmag", "ETAT_GISM": "Indice travaillé", "MINER": "Magnésite"}),
                         {"이름": "Labmag", "광종": "Magnésite", "상태": "Indice travaillé"})
        self.assertEqual(sigeom.friendly({"NOM_GISM_CARR": "Mine Bell", "PROD_EXTR": "Pierre concassée", "USAGE_PROD_EXTR": "Granulat"}),
                         {"이름": "Mine Bell", "산물": "Pierre concassée", "쓰임": "Granulat"})
        self.assertTrue(sigeom.queryable("sigeom:gites_metal"))


class Legend(SimpleTestCase):
    """퀘벡 일반·지역 지질의 보는 범위 범례 — WFS 의 면 색으로 센다 (wetherilli 337)"""
    def test_단위마다_센다(self):
        from unittest import mock
        feats = [{"properties": {"ZGQ_CODE_IDENT_ETIQU_LEGEN": "S9", "ZGQ_DESCR": "Andésite", "AGE": "Néoarchéen", "COUL_REMPL_HEXA": "#80F1B9"}}] * 3 + \
                [{"properties": {"ZGQ_CODE_IDENT_ETIQU_LEGEN": "G2", "ZGQ_DESCR": "Paragneiss", "AGE": "Néoarchéen", "COUL_REMPL_HEXA": "#FFE336"}}]
        ok = mock.Mock(status_code=200, url="u", content=b"{}", json=lambda: {"features": feats}, elapsed=None)
        with mock.patch.object(sigeom.requests, "get", return_value=ok) as get, mock.patch.object(sigeom.usage, "paused", return_value=0):
            rows = sigeom.extent_legend("sigeom:generale", (-79.0, 47.5, -76.5, 49.0), "en")
        self.assertIn("IDS_SGM_WFS", get.call_args[0][0])
        self.assertNotIn("SHAPE", get.call_args[1]["params"]["PROPERTYNAME"])                 # 기하는 받지 않는다
        self.assertEqual([(r["symbol"], r["color"], r["count"]) for r in rows], [("S9", "#80F1B9", 3), ("G2", "#FFE336", 1)])
        self.assertEqual(rows[0]["age"], "Neoarchean")
