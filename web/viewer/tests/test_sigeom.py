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
