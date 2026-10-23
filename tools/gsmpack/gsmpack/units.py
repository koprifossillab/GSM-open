"""지층 면 — WFS GeoJSON 을 묶음에 넣을 면으로 (wetherilli 384·385, P16 에서 `build_offline_pack.unit_features` 를 옮겼다).

속성의 손질은 부르는 쪽이 넘긴다(`tidy(props) → (props, props_en)`). GSM 은 서버의 `feature_info` 손질(링크 가르기·영어판)을 넘기고,
혼자 굽는 쪽은 `plain` — 링크만 가르고 영어판은 두지 않는다(화면은 영어판이 없으면 한국어를 낸다).
"""
import re

from . import clip

_ANCHOR = re.compile(r"""<a\s[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def split_links(value):
    """속성값에 섞여 온 `<a>` 를 `{text, links}` 로 — `viewer.views._split_links` 를 옮겼다. 주소는 http·https 만."""
    if not isinstance(value, str) or "<a" not in value.lower():
        return value
    links = []

    def take(match):
        url = match.group(1).strip()
        label = _TAG.sub("", match.group(2)).strip()
        if not url.lower().startswith(("http://", "https://")):
            return label
        links.append({"label": (label or "열기")[:40], "url": url})
        return ""

    text = _TAG.sub("", _ANCHOR.sub(take, value)).strip()
    if not links:
        return text or value
    return {"text": text, "links": links}


def plain(props):
    """혼자 굽는 쪽의 손질 — 링크만 가른다."""
    return {k: split_links(v) for k, v in props.items()}, None


def features(data: dict, bbox=None, tidy=plain) -> list:
    """WFS GeoJSON → 묶음에 넣을 면. 빈 값을 버리고, `bbox` 가 있으면 그 네모로 잘라 낸다(wetherilli 385)."""
    out = []
    for feature in data.get("features") or []:
        geometry = feature.get("geometry") or {}
        if "Polygon" not in geometry.get("type", ""):
            continue
        if bbox:
            geometry = clip.clip_polygons(geometry, bbox)
            if geometry is None:
                continue
        props = {k: v for k, v in (feature.get("properties") or {}).items() if v not in (None, "", "null")}
        if not props:
            continue
        props, props_en = tidy(props)
        properties = {"props": props}
        if props_en is not None:
            properties["props_en"] = props_en
        out.append({"type": "Feature", "geometry": {"type": geometry["type"], "coordinates": clip.round_coords(geometry["coordinates"])},
                    "properties": properties})
    return out
