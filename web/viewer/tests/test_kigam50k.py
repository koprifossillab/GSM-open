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
