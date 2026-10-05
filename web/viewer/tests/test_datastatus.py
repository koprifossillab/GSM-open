"""구운 자료의 나이 (wetherilli 312) — 있는지·크기·고친 날·원본 판을 한 표로. 빈 임시 폴더에 몇 개만 지어 본다."""
import io
import json
import sqlite3
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from viewer import datastatus


class DataStatus(TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="gsm-datastatus-"))
        dirs = {name: str(root / name.lower()) for name in {i.where for i in datastatus.ITEMS}}
        patch = override_settings(**dirs, PUBLIC=False)
        patch.enable()
        self.addCleanup(patch.disable)
        earth = Path(dirs["EARTH_DIR"])
        earth.mkdir(parents=True)
        db = sqlite3.connect(earth / "glaciers.sqlite")
        db.executescript("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT); INSERT INTO meta VALUES ('built', '2026-10-05'), ('source', 'RGI 7.0');")
        db.commit()
        db.close()
        (earth / "gvp_volcanoes.json").write_text(json.dumps({"source": "GVP-VOTW", "fetched": "2026-10-02", "features": []}), encoding="utf-8")
        gfs = Path(dirs["WIND_DIR"]) / "gfs"
        gfs.mkdir(parents=True)
        (gfs / "index.json").write_text(json.dumps({"times": [{"t": "2026100218"}, {"t": "2026100506"}]}), encoding="utf-8")
        geomap = Path(dirs["GEOMAP_DIR"])
        geomap.mkdir(parents=True)
        (geomap / "ATA_SCAR_GeoMAP_Geology_v2022_08.gpkg").write_bytes(b"x")

    def test_있는_것과_판(self):
        rows = {r["key"]: r for r in datastatus.rows()}
        self.assertEqual(rows["earth/glaciers.sqlite"]["version"], "built 2026-10-05 · source RGI 7.0")
        self.assertEqual(rows["earth/gvp_volcanoes.json"]["version"], "source GVP-VOTW · fetched 2026-10-02")
        self.assertEqual(rows["wind/gfs"]["version"], "2026100218 – 2026100506")
        self.assertEqual(rows["geomap/*.gpkg"]["version"], "2022-08")
        self.assertFalse(rows["earth/pbdb.sqlite"]["exists"])

    def test_없는_것은_연구실_것을_밖에서_뺀다(self):
        here = datastatus.missing()
        self.assertIn("earth/pbdb.sqlite", here)
        self.assertNotIn("earth/glaciers.sqlite", here)
        self.assertIn("usgs/geo3al", here)
        with override_settings(PUBLIC=True):
            self.assertNotIn("usgs/geo3al", datastatus.missing())
        self.assertEqual(here, datastatus.missing(datastatus.rows()))      # 가벼운 셈과 표의 셈이 같다

    def test_열쇠_파일은_적지_않는다(self):
        names = " ".join(i.key for i in datastatus.ITEMS)
        for secret in ("kigam_key", "vworld_key", "geus_whoami", "secret_key"):
            self.assertNotIn(secret, names)

    def test_명령_healthz_관리_화면(self):
        out = io.StringIO()
        call_command("data_status", missing=True, stdout=out)
        self.assertIn("earth/pbdb.sqlite", out.getvalue())
        self.assertNotIn("earth/glaciers.sqlite |", out.getvalue())
        data = self.client.get("/GSM/healthz/").json()
        self.assertEqual(data["data"]["missing"], len(datastatus.missing()))
        page = self.client.get("/GSM/manage/").content.decode()
        self.assertIn('id="tab-data"', page)
        self.assertIn("built 2026-10-05 · source RGI 7.0", page)
        self.assertNotIn(tempfile.gettempdir(), page)                       # 절대 경로는 내지 않는다
