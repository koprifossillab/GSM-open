"""받은 원본을 날짜 폴더에 — 바뀐 판만, 최근 몇 벌만 (jikhanjung P02 4 단계).

**문이 아니다.** 받는 일(문)이 넘긴 본문을 `<자리>/<YYYYMMDD>/` 에 적고 `manifest.json` 을 단다. kigam50k 가 처음 세운 틀(jikhanjung P01 §4)을
뽑아 다른 데이터소스도 쓰게 했다.

- **바뀐 판만** — 파일마다 본문(풀린 것)의 sha256 이 가장 새 폴더의 매니페스트와 **모두 같으면 새 폴더를 만들지 않고** 그 매니페스트에
  확인한 때(`checked`)만 보탠다. 기록 표에는 `changed=0`
- 쓰는 동안은 `.<날짜>.part` 에 적고 다 적은 뒤에 이름을 바꾼다 — 반쪽 판이 가장 새 폴더가 되지 않게. 같은 날 두 번째는 새로 받은 것이 이긴다
- **지우기는 `prune()` 만** — 받는 일은 지우지 않는다. 사람이 `manage.py prune_raw` 로 부른다(cron 에 두지 않는다)
- 날짜 폴더는 이름이 여덟 자리 숫자이고 **`manifest.json` 이 든 것**뿐이다 — 이 틀이 만든 판만 센다. 구운 산출물도 날짜 폴더일 수 있어서다
  (ERA5 의 `wind/era5/20050601/` — 명세의 `raw` 를 잘못 적으면 `prune_raw` 가 그것을 지운다, #379 검토). 다른 것은 세지도 지우지도 않는다
"""
import gzip
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from django.conf import settings

from . import fetchlog

DAY = re.compile(r"^\d{8}$")
#: `prune_raw` 가 기본으로 남기는 벌 수 (사람, 2026-10-06)
KEEP = 3
#: 같은 판일 때 매니페스트에 남기는 확인한 때 — 가장 최근 것만 (#379 검토). 모두 몇 번이었는지는 `checked_count`
CHECKED_KEEP = 30


def resolve(raw: str) -> Path:
    """명세의 `raw`(`<DB 옆>` 아래 자리)를 디스크의 자리로. 첫 마디가 설정의 `<이름>_DIR` 이면 그 자리를 따른다 —
    `kigam50k/raw` 는 `KIGAM50K_DIR/raw`, `earth/…` 는 `EARTH_DIR/…`. 운영에서 자리를 옮겨도 맞게"""
    head, _, rest = raw.strip("/").partition("/")
    base = getattr(settings, f"{head.upper()}_DIR", None)
    if isinstance(base, (str, Path)) and str(base):
        return Path(base) / rest if rest else Path(base)
    return Path(settings.DATABASES["default"]["NAME"]).parent / raw.strip("/")


def label(path) -> str:
    """기록 표·화면에 적을 원본의 자리 — `<DB 옆>` 아래 이름. 그 밖이면 파일 이름만 — 절대 경로를 남기지 않는다"""
    try:
        return str(Path(path).resolve().relative_to(Path(settings.DATABASES["default"]["NAME"]).resolve().parent))
    except ValueError:
        return Path(path).name


def versions(folder: Path) -> list:
    """날짜 폴더들 — 옛 것부터. 이 틀이 만든 판(`manifest.json` 이 든 것)만"""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and DAY.match(p.name) and (p / "manifest.json").is_file())


def latest(folder: Path):
    found = versions(folder)
    return found[-1] if found else None


def is_dated(folder: Path) -> bool:
    return bool(versions(folder))


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data):
    """임시 파일에 적고 바꿔치기 — 가장 새 판의 매니페스트를 고쳐 쓰다 끊겨도 깨지지 않게 (#379 검토)"""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o664)
    os.replace(tmp, path)


def save(folder: Path, entries: dict, meta: dict, now, key: str = "files", where: str = "") -> tuple:
    """원본 한 벌을 적는다. 돌려주는 것 — (그 폴더, 새로 적었나).

    `entries` 는 {이름: {"file": 파일 이름, "body": bytes, …덧붙일 칸}}. 파일 이름이 `.gz` 로 끝나면 gzip 으로 적는다. sha256 은 풀린 본문의 것.
    매니페스트에는 `meta` 와 `{key: {이름: {file, bytes, sha256, …}}}`. `where` 는 기록 표의 `raw_path` 앞머리(`<DB 옆>` 아래 자리).
    """
    folder = Path(folder)
    rows = {}
    for name, entry in entries.items():
        body = entry["body"]
        rows[name] = {**{k: v for k, v in entry.items() if k != "body"}, "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest()}
    whole = hashlib.sha256("".join(rows[n]["sha256"] for n in sorted(rows)).encode()).hexdigest()
    prefix = (where or label(folder)).rstrip("/")

    prev = latest(folder)
    manifest = _read(prev / "manifest.json") if prev else None
    old = (manifest or {}).get(key) or {}
    if manifest and set(old) == set(rows) and all(old[n].get("sha256") == rows[n]["sha256"] for n in rows):
        checked = manifest.get("checked", []) + [now.isoformat(timespec="seconds")]
        manifest["checked_count"] = int(manifest.get("checked_count", len(manifest.get("checked", [])))) + 1
        manifest["checked"] = checked[-CHECKED_KEEP:]
        _write_json(prev / "manifest.json", manifest)
        fetchlog.note(raw_path=f"{prefix}/{prev.name}", raw_sha256=whole, changed=0)
        return prev, False

    day = now.strftime("%Y%m%d")
    work = folder / f".{day}.part"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for name, entry in entries.items():
        path = work / entry["file"]
        opener = gzip.open if entry["file"].endswith(".gz") else open
        with opener(path, "wb") as fh:
            fh.write(entry["body"])
        os.chmod(path, 0o664)
    _write_json(work / "manifest.json", {**meta, "fetched_at": now.isoformat(timespec="seconds"), key: rows})
    dest = folder / day
    if dest.exists():                     # 같은 날 두 번째 — 새로 받은 것이 이긴다
        shutil.rmtree(dest)
    work.rename(dest)
    # 바뀐 파일의 수 — 앞 판이 없으면 모두
    changed = sum(1 for n in rows if old.get(n, {}).get("sha256") != rows[n]["sha256"]) + sum(1 for n in old if n not in rows)
    fetchlog.note(raw_path=f"{prefix}/{day}", raw_sha256=whole, changed=changed)
    return dest, True


def prune(folder: Path, keep: int = KEEP, dry_run: bool = False) -> list:
    """최근 `keep` 벌만 남기고 옛 날짜 폴더를 지운다. 지운(지울) 폴더들. 가장 새 것은 `keep` 이 0 이어도 남긴다."""
    found = versions(folder)
    keep = max(1, int(keep))
    old = found[:-keep] if len(found) > keep else []
    if not dry_run:
        for path in old:
            shutil.rmtree(path)
    return old


def file_sha256(path: Path) -> str:
    """파일째 sha256 — 몇십 MB 까지의 원본에. PBDB(150 MB)처럼 큰 것은 받을 때 셈한다(`pbdb.download(digest=…)`)"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
