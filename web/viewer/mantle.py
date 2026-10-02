"""맨틀 슬랩 — Müller et al. (2022) OPT1 의 섭입한 판(Slabs)·맨틀 하부 더미(Piles)·판 경계 (wetherilli P07 §3·106).

`manage.py build_mantle <zip>` 이 ParaView 묶음(VTK XML)을 시점마다 삼각형 한 덩이로 풀어 `<EARTH_DIR>/mantle/` 에 둔다. 우리 디스크의
파일이라 문이 아니다. 없으면 레이어만 빈다.

- **모의 결과이지 관측이 아니다.** 지구 역학 모형의 온도장에서 뽑은 면이다 — 섭입한 판(찬 것)과 핵–맨틀 경계 위의 더미(뜨거운 것)
- 시점은 20 Myr 마다 51 개(1 000–0 Ma). 사이를 메우지 않는다 — 가장 가까운 시점, 같으면 오래된 쪽(ETT 와 같다)
- 좌표는 반지름 1 의 구다(z 가 북, x 가 경도 0°). 오늘(0 Ma)은 오늘의 지구와 같다. **옛 연대에서는 OPT1 의 맨틀 기준틀이라
  PALEOMAP 판 조각과 맞지 않는다**(ETT `docs/mantle-frame-alignment.md`). 화면이 그렇게 적는다
- VTK 는 numpy 없이 푼다 — 이 묶음에 든 두 꼴(압축 없는 UInt64 머리, meshio 의 zlib 덩이)만 읽고 다른 꼴은 멈춘다
  (ETT `scripts/build_mantle.py`, MIT 를 옮겼다)
"""
import base64
import functools
import json
import struct
import xml.etree.ElementTree as ET
import zlib
from array import array
from pathlib import Path, PurePosixPath

from django.conf import settings

PREFIX = "OPT1_3D_visualisation_ParaView/"
FRAMES = 51
LAYERS = ("slabs", "piles", "boundaries")
TYPES = {"Float32": ("f", 4), "Float64": ("d", 8), "Int64": ("q", 8), "UInt8": ("B", 1)}
CREDIT = "Müller et al. (2022) OPT1, Solid Earth 13, 1127 · CC BY 4.0"


class MantleError(RuntimeError):
    pass


def age_of(frame: int) -> float:
    """원본의 시점 → Ma. 상태 파일의 `TimeToTextConvertor`(Scale −20, Shift 1000)."""
    return 1000.0 - 20.0 * frame


def frame_of(age: float) -> int:
    """연대 → 가장 가까운 시점. 같으면 오래된 쪽."""
    return max(0, min(FRAMES - 1, int((1000.0 - age) / 20.0 + 0.5 - 1e-9)))


def _array(node, root) -> array:
    if node is None or root.get("byte_order") != "LittleEndian" or node.get("format") != "binary":
        raise MantleError("다른 꼴의 VTK 배열이다")
    code, size = TYPES.get(node.get("type"), (None, 0))
    if code is None:
        raise MantleError(f"모르는 수 꼴 {node.get('type')}")
    text = "".join((node.text or "").split())
    if root.get("compressor") == "vtkZLibDataCompressor" and root.get("header_type", "UInt32") == "UInt32":
        # meshio — 압축한 머리와 몸을 따로 base64 로 적는다
        blocks = struct.unpack("<I", base64.b64decode(text[:8])[:4])[0]
        head_len = 4 * (((3 + blocks) * 4 + 2) // 3)
        sizes = struct.unpack(f"<{3 + blocks}I", base64.b64decode(text[:head_len])[:4 * (3 + blocks)])
        body, data, at = base64.b64decode(text[head_len:]), b"", 0
        for n in sizes[3:]:
            data += zlib.decompress(body[at:at + n])
            at += n
    elif not root.get("compressor") and root.get("header_type") == "UInt64":
        raw = base64.b64decode(text)
        if struct.unpack("<Q", raw[:8])[0] != len(raw) - 8:
            raise MantleError("VTK 바이트 수가 맞지 않는다")
        data = raw[8:]
    else:
        raise MantleError("다른 꼴의 VTK 압축이다")
    out = array(code)
    out.frombytes(data)
    return out


def read_piece(data: bytes, lines: bool):
    """VTU 한 조각 → (점 float32 xyz, 이음 uint32). 선은 토막마다 두 점씩 편다."""
    root = ET.fromstring(data)
    piece = root.find("UnstructuredGrid/Piece")
    if piece is None:
        raise MantleError("조각이 없다")
    points = array("f", _array(piece.find("Points/DataArray"), root))
    cells = {a.get("Name"): _array(a, root) for a in piece.findall("Cells/DataArray")}
    offsets, conn, types = cells["offsets"], cells["connectivity"], cells["types"]
    if len(points) != 3 * int(piece.get("NumberOfPoints")) or len(types) != int(piece.get("NumberOfCells")):
        raise MantleError("VTK 점·칸 수가 맞지 않는다")
    if lines:
        out, start = array("I"), 0
        for end in offsets:
            for a, b in zip(conn[start:end - 1], conn[start + 1:end]):
                out.extend((a, b))
            start = end
    else:
        if any(t != 5 for t in types):
            raise MantleError("삼각형이 아닌 칸이 있다")
        out = array("I", conn)
    return points, out


def read_layer(zf, name: str, frame: int):
    """시점 하나의 레이어 → (점, 이음). 조각(12)을 이어 붙인다."""
    if name == "boundaries":
        members = [PREFIX + f"Reconstruction/Plate-polygons/PlateBoundaries_gcm32__{frame:02d}.vtu"]
    else:
        title = {"slabs": "Slabs", "piles": "Piles"}[name]
        parent = PREFIX + f"{title}/{title}_{frame:02d}.pvtu"
        root = ET.fromstring(zf.read(parent))
        members = []
        for part in root.findall(".//Piece"):
            rel = PurePosixPath(part.get("Source"))
            if rel.is_absolute() or ".." in rel.parts:
                raise MantleError("묶음 밖을 가리키는 조각")
            members.append(str(PurePosixPath(parent).parent / rel))
    points, conn = array("f"), array("I")
    for member in members:
        p, c = read_piece(zf.read(member), name == "boundaries")
        base = len(points) // 3
        points.extend(p)
        conn.extend(i + base for i in c)
    for i in range(0, len(points), 3 * max(1, len(points) // 3000)):       # 반지름 1 의 구 안인지 몇 점만
        r = (points[i] ** 2 + points[i + 1] ** 2 + points[i + 2] ** 2) ** 0.5
        if not 0.5 <= r <= 1.01:
            raise MantleError(f"구 밖의 점 (반지름 {r:.3f})")
    return points, conn


def folder() -> Path:
    return Path(settings.EARTH_DIR) / "mantle"


@functools.lru_cache(maxsize=1)
def _catalogue(mtime):
    with open(folder() / "catalogue.json", encoding="utf-8") as fh:
        return json.load(fh)


def catalogue():
    """구운 목록. 없으면 None."""
    try:
        return _catalogue((folder() / "catalogue.json").stat().st_mtime)
    except FileNotFoundError:
        return None


def file_for(frame: int, layer: str):
    """시점·레이어의 파일(gzip 한 것과 안 한 것). 목록에 없으면 None."""
    cat = catalogue()
    if not cat or layer not in LAYERS:
        return None
    for f in cat["frames"]:
        if f["frame"] == frame:
            return folder() / f["layers"][layer]["file"]
    return None
