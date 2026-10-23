"""한반도 둘레의 육지 마스크(`gsmpack/landmask.png`)를 굽는다 — 어림(`bake.Plan`)이 바다 칸을 덜어 세는 바탕 (wetherilli 409).

    python tools/gsmpack/scripts/build_landmask.py /nfs/temp-share/GSM/sources/earth/natural_earth/ne_10m_admin_0_countries.zip

원본은 Natural Earth 10 m 나라 경계(공공 도메인). 나라를 가리지 않고 땅이면 칠한다 — 어림은 넘치는 쪽이 낫다.
사람이 원본을 바꿀 때만 부른다. 패키지는 구운 PNG 만 읽는다(Pillow 하나). 셰이프 읽기는 `build_natural_earth` 의 것을 옮겼다.
"""
import hashlib
import struct
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gsmpack import landmask  # noqa: E402

OUT = Path(landmask.__file__).with_name("landmask.png")


def shapes(data: bytes) -> list:
    """셰이프파일(면) → 레코드마다 고리 목록 `[[(x, y)…]…]`."""
    at, out = 100, []
    while at + 8 <= len(data):
        _, words = struct.unpack(">2i", data[at:at + 8])
        body = at + 8
        if struct.unpack("<i", data[body:body + 4])[0] == 5:
            nparts, npoints = struct.unpack("<2i", data[body + 36:body + 44])
            starts = list(struct.unpack(f"<{nparts}i", data[body + 44:body + 44 + 4 * nparts])) + [npoints]
            base = body + 44 + 4 * nparts
            xy = struct.unpack(f"<{2 * npoints}d", data[base:base + 16 * npoints])
            out.append([[(xy[2 * k], xy[2 * k + 1]) for k in range(a, b)] for a, b in zip(starts, starts[1:])])
        at = body + words * 2
    return out


def signed_area(ring) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])) / 2


def main(path):
    raw = Path(path).read_bytes()
    with zipfile.ZipFile(path) as zf:
        stem = next(n[:-4] for n in zf.namelist() if n.endswith(".shp"))
        records = shapes(zf.read(f"{stem}.shp"))
    west, south, east, north = landmask.EXTENT
    width, height = round((east - west) / landmask.STEP), round((north - south) / landmask.STEP)
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)

    def px(p):
        return ((p[0] - west) / landmask.STEP, (north - p[1]) / landmask.STEP)

    # 셰이프파일의 바깥 고리는 시계 방향(넓이가 음수), 구멍은 반대다 — 바깥을 다 칠한 뒤 구멍을 비운다
    rings = [ring for record in records for ring in record
             if max(p[0] for p in ring) >= west and min(p[0] for p in ring) <= east
             and max(p[1] for p in ring) >= south and min(p[1] for p in ring) <= north and len(ring) >= 3]
    for ring in rings:
        if signed_area(ring) < 0:
            draw.polygon([px(p) for p in ring], fill=1)
    for ring in rings:
        if signed_area(ring) > 0:
            draw.polygon([px(p) for p in ring], fill=0)
    info = PngImagePlugin.PngInfo()
    info.add_text("source", f"Natural Earth 10 m {Path(path).name} sha256 {hashlib.sha256(raw).hexdigest()[:16]} (public domain)")
    image.save(OUT, optimize=True, pnginfo=info)
    land = image.convert("L").histogram()[255] / (width * height)
    print(f"{OUT} — {width}×{height}, 땅 {land:.1%}, {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv[1])
