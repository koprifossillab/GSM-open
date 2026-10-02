"""인증키가 없을 때 타일 자리에 띄우는 안내.

키 심사를 기다리는 동안에도 레이어 패널·좌표·점묶음을 만들고 볼 수 있어야
해서 둔다. 빈 화면 대신 까닭이 적힌 타일이 뜬다.

**글자는 로마자로 적는다.** 이 저장소는 화면 문구를 한국어로 쓰지만 여기만
예외다 — 컨테이너 이미지(`python:3.12-slim`)에 폰트가 하나도 없어서 PIL 의
기본 글꼴로 한글을 그리면 **네모가 줄줄이 찍힌다.** 2026-09-23 첫 배포
화면이 그랬다.

글꼴을 이미지에 넣는 길도 있지만 한글 글꼴 하나가 웬만한 이미지 층보다
크고, **까닭은 이미 한국어로 옆에 적혀 있다** — 레이어 패널 위의 안내 띠가
그것이다(`templates/viewer/map.html` 의 `.warn`). 타일의 글자는 "여기가
자료가 아니라 안내" 임을 알리는 표지면 된다.
"""
import io

from PIL import Image, ImageDraw

_BG = (248, 246, 242, 235)
_LINE = (176, 166, 152, 255)
_TEXT = (92, 84, 74, 255)

#: 타일에 적는 말. 한글을 쓰지 않는 까닭은 이 파일 머리에 적었다.
NO_KEY = "GSM: no API key"
NO_MAP = "GSM: upstream gave no map"
#: 남극 지질도(GeoMAP) 파일이 서버에 없다 — geomap.py
NO_DATA = "GSM: no GeoMAP data file"
#: 한반도 지질도 음영판·민판을 아직 잘라 두지 않았다 — peninsula.py
NO_PENINSULA = "GSM: no peninsula tiles"
#: 남극 IBCSO 판을 아직 잘라 두지 않았다 — ibcso.py (047)
NO_IBCSO = "GSM: no IBCSO tiles"
#: 달 지질도 원도 6 장을 아직 굽지 않았다 — moonmap.py (039)
NO_MOON = "GSM: no lunar original maps file"
#: 화성 크레이터 목록을 아직 굽지 않았다 — marscraters.py (067)
NO_MARS_CRATERS = "GSM: no Mars crater file"
#: 화성 옛 지질도를 아직 굽지 않았다 — marsmap.py (068)
NO_MARS_ORIGINALS = "GSM: no Mars original maps file"
#: 수성 지질도를 아직 굽지 않았다 — mercurymap.py (wetherilli 144)
NO_MERCURY_GEOLOGY = "GSM: no Mercury geologic map file"


def notice_tile(width: int, height: int, message: str) -> bytes:
    width = max(1, min(width, 4096))
    height = max(1, min(height, 4096))
    img = Image.new("RGBA", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    # 빗금 — 여기가 자료가 아니라 안내임을 한눈에 알리려는 것
    step = 24
    for x in range(-height, width, step):
        draw.line([(x, height), (x + height, 0)], fill=_LINE, width=1)

    if width >= 180 and height >= 60:
        box = (8, height // 2 - 20, width - 8, height // 2 + 20)
        draw.rectangle(box, fill=(255, 255, 255, 236), outline=_LINE)
        draw.text((18, height // 2 - 8), message, fill=_TEXT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def blank_tile(width: int = 256, height: int = 256) -> bytes:
    """비어 있는 자리의 투명한 타일. 상류에 그 자리 타일이 아예 없을 때 쓴다 —
    한반도 지질도(026)의 바다가 그렇다. 안내가 아니라 "그릴 것이 없다" 이다."""
    buf = io.BytesIO()
    Image.new("RGBA", (max(1, min(width, 4096)), max(1, min(height, 4096))), (0, 0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()
