"""올린 파일을 점묶음으로 읽는다. CSV 와 GeoJSON 둘뿐이다.

GeoJSON 은 **점·선·면을 다 받는다** (v0.5.1). 선·면은 `"geometry"` 를 단
항목으로 돌려주고, 뷰가 그것을 `Shape` 로 담는다. 점은 예전 그대로다.

**열 이름을 사람이 고르게 하지 않는다.** 위경도 열은 이름으로 알아낸다 —
현장에서 쓰는 표는 열 이름이 제각각이라(`lat`·`위도`·`Y`) 고르라고 물으면
올릴 때마다 묻게 된다. 못 알아내면 그때만 까닭을 적어 돌려준다.
"""
import csv
import io
import json
import re

from . import coords, crs
from .i18n import msg

#: 위도로 읽는 열 이름. 소문자로 견준다.
LAT_KEYS = ("lat", "latitude", "위도", "y", "lat_dd", "dd_lat", "북위")
LON_KEYS = ("lon", "lng", "long", "longitude", "경도", "x", "lon_dd", "dd_lon", "동경")
#: 이름표로 쓸 열. 없으면 이름표 없이 둔다.
LABEL_KEYS = ("label", "name", "이름", "이름표", "지점", "지점명", "site", "station", "id",
              "시료", "시료번호", "시료명", "sample", "sample_id", "sample_no")
#: 주소로 읽는 열 (wetherilli 152). 위경도 열이 없고 이것이 있으면 화면이 VWorld 로 주소를 찾아 좌표를 붙인다
ADDRESS_KEYS = ("주소", "address", "addr", "도로명주소", "지번주소", "소재지", "소재지주소", "도로명", "지번",
                "채취지", "채취지 주소", "location")
#: 한 번에 주소로 찾는 줄의 한도 — 화면이 50 줄씩 나눠 묻는다. VWorld 지오코더는 하루 호출 수가 정해져 있다
MAX_ADDRESS_ROWS = 2000
#: 평면 좌표계일 때 읽는 열. **열 이름을 먼저 믿는다** — 중부원점에서는 동·북을
#: 뒤바꿔도 둘 다 한반도 안(부산 앞바다 같은 곳)에 떨어지는 일이 있어, 값만
#: 보고는 가를 수 없다.
#: - 동·북이 이름에 드러난 열은 이름 그대로
#: - `X좌표`·`Y좌표` 는 측량 관례 — X 가 북쪽이다
#: - 그냥 `x`·`y` 는 GIS 관례 — x 가 동쪽. 한반도 밖에 떨어질 때만 뒤집는다
PLANAR_PAIRS = (
    ("named", ("e", "east", "easting", "동", "동거"), ("n", "north", "northing", "북", "북거")),
    ("survey", ("y좌표",), ("x좌표",)),
    ("gis", ("x", "tm_x"), ("y", "tm_y")),
)
EAST_KEYS = tuple(k for _, east, _ in PLANAR_PAIRS for k in east)
NORTH_KEYS = tuple(k for _, _, north in PLANAR_PAIRS for k in north)


#: 선·면을 받는 GeoJSON 갈래. 여러 겹(Multi*)도 한 모양으로 둔다.
SHAPE_KINDS = {"LineString": "line", "MultiLineString": "line",
               "Polygon": "polygon", "MultiPolygon": "polygon"}
#: 꼭짓점 한도. 행정경계 한 장을 통째로 올리면 수십만 개다 — 그런 것은
#: 이 뷰어가 그릴 것이 아니라 상류 레이어로 볼 것이다.
MAX_VERTICES_PER_SHAPE = 50_000
MAX_VERTICES_TOTAL = 300_000


class UploadError(ValueError):
    """올린 것을 점묶음으로 읽지 못했을 때. 메시지는 사람에게 그대로 보인다."""


class NeedsAddresses(Exception):
    """위경도 열은 없고 주소 열이 있다 (wetherilli 152). 뷰가 줄들을 화면에 돌려주고, 화면이 주소를 찾아 좌표를 붙여 다시 올린다.

    `fields` 는 열 이름 차례, `column` 은 주소 열, `rows` 는 `{"line", "address", "values"}`, `blank` 는 주소가 빈 줄 번호다."""

    def __init__(self, fields, column, rows, blank):
        super().__init__(column)
        self.fields, self.column, self.rows, self.blank = list(fields), column, rows, blank


