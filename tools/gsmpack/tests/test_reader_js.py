"""읽는 쪽(`js/gsmpack-reader.js`)이 쓰는 쪽(`format.py`)이 지은 묶음을 읽는다 — node 로. node 가 없으면 건너뛴다 (wetherilli P16)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from gsmpack import format

READER = Path(__file__).resolve().parent.parent / "js" / "gsmpack-reader.js"

SCRIPT = r"""
const fs = require("fs");
global.self = global;
require(process.argv[2]);
const P = self.GSMPack;
const blob = new Blob([fs.readFileSync(process.argv[3])]);
(async () => {
  const got = await P.readHeader(blob);
  const pack = {blob, head: got.head, base: got.base};
  const tile = await P.tile(pack, "L", 12, 3510, 1580).text();
  const wrong = P.tile(pack, "L", 12, 3510, 1580, 256);
  const sameGrid = !!P.tile(pack, "L", 12, 3510, 1580, {size: 512, grid: "EPSG:3857"});   // 옛 묶음(grid 없음)은 3857
  const otherGrid = P.tile(pack, "L", 12, 3510, 1580, {size: 512, grid: "EPSG:3031"});
  const none = P.tile(pack, "L", 12, 1, 1);
  const deep = P.deeper(pack, "L", 14, 3510 * 4 + 3, 1580 * 4 + 1);
  const deepText = deep && await deep.blob.text();
  const tooDeep = P.deeper(pack, "L", 17, 3510 * 32, 1580 * 32);
  const rows = await P.readUnits(pack, "L");
  const hole = P.deeper(pack, "L", 12, 3511, 1580);                    // 받지 못한 자리 → 줌 11 의 타일
  const holeText = hole && await hole.blob.text();
  const holeDeep = P.deeper(pack, "L", 13, 3511 * 2 + 1, 1581 * 2);     // 마지막 줌보다 깊은데 그 줌의 타일도 못 받았다 → 줌 11
  const sea = P.deeper(pack, "L", 12, 3510, 1581);                     // 그냥 없는 자리(바다)는 메우지 않는다
  let code = null;
  try { await P.readHeader(new Blob(["PK nope nope nope"])); } catch (e) { code = e.code; }
  console.log(JSON.stringify({title: got.head.title, tile, wrong, sameGrid, otherGrid, none, deepText,
    deep: deep && [deep.dz, deep.col, deep.row], tooDeep, holeText, hole: hole && [hole.dz, hole.col, hole.row],
    holeDeep: holeDeep && [holeDeep.dz, holeDeep.col, holeDeep.row], sea,
    missing: [P.missing(pack, "L", 12, 3511, 1580), P.missing(pack, "L", 12, 3510, 1581)], hasUnits: P.hasUnits(pack, "L"),
    inside: P.unitsAt(rows, 129.01, 37.01, "ko"), en: P.unitsAt(rows, 129.01, 37.01, "en"),
    outside: P.unitsAt(rows, 129.09, 37.09, "ko"), contains: [P.contains(pack, 129.01, 37.01), P.contains(pack, 130, 37)], code}));
})().catch(e => { console.error(e); process.exit(1); });
"""


@unittest.skipUnless(shutil.which("node"), "node 가 없다")
class Reader(unittest.TestCase):
    def test_쓴_것을_읽는다(self):
        with tempfile.TemporaryDirectory() as tmp:
            units = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
                    [[129.0, 37.0], [129.05, 37.0], [129.05, 37.05], [129.0, 37.05], [129.0, 37.0]]]},
                 "properties": {"props": {"지층": "풍촌석회암층"}, "props_en": {"Unit": "Pungchon"}}}]}
            path = Path(tmp) / "t-20261021.gsmpack"
            format.write(path, {"box": "t", "title": "시험", "bbox": [129.0, 37.0, 129.1, 37.1],
                                "layers": {"L": {"tile_size": 512, "type": "image/png", "zooms": [11, 12]}},
                                "missing": ["L/12/3511/1580", "L/12/3511/1581"],
                                "units": {"L": {"key": "@units/L"}}},
                         [("L/12/3510/1580", b"tile-bytes"), ("L/11/1755/790", b"parent-bytes"), ("@units/L", json.dumps(units).encode("utf-8"))])
            script = Path(tmp) / "run.js"
            script.write_text(SCRIPT, encoding="utf-8")
            out = subprocess.run(["node", str(script), str(READER), str(path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = json.loads(out.stdout)
        self.assertEqual(got["title"], "시험")
        self.assertEqual(got["tile"], "tile-bytes")
        self.assertIsNone(got["wrong"])                     # 격자가 다르면 그리지 않는다
        self.assertTrue(got["sameGrid"])                    # 머리에 grid 가 없는 옛 묶음은 3857 이다 (wetherilli 410)
        self.assertIsNone(got["otherGrid"])                 # 크기가 같아도 격자 이름이 다르면 그리지 않는다
        self.assertIsNone(got["none"])
        self.assertEqual(got["deepText"], "tile-bytes")          # 줌 14 의 자리 → 줌 12 의 타일, 4 × 4 칸의 (3, 1) (wetherilli 405)
        self.assertEqual(got["deep"], [2, 3, 1])
        self.assertIsNone(got["tooDeep"])                        # 16 배보다 깊게는 늘리지 않는다
        self.assertEqual(got["holeText"], "parent-bytes")        # 받지 못한 자리는 한 줌 얕은 타일을 늘린다 (wetherilli 409)
        self.assertEqual(got["hole"], [1, 1, 0])
        self.assertEqual(got["holeDeep"], [2, 3, 2])
        self.assertIsNone(got["sea"])
        self.assertEqual(got["missing"], [True, False])
        self.assertTrue(got["hasUnits"])
        self.assertEqual(got["inside"], [{"지층": "풍촌석회암층"}])
        self.assertEqual(got["en"], [{"Unit": "Pungchon"}])
        self.assertEqual(got["outside"], [])
        self.assertEqual(got["contains"], [True, False])
        self.assertEqual(got["code"], "not-pack")
