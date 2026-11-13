"""덧붙이 — 다른 저장소의 Django 앱을 GSM 에 얹는 이음매 (wetherilli P19·446).

GSM 은 덧붙이가 무엇인지 모른다. `GSM_ADDONS` 에 적힌 패키지가 **아래 이름의 것을 갖고 있으면** 싣는다 — 없으면 건너뛴다.
덧붙이가 없으면(`settings.ADDONS` 가 비면) 이 파일의 손은 모두 빈 것을 돌려주고 GSM 은 전과 한 글자도 다르지 않게 돈다.

| 덧붙이 패키지 안의 것 | GSM 이 하는 일 | 읽는 자리 |
|---|---|---|
| `urls.py` | `<접두사>x/<이름>/` 에 건다 | `gsmweb/urls.py` |
| `REGISTRY = ` 가 든 파일 | 문으로 긁는다(`doors.py` 의 꼴 그대로) | `doors._modules` |
| 그 파일의 `SETS`·`legend()` | 칠해 잘라 둔 남극 격자로 낸다(`polargrid.Set`) | `views.POLAR_SETS` |
| `data/*_layers.json` | 카탈로그 씨앗 — `_지역`·`_상류` 를 꼭 적는다 | `seed_catalog` |
| `i18n.py` 의 `EN`·`PROP_EN`·`LAYER_EN`·`GROUP_EN`·`ABSTRACT_EN` | GSM 의 표에 합친다 — 같은 열쇠는 GSM 것이 이긴다 | `apps.ready` |
| `datastatus.py` 의 `ITEMS` | 구운 자료의 표에 덧붙인다 | `apps.ready` |
| `static/<이름>/map.js`·`map.css` | 지역 지도(`map.html`)가 제 `map.js`·`map.css` 뒤에 싣는다 — 손은 `window.GSMScreen`(`map.js`, wetherilli 447·448) | `context.profile` |
| 문 파일 `SETS` 의 `Set.along` | 누른 자리에 함께 낼 다른 판의 이름들 | `views.polargrid_info` |
| 문 파일의 `POINTS`·`points(name, lang, request)` | 점 레이어 — 카탈로그 행(`kind: points`)과 `points/` 의 덩이. 덩이는 담지 않는다(no-store) | `views.ADDON_POINTS` |
| `brand.py` 의 `BRAND` | 차림의 얼굴 — 이름·한 줄 소개(`{"ko", "en"}`)·아이콘·대기 화면의 정적 파일. 지역 지도·온 지구·3D·관리 화면의 이름과, 지역 지도의 아이콘·대기 화면 (wetherilli 453) | `context.profile` |

모델·migration·관리 명령·템플릿·정적 파일은 `INSTALLED_APPS` 에 들면 Django 가 스스로 다룬다 — 여기서 하지 않는다.
이름은 패키지 이름의 마지막 마디다(`asm` · `viewer.tests.fake_addon` → `fake_addon`).

**연 것은 약속이다** — 덧붙이가 기대는 것은 이 표와 `doors.py`·`polargrid.py` 의 꼴뿐이다. 시험(`test_addons`)이 가짜 덧붙이로
이음매마다 한 번씩 지나간다. 이음매를 고치면 그 시험이 먼저 깨져야 한다.
"""

import importlib
import importlib.util
from pathlib import Path

from django.conf import settings

#: 번역표 — 덧붙이의 `i18n.py` 가 같은 이름으로 두면 합친다
I18N_TABLES = ("EN", "PROP_EN", "LAYER_EN", "GROUP_EN", "ABSTRACT_EN")


def names() -> tuple:
    return tuple(getattr(settings, "ADDONS", ()) or ())


def short(package: str) -> str:
    return package.rsplit(".", 1)[-1]