def parse(filename: str, raw: bytes, crs_code: str = "4326", *, lunar: bool = False):
    """(점 목록, 알림 목록) 을 돌려준다. 점 하나는 dict 다.

    `crs_code` 는 사람이 고른 좌표계다. GeoJSON 이 스스로 `crs` 를 밝히면
    그쪽이 이긴다.

    `lunar` 면 달(화성도, 058) 경위도로만 읽는다(devlog 037) — 평면 좌표계(TM·UTM-K …)는 지구의 것이라
    고른 것도 GeoJSON 이 밝힌 것도 듣지 않는다.
    """
    text = _decode(raw)
    if lunar:
        crs_code = "4326"
    if filename.lower().endswith((".geojson", ".json")) or text.lstrip().startswith("{"):
        return _from_geojson(text, crs_code, ignore_declared=lunar)
    if crs.is_planar(crs_code):
        return _from_csv_planar(text, crs_code)
    return _from_csv(text)


def _decode(raw: bytes) -> str:
    """한글이 든 CSV 는 UTF-8 이거나 CP949 다. BOM 도 흔하다."""
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadError(msg("글자를 읽지 못했다. UTF-8 이나 CP949 로 저장해 다시 올린다."))


def _pick(fieldnames, wanted):
    lowered = {(f or "").strip().lower(): f for f in fieldnames}
    for key in wanted:
        if key in lowered:
            return lowered[key]
    return None


def _from_csv(text: str):
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel                       # 열 하나뿐이면 재지 못한다
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise UploadError(msg("첫 줄에 열 이름이 없다."))

    lat_col = _pick(reader.fieldnames, LAT_KEYS)
    lon_col = _pick(reader.fieldnames, LON_KEYS)
    address_col = _pick(reader.fieldnames, ADDRESS_KEYS)
    if (not lat_col or not lon_col) and address_col:
        rows, blank = [], []
        for lineno, row in enumerate(reader, start=2):
            address = " ".join(str(row.get(address_col) or "").split())
            if address:
                rows.append({"line": lineno, "address": address,
                             "values": {k: v for k, v in row.items() if k is not None}})
            else:
                blank.append(lineno)
        if not rows:
            raise UploadError(msg("주소 열({col})이 모두 비어 있다.", col=address_col))
        raise NeedsAddresses(reader.fieldnames, address_col, rows, blank)
    if not lat_col or not lon_col:
        raise UploadError(msg(
            "위경도 열을 찾지 못했다. 열 이름을 {lat} / {lon} 가운데 하나로 두고 "
            "다시 올린다. (읽은 열: {cols})",
            lat="·".join(LAT_KEYS[:4]), lon="·".join(LON_KEYS[:4]),
            cols=", ".join(reader.fieldnames)))
    label_col = _pick(reader.fieldnames, LABEL_KEYS)

    points, notes, skipped = [], [], 0
    for lineno, row in enumerate(reader, start=2):
        pair = _read_pair(row.get(lat_col), row.get(lon_col))
        if pair is None:
            skipped += 1
            if len(notes) < 5:
                notes.append(msg("{line}째 줄 — 좌표를 읽지 못해 건너뛰었다", line=lineno))
            continue
        lat, lon = pair
        # 위경도와 이름표로 쓴 열은 속성에서 뺀다. 넣어 두면 팝업에
        # 이름표가 두 번 뜬다 — 위에 한 번, 표 안에 또 한 번.
        used = (lat_col, lon_col, label_col)
        props = {k: v for k, v in row.items()
                 if k not in used and v not in (None, "")}
        points.append({"lat": lat, "lon": lon,
                       "label": (row.get(label_col) or "").strip() if label_col else "",
                       "props": props})

    if not points:
        if _looks_planar(reader_rows_sample(text, dialect, lat_col, lon_col)):
            raise UploadError(msg("좌표가 위경도 범위를 벗어난다. TM 좌표면 올리기 전에 좌표계를 고른다."))
        raise UploadError(msg("좌표를 하나도 읽지 못했다."))
    if skipped > len(notes):
        notes.append(msg("…모두 {n}줄을 건너뛰었다", n=skipped))
    return points, notes


def reader_rows_sample(text, dialect, a_col, b_col, n=5):
    rows = []
    for row in csv.DictReader(io.StringIO(text), dialect=dialect):
        rows.append((row.get(a_col), row.get(b_col)))
        if len(rows) >= n:
            break
    return rows


