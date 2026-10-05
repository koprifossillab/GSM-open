"""남호주 방사능 농도 격자 — 누른 자리의 칼륨·토륨·우라늄 값 (wetherilli 358).

SARIG 의 영상 WMS(`gssa:rad_rgb`, wetherilli 329)는 칠한 삼색만 주어 누르면 RGB 뿐이다. 값을 보이려고 원본 격자를 받아 둔다.
상류가 아니라 **우리 디스크의 파일**이라 문이 아니다. 원본은 NAS `N:\\GSM\\sources\\australia\\sa_radiometrics\\`, 구운 것은
`GSM_SARAD_DIR`(기본 `<DB 옆>/sa_radiometrics`). 파일이 없으면 `rad_rgb` 를 누르지 않는다 — 하던 대로다.

- 원본: "South Australian regional radiometric images, 2024"(SARIG 목록 `mesac771`, **CC BY 4.0 Australia**) — 원소마다 ZIP 하나(650 MB 남짓)에
  ER Mapper 격자(`*_DD.ers` 머리 + 머리 없는 float32 몸). GDA94 경위도, 한 칸 0.00077°(80 m 남짓), 15 581×15 796 칸, 빈 곳 −99999.
  K 는 %, Th·U 는 등가 ppm(eTh·eU) — 메타데이터 PDF 가 그렇게 적는다. 2025 "State radiometric grid merge" 의 43 MB ZIP 은 격자가 아니라
  탐사 구역 셰이프였다(TODOs 가 "가장 싸다" 고 적은 것)
- **네 칸에 하나를 고른다**(320 m 남짓) — 원본이 이미 80 m 로 보간한 매끄러운 격자라 누른 자리의 값으로는 넉넉하고, 원소마다 30 MB 남짓이 된다.
  numpy 없이 줄마다 `array` 를 잘라(C 에서 돈다) 컨테이너에서도 굽는다
- 값은 int16 — K 는 ×1000(0.001 %), Th·U 는 ×100(0.01 ppm). 빈 곳은 −32768. GDA94 와 WGS84 의 차(1 m 남짓)는 칸보다 훨씬 작아 옮기지 않는다
"""
import json
import math
import struct
import zipfile
from array import array
from pathlib import Path

from django.conf import settings

#: 원소 → (원본 ZIP 이름에 든 것, 배율, 속성 이름)
ELEMENTS = {"k": ("_K_", 1000, "칼륨 K (%)"), "th": ("_Th_", 100, "토륨 eTh (ppm)"), "u": ("_U_", 100, "우라늄 eU (ppm)")}
STEP = 4
NODATA = -32768


class SaradError(RuntimeError):
    pass


def root() -> Path:
    return Path(settings.SARAD_DIR)


def available() -> bool:
    return (root() / "meta.json").is_file()


def _dms(text: str) -> float:
    """ER Mapper 의 `도:분:초` → 십진도"""
    parts = [float(p) for p in text.strip().split(":")]
    sign = -1 if text.strip().startswith("-") else 1
    deg, minutes, seconds = (abs(parts[0]), *(parts[1:] + [0, 0])[:2])
    return sign * (deg + minutes / 60 + seconds / 3600)


def read_header(text: str) -> dict:
    """`.ers` 머리 → {cols, rows, dx, dy, west, north, null, little}. 경위도·float32·한 띠만 받는다"""
    values = {}
    for line in text.splitlines():
        key, eq, value = line.partition("=")
        if eq:
            values[key.strip()] = value.strip().strip('"')
    try:
        head = {"cols": int(values["NrOfCellsPerLine"]), "rows": int(values["NrOfLines"]),
                "dx": float(values["Xdimension"]), "dy": float(values["Ydimension"]),
                "west": _dms(values["Longitude"]), "north": _dms(values["Latitude"]),
                "null": float(values.get("NullCellValue", "-99999")), "little": values.get("ByteOrder", "LSBFirst") == "LSBFirst"}
    except (KeyError, ValueError) as exc:
        raise SaradError(f"ER Mapper 머리를 읽지 못했다: {exc}") from exc
    if values.get("CellType") != "IEEE4ByteReal" or values.get("NrOfBands", "1") != "1" or values.get("CoordinateType") != "LATLONG":
        raise SaradError("float32 한 띠의 경위도 격자만 굽는다")
    if int(values.get("RegistrationCellX", "0")) or int(values.get("RegistrationCellY", "0")):
        raise SaradError("기준 칸이 왼쪽 위가 아니다")
    return head


