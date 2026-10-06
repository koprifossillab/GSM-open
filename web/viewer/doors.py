"""상류의 문을 모은다 — 문마다 제 파일 끝에 `REGISTRY` 를 적고, 여기가 그것을 긁어 표를 짓는다 (wetherilli 371).

상류 하나를 더할 때 고칠 자리가 공유하는 긴 줄에 흩어져 있었다 — views 의 import·오류 튜플·문 표·열쇠 없는 상류·3D 목록,
prewarm 의 `PROJECTED`, map.js 의 딱지·기관 이름·그리는 손. 세션 여럿이 같은 줄 끝에 이름을 붙여 PR 마다 부딪혔다.
이제 새 문은 **제 파일만** 고친다 — 이 파일도, 위의 표도 손대지 않는다.

`REGISTRY` 는 상류마다 dict 하나다.

| 열쇠 | 뜻 |
|---|---|
| `upstream` | `Layer.upstream` 의 이름 |
| `tag` · `title` | 레이어 패널의 딱지(기관 약자, 옮기지 않는다)와 기관 이름(한국어 원문 — 영어는 `i18n.EN`) |
| `relay` | `wms/`·`featureinfo/`·`legend/` 가 이 상류를 이 문으로 중계한다. `True` 면 그 파일이, 아니면 준 객체가 문이다 |
| `projected` | 화면이 카탈로그 행의 투영으로 문을 거쳐 받는다(`map.js` 의 `npolarSource`), 미리 데우기도 그 길로 |
| `globe` | 3D 가 `wms/` 의 3857 타일로 얹는다 |
| `ready` | 쓸 수 있는지 묻는 함수 — 없으면 열쇠가 없는 공개 서비스라 늘 된다 |
| `local` | 상류가 아니라 우리 디스크의 파일이다 — 속성·범례를 캐시에 담지 않는다 |

파일을 import 하기 전에 글자로 `REGISTRY =` 를 찾는다 — 호스트에서만 도는 문(numpy 따위)을 컨테이너에서 부르지 않게.
"""

import functools
import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Spec:
    upstream: str
    module: object
    tag: str = ""
    title: str = ""
    relay: object = None
    projected: bool = False
    globe: bool = False
    ready: object = None
    local: bool = False


def _modules():
    here = Path(__file__).parent
    for path in sorted(here.glob("*.py")):
        if path.stem == "doors":
            continue
        if "\nREGISTRY = " not in path.read_text(encoding="utf-8"):
            continue
        yield importlib.import_module(f".{path.stem}", __package__)


@functools.lru_cache(maxsize=None)
def specs() -> dict:
    """상류 이름 -> `Spec`. 둘이 같은 이름을 적으면 멈춘다 — 조용히 하나를 덮지 않게."""
    out = {}
    for module in _modules():
        for row in module.REGISTRY:
            row = dict(row)
            relay = row.pop("relay", None)
            name = row["upstream"]
            if name in out:
                raise ValueError(f"상류 {name} 를 두 파일이 적었다: {out[name].module.__name__}, {module.__name__}")
            out[name] = Spec(module=module, relay=module if relay is True else relay, **row)
    return out


def relays() -> dict:
    """중계하는 문 — 상류 이름 -> get_map·get_feature_info·get_legend 를 가진 것."""
    return {name: spec.relay for name, spec in specs().items() if spec.relay is not None}


def errors() -> tuple:
    """`REGISTRY` 를 둔 파일이 정의한 예외 전부 — 상류가 못 줄 때 옛것·안내 타일로 돌리는 `except` 가 쓴다.
    중계하지 않는 문(BAS 범례 따위)의 것도 든다 — 범례·속성 길이 같은 튜플로 받는다."""
    found = []
    for module in sorted({spec.module for spec in specs().values()}, key=lambda m: m.__name__):
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Exception) and obj.__module__ == module.__name__ and obj not in found:
                found.append(obj)
    return tuple(found)


def names(flag: str) -> tuple:
    """`projected`·`globe` 따위가 선 상류 이름."""
    return tuple(sorted(name for name, spec in specs().items() if getattr(spec, flag)))


def client(lang: str = "ko") -> dict:
    """화면에 실을 표 — 상류 이름 -> [딱지, 기관 이름, 투영으로 받나]. 기관 이름은 화면이 `T()` 로 옮긴다."""
    return {name: [spec.tag, spec.title, spec.projected] for name, spec in specs().items()}
