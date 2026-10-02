"""십진도와 도분초를 오간다.

import 가 하나도 없다. 좌표 표시는 상류도 DB 도 타지 않는 순수한 계산이고,
그 경계를 지켜 두면 시험이 쉽다.
"""


def dd_to_dms(value: float, is_lat: bool) -> str:
    """십진도 -> 도분초. `37°30'15.2\"N` 꼴."""
    hemi = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    value = abs(value)
    deg = int(value)
    rest = (value - deg) * 60
    minute = int(rest)
    second = (rest - minute) * 60
    # 반올림이 60 을 만들면 한 자리 올린다 — 59'60" 이 뜨지 않게 한다
    if round(second, 1) >= 60:
        second = 0.0
        minute += 1
    if minute >= 60:
        minute = 0
        deg += 1
    return f"{deg}°{minute:02d}'{second:04.1f}\"{hemi}"


def format_pair(lon: float, lat: float, dms: bool = False) -> str:
    """화면 아래에 늘 떠 있는 좌표 한 줄. 위도를 앞에 쓴다."""
    if dms:
        return f"{dd_to_dms(lat, True)} {dd_to_dms(lon, False)}"
    return f"{lat:.6f}, {lon:.6f}"


def parse(text: str):
    """사람이 찍어 넣은 좌표를 읽는다. (lat, lon) 또는 None.

    받아들이는 꼴:
        37.5665, 126.9780
        37.5665 126.9780
        37°30'15.2"N 127°00'30.1"E
        N37 30 15.2 E127 00 30.1
    """
    if not text:
        return None
    s = text.strip().replace(",", " ")
    for ch in "°'\"′″":
        s = s.replace(ch, " ")
    tokens = s.split()
    if not tokens:
        return None

    # 십진도 둘뿐이면 그대로
    if len(tokens) == 2:
        try:
            lat, lon = float(tokens[0]), float(tokens[1])
        except ValueError:
            pass
        else:
            return (lat, lon) if _sane(lat, lon) else None

    # 반구 글자를 떼어내며 두 덩이로 가른다
    parts, current, hemis = [], [], []
    for token in tokens:
        head = token[0].upper()
        tail = token[-1].upper()
        hemi = head if head in "NSEW" else (tail if tail in "NSEW" else None)
        if hemi:
            token = token.strip("NSEWnsew")
            if current:
                parts.append(current)
                current = []
            hemis.append(hemi)
        if token:
            current.append(token)
    if current:
        parts.append(current)
    if len(parts) != 2 or len(hemis) != 2:
        return None

    try:
        values = [_dms_parts_to_dd(p) for p in parts]
    except ValueError:
        return None

    pair = {}
    for hemi, value in zip(hemis, values):
        if hemi in "NS":
            pair["lat"] = value if hemi == "N" else -value
        else:
            pair["lon"] = value if hemi == "E" else -value
    if "lat" not in pair or "lon" not in pair:
        return None
    return (pair["lat"], pair["lon"]) if _sane(pair["lat"], pair["lon"]) else None


def _dms_parts_to_dd(parts) -> float:
    deg = float(parts[0])
    minute = float(parts[1]) if len(parts) > 1 else 0.0
    second = float(parts[2]) if len(parts) > 2 else 0.0
    return deg + minute / 60 + second / 3600


def _sane(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180
