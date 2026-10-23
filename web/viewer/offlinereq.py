"""오프라인 묶음 굽기 요청 — 고를 수 있는 레이어, 요청 박스 검사, 일꾼 띄우기와 한 번에 하나의 잠금 (wetherilli P16·408). 문이 아니다.

요청 한 줄은 `models.OfflinePackRequest`, 굽는 것은 `manage.py build_offline_pack --queue` 다. 화면(`/GSM/offline/request/`)과
관리 화면의 "오프라인 묶음" 탭이 이것을 부른다.

- **박스는 도폭 하나 크기까지**(한 변 `MAX_SIDE`°, 사람, 2026-10-21) — 5만 도폭이 0.25° × 0.17° 이고 둘레 0.02° 를 더한다
- **레이어는 카탈로그에서 자유롭게**(사람, 2026-10-21) — 켜진 한국 KIGAM 타일 레이어와 VWorld 배경, 레이어마다 화면 줌 `[처음, 마지막]`
- 예산은 묶음 하나 200 MB 그대로다 — 넘으면 뒤의 레이어부터 마지막 줌이 덜린다(요청 화면의 어림이 미리 보인다)
"""
import fcntl
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

from . import vworld

MAX_SIDE = 0.3                 # 박스 한 변(°) — 도폭 하나와 둘레
KOREA = (124.0, 32.5, 132.5, 43.5)
ZOOMS = (6, 16)                # 고를 수 있는 화면 줌 — 더 가까이는 화면이 마지막 줌을 늘려 그린다(405)
MAX_LAYERS = 16
BUDGET_MB = 200
#: 누른 자리의 속성(지층 면)을 담을 수 있는 레이어 — 굽는 명령의 `layer_units` 가 아는 것(wetherilli 384)
UNIT_LAYERS = ("L_50K_Geology_Map", "L_250K_Geology_Map", "L_1M_Geology_Map")
#: 처음 고른 것과 줌 — 진교·사천 묶음(406)의 세트. 그 밖의 레이어는 끈 채 `DEFAULT_ZOOMS` 로 보인다
PRESET = {"L_50K_Geology_Map": [10, 16], "L_250K_Geology_Map": [10, 13], "L_1M_Geology_Map": [10, 11],
          "l_50k_geology_frame_latest": [10, 13], "vworld:Base": [10, 15], "vworld:Satellite": [10, 15], "vworld:Hybrid": [10, 15]}
DEFAULT_ZOOMS = [10, 13]
VWORLD_TITLES = {"Base": "VWorld 배경", "white": "VWorld 흰 배경", "midnight": "VWorld 밤 배경",
                 "Satellite": "VWorld 위성", "Hybrid": "VWorld 지명(위성 겹)"}


def kigam_layers() -> list:
    """고를 수 있는 KIGAM 레이어 — 켜진 한국 레이어 가운데 타일인 것. `[(이름, 제목, 레이어군)]`, 카탈로그 차례"""
    from .management.commands.prewarm import WmsPlan, plan_for
    from .models import Layer
    rows = (Layer.objects.filter(upstream="kigam", enabled=True, group__region="korea")
            .exclude(kind__in=("vector", "points")).select_related("group").order_by("group__order", "group__name", "id"))
    return [(r.name, r.title, r.group.name) for r in rows if isinstance(plan_for(r.name, "kigam"), WmsPlan)]


def choices() -> list:
    """요청 화면의 레이어 목록 — `[{name, title, group, first, last, on, units}]`. 앞에 둔 것이 앞설 차례다(예산은 뒤에서부터 덜린다)."""
    rows = [{"name": n, "title": t, "group": g} for n, t, g in kigam_layers()]
    rows += [{"name": f"vworld:{k}", "title": VWORLD_TITLES.get(k, f"VWorld {k}"), "group": "VWorld"} for k in vworld.WMTS_LAYERS]
    for row in rows:
        zooms = PRESET.get(row["name"], DEFAULT_ZOOMS)
        row.update(first=zooms[0], last=zooms[1], on=row["name"] in PRESET, units=row["name"] in UNIT_LAYERS)
    # 지질도 → 도폭 틀 → VWorld → 그 밖 (스킬 1 절의 차례) — 처음 고른 것이 앞에 오게
    order = list(PRESET)
    return sorted(rows, key=lambda r: (order.index(r["name"]) if r["name"] in order else len(order)))