def _looks_planar(rows) -> bool:
    """위경도로 읽히지 않은 수들이 TM 처럼 큰가 (천 단위를 넘는가)."""
    for a, b in rows:
        try:
            if abs(float(a)) > 1000 and abs(float(b)) > 1000:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _from_csv_planar(text: str, code: str):
    """TM 등 평면 좌표계로 찍힌 표. 동·북 열을 찾아 위경도로 바꾼다."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise UploadError(msg("첫 줄에 열 이름이 없다."))
    a_col = b_col = rule = None
    for rule_name, east_keys, north_keys in PLANAR_PAIRS:
        a, b = _pick(reader.fieldnames, east_keys), _pick(reader.fieldnames, north_keys)
        if a and b and a != b:
            a_col, b_col, rule = a, b, rule_name
            break
    if not a_col:
        raise UploadError(msg(
            "평면 좌표 열을 찾지 못했다. 열 이름을 {east} / {north} 가운데 하나로 두고 "
            "다시 올린다. (읽은 열: {cols})",
            east="·".join(EAST_KEYS[:5]), north="·".join(NORTH_KEYS[:5]),
            cols=", ".join(reader.fieldnames)))
    label_col = _pick(reader.fieldnames, LABEL_KEYS)
    name = crs.SYSTEMS[code][0]

    points, notes, skipped, swapped_any = [], [], 0, False
    for lineno, row in enumerate(reader, start=2):
        try:
            a, b = float(str(row.get(a_col)).replace(",", "")), float(str(row.get(b_col)).replace(",", ""))
            if rule == "gis":
                got = crs.resolve(code, a, b)          # 밖이면 뒤집어 본다
            else:
                lat, lon = crs.to_latlon(code, a, b)    # 이름을 믿는다
                got = (lat, lon, False) if crs.in_korea(lat, lon) else None
        except (TypeError, ValueError, OverflowError):
            got = None
        if got is None:
            skipped += 1
            if len(notes) < 5:
                notes.append(msg("{line}째 줄 — {name} 좌표로 읽지 못해 건너뛰었다", line=lineno, name=name))
            continue
        lat, lon, swapped = got
        swapped_any = swapped_any or swapped
        used = (a_col, b_col, label_col)
        props = {k: v for k, v in row.items() if k not in used and v not in (None, "")}
        # 원래 좌표도 남긴다 — 옮긴 값만 남으면 원본과 견줄 수 없다
        props[f"{name} 동"] = row.get(b_col if swapped else a_col)
        props[f"{name} 북"] = row.get(a_col if swapped else b_col)
        points.append({"lat": round(lat, 7), "lon": round(lon, 7),
                       "label": (row.get(label_col) or "").strip() if label_col else "",
                       "props": props})
    if not points:
        raise UploadError(msg("{name} 좌표로 읽히는 줄이 없다. 좌표계를 다시 고른다.", name=name))
    # 어느 쪽으로 읽었는지 늘 말한다 — 틀리게 읽었으면 사람이 곧바로 알아야 한다
    if rule == "survey":
        notes.insert(0, msg("'{n}' 를 북쪽, '{e}' 를 동쪽으로 읽었다 (측량 관례).", n=b_col, e=a_col))
    elif swapped_any:
        notes.insert(0, msg("'{n}' 를 북쪽, '{e}' 를 동쪽으로 읽었다 (측량 관례).", n=a_col, e=b_col))
    elif rule == "gis":
        notes.insert(0, msg("'{e}' 를 동쪽, '{n}' 를 북쪽으로 읽었다. 측량 관례(X=북)면 열 이름을 "
                            "X좌표·Y좌표 로 바꿔 다시 올린다.", e=a_col, n=b_col))
    if skipped > len([n for n in notes if "째 줄" in n]):
        notes.append(msg("…모두 {n}줄을 건너뛰었다", n=skipped))
    return points, notes


def _read_pair(lat_raw, lon_raw):
    """십진도가 먼저다. 안 되면 도분초로 읽어 본다."""
    if lat_raw is None or lon_raw is None:
        return None
    lat_raw, lon_raw = str(lat_raw).strip(), str(lon_raw).strip()
    if not lat_raw or not lon_raw:
        return None
    try:
        lat, lon = float(lat_raw), float(lon_raw)
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except ValueError:
        pass
    return coords.parse(f"{lat_raw} {lon_raw}")


def _clean_coords(coords, depth, counter):
    """좌표를 숫자·범위로 걸러 소수 일곱째 자리(약 1 cm)에서 자른다.

    `depth` 는 겹 수다 — LineString 2, Polygon 3, MultiPolygon 4.
    잘못된 것이 하나라도 있으면 None.
    """
    if depth == 1:
        try:
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return None
        counter[0] += 1
        return [round(lon, 7), round(lat, 7)]
    if not isinstance(coords, list) or not coords:
        return None
    out = []
    for c in coords:
        got = _clean_coords(c, depth - 1, counter)
        if got is None:
            return None
        out.append(got)
    return out


DEPTH = {"LineString": 2, "MultiLineString": 3, "Polygon": 3, "MultiPolygon": 4}


def _shape_from(geom):
    """GeoJSON 기하 하나를 모양으로. 못 읽으면 None, 너무 크면 UploadError."""
    gtype = geom.get("type")
    counter = [0]
    coords = _clean_coords(geom.get("coordinates"), DEPTH[gtype], counter)
    if coords is None or counter[0] < 2:
        return None
    if counter[0] > MAX_VERTICES_PER_SHAPE:
        raise UploadError(msg("모양 하나의 꼭짓점이 {n}개로 너무 많다 (한도 {max}개).",
                              n=counter[0], max=MAX_VERTICES_PER_SHAPE))
    flat = []

    def walk(c):
        if isinstance(c[0], (int, float)):
            flat.append(c)
        else:
            for x in c:
                walk(x)
    walk(coords)
    lons = [c[0] for c in flat]
    lats = [c[1] for c in flat]
    return {"kind": SHAPE_KINDS[gtype],
            "geometry": {"type": gtype, "coordinates": coords},
            "lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2,
            "vertices": counter[0]}


def _label_of(props):
    for key in LABEL_KEYS:
        for prop_key, value in props.items():
            if prop_key.lower() == key:
                return str(value)
    return ""


def _declared_crs(data):
    """GeoJSON 이 스스로 밝힌 좌표계 (`"crs": {"properties": {"name": ...}}`)."""
    try:
        name = data["crs"]["properties"]["name"]
    except (KeyError, TypeError):
        return None
    m = re.search(r"EPSG:+(\d+)", str(name))
    return m.group(1) if m and m.group(1) in crs.SYSTEMS else None


def _reproject(coords, code):
    """GeoJSON 좌표(동, 북)를 위경도로. 겹이 몇이든 끝의 [x, y] 까지 내려간다."""
    if isinstance(coords, list) and coords and isinstance(coords[0], (int, float)):
        lat, lon = crs.to_latlon(code, float(coords[0]), float(coords[1]))
        return [lon, lat]
    if isinstance(coords, list):
        return [_reproject(c, code) for c in coords]
    return coords


def _from_geojson(text: str, crs_code: str = "4326", *, ignore_declared: bool = False):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UploadError(msg("GeoJSON 이 깨져 있다: {err}", err=exc)) from exc
    declared = None if ignore_declared or not isinstance(data, dict) else _declared_crs(data)
    code = declared or crs_code

    features = data.get("features") if isinstance(data, dict) else None
    if features is None:
        features = [data] if isinstance(data, dict) and data.get("type") == "Feature" else None
    if not features:
        raise UploadError(msg("GeoJSON 에 features 가 없다."))

    points, notes, skipped, vertices = [], [], 0, 0
    for feature in features:
        geom = (feature or {}).get("geometry") or {}
        if crs.is_planar(code) and geom.get("coordinates") is not None:
            try:
                geom = dict(geom, coordinates=_reproject(geom["coordinates"], code))
            except (TypeError, ValueError, IndexError, OverflowError):
                geom = {}
        gtype = geom.get("type")
        props = {k: v for k, v in ((feature or {}).get("properties") or {}).items()
                 if v not in (None, "")}
        label = _label_of(props)
        if gtype == "Point":
            try:
                lon, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                skipped += 1
                continue
            points.append({"lat": lat, "lon": lon, "label": label, "props": props})
        elif gtype == "MultiPoint":
            for c in geom.get("coordinates") or []:
                try:
                    points.append({"lat": float(c[1]), "lon": float(c[0]),
                                   "label": label, "props": props})
                except (IndexError, TypeError, ValueError):
                    skipped += 1
        elif gtype in SHAPE_KINDS:
            shape = _shape_from(geom)
            if shape is None:
                skipped += 1
                continue
            vertices += shape.pop("vertices")
            if vertices > MAX_VERTICES_TOTAL:
                raise UploadError(msg("꼭짓점이 모두 {max}개를 넘는다. 파일을 나눠 올린다.",
                                      max=MAX_VERTICES_TOTAL))
            shape.update(label=label, props=props)
            points.append(shape)
        else:
            skipped += 1

    if not points:
        raise UploadError(msg("점·선·면을 하나도 찾지 못했다."))
    if skipped:
        notes.append(msg("읽지 못한 것 {n}개를 건너뛰었다 (기하가 없거나 깨졌거나 GeometryCollection)",
                         n=skipped))
    return points, notes


#: 출처 → 높이 기준 (`elevation.SOURCES` 와 같다). 이 파일은 상류를 모르게 두려고 옮겨 적었다
ELEV_DATUMS = {"aws-terrarium-z12": "egm96", "gsi-dem-10m": "gsi-geoid",
               "pgc-arcticdem-2m": "pgc-orthometric", "pgc-rema-2m": "pgc-orthometric",
               # 달 — `trek.ELEV_SOURCE`. 반지름 1 737.4 km 구에서 잰 높이 (037)
               "lola-256ppd": "moon-sphere",
               "lola-128ppd": "moon-sphere",   # 2026-09-30 전에 채운 점 (wetherilli 083)
               # 화성 — `trek.MARS_ELEV_SOURCE`. 화성 기준면(아레오이드)에서 잰 높이 (058)
               "mola-hrsc-200m": "mars-areoid",
               # 수성 — `trek.MERCURY_ELEV_SOURCE`. 반지름 2 439.4 km 구에서 잰 높이 (wetherilli P10)
               "messenger-usgs-665m": "mercury-sphere"}


#: VWorld 둘레(074)의 이름 — `views.PLACE_PROPS` 와 같다. 이 파일은 뷰를 모르게 두려고 옮겨 적었다
_PLACE_NAMES = {"도로명(VWorld)": "road", "지번(VWorld)": "parcel", "읍면동(VWorld)": "emd",
                "보호구역(VWorld)": "protected", "지목(VWorld)": "jimok", "소유구분(VWorld)": "owner"}


def _place_from(props: dict) -> dict:
    """사본에 실린 VWorld 둘레를 떼어 `Point.place` 로 돌린다. `props` 에서 지운다."""
    place = {}
    for label, key in _PLACE_NAMES.items():
        value = props.pop(label, None)
        if value:
            place[key] = str(value)
    fault = props.pop("가까운 단층(VWorld, m)", None)
    if isinstance(fault, (int, float)):
        place["fault_m"] = round(fault)
    near = props.pop("둘레 지명(VWorld)", None)
    if isinstance(near, str) and " · " in near and near.endswith(" m"):
        name, dist = near.rsplit(" · ", 1)
        try:
            place["place"], place["place_m"] = name, int(dist[:-2])
        except ValueError:
            pass
    return place


def restore(gone):
    """지운 기록(`PointSetDeletion`)의 사본으로 점묶음을 되살린다.

    (새 점묶음, 점 수, 모양 수). 명령(`deleted_pointsets --restore`)과 화면의
    되살리기 단추가 함께 쓴다.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models import Point, PointSet, Shape

    feats = (gone.snapshot or {}).get("features") or []
    with transaction.atomic():
        ps = PointSet.objects.create(name=gone.name, color=gone.color or "#e4572e",
                                     source_filename=gone.source_filename, body=gone.body or "earth")
        points = shapes = 0
        for f in feats:
            geom = f.get("geometry") or {}
            props = dict(f.get("properties") or {})
            label = str(props.pop("이름표", ""))[:200]
            # 표고(P03)는 `props` 가 아니라 제 칸이다 — 사본에 실린 것을 떼어 돌린다
            elev, source = props.pop("표고(DEM)", None), str(props.pop("표고 출처", "") or "")
            # IBCSO 수심(070)은 부를 때마다 격자에서 읽어 붙이는 것이다 — 원본의 열이 아니다
            props.pop("해저·빙저(IBCSO)", None)
            props.pop("얼음 두께(IBCSO)", None)
            place = _place_from(props)
            if geom.get("type") == "Point":
                lon, lat = geom["coordinates"][:2]
                extra = {}
                if isinstance(elev, (int, float)) and source in ELEV_DATUMS:
                    extra = {"elev": float(elev), "elev_source": source, "elev_datum": ELEV_DATUMS[source]}
                if place:
                    extra["place"] = place
                Point.objects.create(pointset=ps, lat=lat, lon=lon, label=label, props=props, **extra)
                points += 1
            elif geom.get("type") in SHAPE_KINDS:
                s = _shape_from(geom)
                if s:
                    Shape.objects.create(pointset=ps, kind=s["kind"], geometry=s["geometry"],
                                         lat=s["lat"], lon=s["lon"], label=label, props=props)
                    shapes += 1
        gone.restored_at = timezone.now()
        gone.save(update_fields=["restored_at"])
    return ps, points, shapes
