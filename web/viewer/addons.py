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