def folder(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise ImportError(f"덧붙이 {package} 를 찾지 못했다 — GSM_ADDONS 와 파이썬 경로를 본다")
    return Path(list(spec.submodule_search_locations)[0])


def _part(package: str, name: str):
    """덧붙이의 `<name>.py` — 없으면 None. 있는데 깨졌으면 그대로 터뜨린다(조용히 빼먹지 않게)."""
    if importlib.util.find_spec(f"{package}.{name}") is None:
        return None
    return importlib.import_module(f"{package}.{name}")


def door_modules():
    """`REGISTRY = ` 가 든 덧붙이 파일 — `doors._modules` 가 제 것 뒤에 잇는다. 글자로 먼저 찾는 것도 같다."""
    for package in names():
        for path in sorted(folder(package).glob("*.py")):
            if "\nREGISTRY = " in path.read_text(encoding="utf-8"):
                yield importlib.import_module(f"{package}.{path.stem}")


def seeds() -> list:
    """덧붙이의 카탈로그 씨앗 — (경로, 이름표). `seed_catalog` 가 제 씨앗 뒤에 넣는다."""
    out = []
    for package in names():
        for path in sorted((folder(package) / "data").glob("*_layers.json")):
            out.append((path, f"덧붙이 {short(package)} ({path.stem})"))
    return out


def urlpatterns(prefix: str) -> list:
    """덧붙이의 주소 — `<접두사>x/<이름>/`. `x/` 밑에 모아 GSM 의 주소와 부딪히지 않게 한다."""
    from django.urls import include, path
    return [path(f"{prefix}x/{short(package)}/", include(f"{package}.urls"))
            for package in names() if _part(package, "urls") is not None]


def merge() -> None:
    """번역표와 구운 자료의 표를 합친다 — 앱이 뜰 때 한 번(`apps.ready`). 같은 열쇠·같은 줄은 GSM 것을 둔다."""
    if not names():
        return
    from . import datastatus, i18n
    for package in names():
        table = _part(package, "i18n")
        for name in I18N_TABLES if table else ():
            for key, value in (getattr(table, name, None) or {}).items():
                getattr(i18n, name).setdefault(key, value)
        status = _part(package, "datastatus")
        have = {item.key for item in datastatus.ITEMS}
        for item in (getattr(status, "ITEMS", None) or ()) if status else ():
            if item.key not in have:
                datastatus.ITEMS.append(item)
                have.add(item.key)


#: 차림의 얼굴 — 이름·아이콘·대기 화면. 덧붙이의 `brand.py` 가 `BRAND` 에 같은 열쇠를 두면 그 값으로 바뀐다 (wetherilli 453)
BRAND = {
    "name": {"ko": "대돌여지도", "en": "Great Stone Map"},
    "tagline": {"ko": "GREAT STONE MAP", "en": "대돌여지도"},
    "emblem": "viewer/emblem.svg",                    # 정적 파일의 길 — 숨은 차림 단추·설정 제목·브라우저 탭
    "emblem_polar": "viewer/emblem-polar.png",        # 극지(평사도법으로 보는 지역)에서
    "splash_webp": "viewer/splash.webp", "splash_gif": "viewer/splash.gif",
    "splash_polar_webp": "viewer/splash-polar.webp", "splash_polar_gif": "viewer/splash-polar.gif",
}


def brand(lang: str = "ko") -> dict:
    """템플릿에 넘길 얼굴 — 이름·한 줄 소개는 그 언어의 것으로 고른다. 덧붙이가 없거나 `brand.py` 가 없으면 GSM 의 것 그대로다.
    덧붙이가 모르는 열쇠를 두면 터뜨린다(오타로 얼굴이 반만 바뀌지 않게)"""
    out = dict(BRAND)
    for package in names():
        part = _part(package, "brand")
        given = getattr(part, "BRAND", None) if part else None
        if given:
            unknown = set(given) - set(BRAND)
            if unknown:
                raise ValueError(f"덧붙이 {package} 의 BRAND 에 모르는 열쇠가 있다: {sorted(unknown)}")
            out.update(given)
    pick = "en" if lang == "en" else "ko"
    return {**out, "name": out["name"][pick], "tagline": out["tagline"][pick]}


def screen_assets() -> dict:
    """지역 지도에 실을 덧붙이의 정적 파일 — `{"scripts": ["<이름>/map.js"…], "styles": ["<이름>/map.css"…]}` (wetherilli 447).
    이름은 정해 두었다(`static/<이름>/map.js`·`map.css`) — 있으면 싣고 없으면 건너뛴다. 덧붙이가 없으면 둘 다 빈 목록이다."""
    out = {"scripts": [], "styles": []}
    for package in names():
        base = folder(package) / "static" / short(package)
        if (base / "map.js").is_file():
            out["scripts"].append(f"{short(package)}/map.js")
        if (base / "map.css").is_file():
            out["styles"].append(f"{short(package)}/map.css")
    return out