def clean(data) -> tuple:
    """요청한 것 → `(박스, 오류 문장)`. 오류가 있으면 박스는 None. 오류 문장은 `i18n.msg` 의 것이다(화면이 옮긴다)."""
    from .i18n import msg
    if not isinstance(data, dict):
        return None, msg("요청을 읽지 못했다")
    title = str(data.get("title") or "").strip()[:60]
    try:
        w, s, e, n = (float(v) for v in data.get("bbox") or ())
    except (TypeError, ValueError):
        return None, msg("범위는 서·남·동·북 네 수다")
    if not (w < e and s < n):
        return None, msg("범위는 서·남·동·북 네 수다")
    if e - w > MAX_SIDE + 1e-9 or n - s > MAX_SIDE + 1e-9:
        return None, msg("범위가 너무 넓다 — 도폭 하나 크기(한 변 0.3°)까지다")
    if w < KOREA[0] or s < KOREA[1] or e > KOREA[2] or n > KOREA[3]:
        return None, msg("한국 밖이다 — 지금은 KIGAM·VWorld 만 굽는다")
    known = {r["name"] for r in choices()}
    layers = {}
    for name, zooms in (data.get("layers") or {}).items():
        if name not in known:
            return None, msg("굽지 못하는 레이어가 있다")
        try:
            first, last = int(zooms[0]), int(zooms[1])
        except (TypeError, ValueError, IndexError, KeyError):
            return None, msg("줌은 처음·마지막 두 수다")
        if not (ZOOMS[0] <= first <= last <= ZOOMS[1]):
            return None, msg("줌은 처음·마지막 두 수다")
        layers[name] = [first, last]
    if not layers:
        return None, msg("레이어를 하나 넘게 고른다")
    if len(layers) > MAX_LAYERS:
        return None, msg("레이어가 너무 많다")
    # 차례는 화면에서 고른 차례가 아니라 정한 차례(`choices`) — 지질도가 VWorld 보다 앞서야 예산이 지질도를 지킨다
    order = [r["name"] for r in choices()]
    layers = {k: layers[k] for k in sorted(layers, key=order.index)}
    box = {"title": title or f"{(w + e) / 2:.3f}°E {(s + n) / 2:.3f}°N", "region": "korea",
           "bbox": [round(w, 5), round(s, 5), round(e, 5), round(n, 5)], "layers": layers,
           "units": [k for k in UNIT_LAYERS if k in layers], "budget_mb": BUDGET_MB}
    return box, None


# ── 일꾼 ─────────────────────────────────────────────────────────────
#
# 승인하면 웹이 `build_offline_pack --queue` 를 떨어진 프로세스로 띄운다. 일꾼은 잠금을 쥐고 승인된 것을 하나씩 굽다가 남은 것이 없으면
# 끝난다. 이미 하나가 돌면 새로 띄운 것은 잠금을 못 쥐고 곧장 끝난다 — 도는 것이 새 승인까지 집어 간다. 컨테이너가 뜰 때도 한 번 띄운다
# (`entrypoint-web.sh`) — 배포로 끊긴 "굽는 중" 을 이어 굽는다(받은 것은 parts.sqlite 가 안다). 호스트 cron 에 두지 않는다(호스트는 GSM.db 를 열지 않는다).

def queue_dir() -> Path:
    return Path(settings.OFFLINE_DIR)


@contextmanager
def queue_lock():
    """한 번에 하나 — 쥐면 True, 다른 일꾼이 쥐고 있으면 False. 프로세스가 죽으면 잠금도 풀린다(flock)."""
    path = queue_dir() / ".queue.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def spawn() -> None:
    """일꾼을 떨어뜨려 띄운다 — 셸이 뒤로 보내고 곧장 끝나 웹 워커의 자식으로 남지 않는다(좀비가 생기지 않게). 기록은 `<OFFLINE_DIR>/.queue.log`"""
    queue_dir().mkdir(parents=True, exist_ok=True)
    log = queue_dir() / ".queue.log"
    manage = Path(settings.BASE_DIR) / "manage.py"
    subprocess.run(["sh", "-c", 'nohup "$0" "$1" build_offline_pack --queue >> "$2" 2>&1 < /dev/null &',
                   sys.executable, str(manage), str(log)], cwd=settings.BASE_DIR, env=os.environ.copy(), check=False, timeout=10)
