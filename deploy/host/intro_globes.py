"""소개 화면의 둥근 지구·달·화성·수성에 감을 그림(정거원통, 2:1)을 굽는다 (wetherilli 115).

    ~/venv/GSM/bin/python deploy/host/intro_globes.py [뿌리 주소] [earth|moon|mars|mercury …]     기본 http://localhost/GSM/, 넷 다

달(LRO WAC)·화성(Viking) 영상 위에 우리 서버의 지질도를 비치게 얹는다 — 구가 천체처럼 보이면서 지질도의 색이
드러나게. 지구는 Blue Marble 영상만이다(아래 `earth` 의 까닭). 결과는 `web/viewer/static/viewer/intro/globe-<몸>.webp` 한 장씩이다.

- 달·화성의 지질도는 경위도 격자(줌 0 이 가로 2·세로 1)라 이어 붙이면 그대로 정거원통이다
- 영상은 바깥에서 곧장 받는다(GIBS WMS·NASA Trek). 제품의 문(`viewer/*.py`)을 타지 않는 일회성 도구라
  표준 라이브러리 `urllib` 로 받는다
"""
import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost/GSM/").rstrip("/") + "/"
OUT = Path(__file__).resolve().parents[2] / "web" / "viewer" / "static" / "viewer" / "intro"
W, H = 2048, 1024
UA = {"User-Agent": "GSM/0.1"}


def fetch(url: str) -> Image.Image:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGBA")


def stitch(url: str, z: int, cols: int, rows: int, order: str = "zxy") -> Image.Image:
    """경위도 격자의 타일을 한 장으로 잇는다. `order` 가 zyx 면 주소에 y 가 먼저다(Trek)."""
    size = 256
    sheet = Image.new("RGBA", (cols * size, rows * size))
    for y in range(rows):
        for x in range(cols):
            u = url.format(z=z, x=x, y=y)
            try:
                sheet.paste(fetch(u).resize((size, size)), (x * size, y * size))
            except Exception as e:                 # 빈 타일(바다·자료 없음)은 비워 둔다
                print("  빈칸", u, e)
    return sheet.resize((W, H), Image.LANCZOS)


def blend(base: Image.Image, geo: Image.Image, alpha: float) -> Image.Image:
    """영상 위에 지질도를 곱하듯 얹는다 — 영상의 음영이 지질도 아래로 비친다."""
    base = base.convert("RGB")
    geo_rgb = geo.convert("RGB")
    a = geo.getchannel("A").point(lambda v: int(v * alpha))
    lit = Image.blend(geo_rgb, Image.eval(Image.blend(base, geo_rgb, .5), lambda v: v), .35)
    return Image.composite(lit, base, a)


def save(img: Image.Image, name: str):
    path = OUT / f"globe-{name}.webp"
    img.convert("RGB").save(path, "WEBP", quality=80, method=6)
    print(f"  {path.name}  {path.stat().st_size // 1024} KB")


def earth():
    # 지구는 영상만 — Macrostrat 은 낮은 줌에서 대륙 일부가 비고(줌 2) 대역이 다른 타일이 섞여(줌 3) 구 한 장에
    # 얼룩이 진다. 지질도의 색은 달·화성의 구와 장면의 화면이 보인다
    save(fetch("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap"
               "&VERSION=1.3.0&LAYERS=BlueMarble_ShadedRelief_Bathymetry&STYLES=&CRS=EPSG:4326"
               f"&BBOX=-90,-180,90,180&WIDTH={W}&HEIGHT={H}&FORMAT=image/jpeg"), "earth")


def moon():
    base = stitch("https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/"
                  "{z}/{y}/{x}.jpg", 2, 8, 4)
    save(blend(base, stitch(ROOT + "moon/tiles/units/{z}/{x}/{y}.png", 2, 8, 4), .48), "moon")


def mars():
    base = stitch("https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/"
                  "default028mm/{z}/{y}/{x}.jpg", 2, 8, 4)
    save(blend(base, stitch(ROOT + "mars/tiles/units/{z}/{x}/{y}.png", 2, 8, 4), .5), "mars")


def mercury():
    # 수성 — MESSENGER 모자이크 위에 USGS 1:500만 지질도(wetherilli 144). 지질도는 마리너 10 이 찍은 반쪽 남짓뿐이다
    base = stitch("https://trek.nasa.gov/tiles/Mercury/EQ/Mercury_MESSENGER_mosaic_global_250m_2013/1.0.0/default/"
                  "default028mm/{z}/{y}/{x}.png", 2, 8, 4)
    save(blend(base, stitch(ROOT + "mercury/tiles/units/{z}/{x}/{y}.png", 2, 8, 4), .5), "mercury")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[2:]
    for job in (earth, moon, mars, mercury):
        if only and job.__name__ not in only:
            continue
        print(job.__name__)
        job()