def _element_of(name: str):
    for key, (mark, _, _) in ELEMENTS.items():
        if mark in Path(name).name:
            return key
    return None


def bake(head: dict, body, scale: int, out: Path, step: int = STEP) -> dict:
    """머리 없는 float32 몸(파일 꼴, 위 줄부터)을 `step` 칸에 하나씩 골라 int16 로 `out` 에 적는다. 고른 격자의 머리를 돌려준다"""
    cols, line_bytes = head["cols"], head["cols"] * 4
    keep_cols = len(range(step // 2, cols, step))
    rows = 0
    null = head["null"]
    big = not head["little"]
    with open(out, "wb") as fh:
        for row in range(head["rows"]):
            raw = body.read(line_bytes)
            if len(raw) < line_bytes:
                raise SaradError(f"몸이 짧다 — {row} 줄째에서 끝났다")
            if row % step != step // 2:
                continue
            line = array("f", raw)
            if big:
                line.byteswap()
            picked = line[step // 2::step]
            out_line = array("h", (NODATA if v <= null + 1 or v != v else max(-32767, min(32767, round(v * scale))) for v in picked))
            fh.write(out_line.tobytes())
            rows += 1
    return {"cols": keep_cols, "rows": rows, "dx": head["dx"] * step, "dy": head["dy"] * step,
            # 고른 칸의 가운데가 원본 칸 `step//2` 의 가운데다 — 왼쪽 위 모서리를 그만큼 옮긴다
            "west": head["west"] + head["dx"] * (step // 2 + 0.5) - head["dx"] * step / 2,
            "north": head["north"] - head["dy"] * (step // 2 + 0.5) + head["dy"] * step / 2, "scale": scale}


def build(sources, out_dir=None, log=print) -> dict:
    """원소마다의 ZIP 들 → `<out>/{k,th,u}.i16`·`meta.json`. 한 원소만 넘겨도 된다 — 있는 meta 에 보탠다"""
    out = Path(out_dir) if out_dir else root()
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    for source in sources:
        with zipfile.ZipFile(source) as zf:
            ers = [n for n in zf.namelist() if n.lower().endswith(".ers")]
            if len(ers) != 1:
                raise SaradError(f"{source}: .ers 가 하나가 아니다 ({len(ers)})")
            key = _element_of(ers[0])
            if not key:
                raise SaradError(f"{source}: K·Th·U 가운데 무엇인지 모른다 ({ers[0]})")
            head = read_header(zf.read(ers[0]).decode("latin-1"))
            log(f"{key}: {head['cols']}×{head['rows']} 칸, {head['dx']}° — {STEP} 칸에 하나")
            tmp = out / f"{key}.i16.part"
            with zf.open(ers[0][:-4]) as body:
                grid = bake(head, body, ELEMENTS[key][1], tmp)
            tmp.replace(out / f"{key}.i16")
            meta[key] = grid
            meta_path.write_text(json.dumps(meta, indent=1))
    return meta


_meta_cache = {}


def _meta() -> dict:
    path = root() / "meta.json"
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return {}
    if _meta_cache.get("stamp") != stamp:
        _meta_cache.update(stamp=stamp, meta=json.loads(path.read_text()))
    return _meta_cache["meta"]


def value_at(lat: float, lon: float) -> dict:
    """누른 자리의 {속성 이름: 값}. 격자 밖이거나 빈 곳이면 그 원소는 없다"""
    out = {}
    for key, grid in _meta().items():
        if key not in ELEMENTS:
            continue
        # floor — int 는 0 쪽으로 잘라 격자 바로 바깥(서·북)을 첫 칸으로 읽는다
        col = math.floor((lon - grid["west"]) / grid["dx"])
        row = math.floor((grid["north"] - lat) / grid["dy"])
        if not (0 <= col < grid["cols"] and 0 <= row < grid["rows"]):
            continue
        try:
            with open(root() / f"{key}.i16", "rb") as fh:
                fh.seek((row * grid["cols"] + col) * 2)
                raw = fh.read(2)
        except OSError:
            continue
        if len(raw) < 2:
            continue
        (value,) = struct.unpack("<h", raw)
        if value != NODATA:
            digits = 3 if grid["scale"] >= 1000 else 2
            out[ELEMENTS[key][2]] = round(value / grid["scale"], digits)
    return {name: out[name] for _, _, name in ELEMENTS.values() if name in out}
