"""KIGAM 5만 지질도의 구조 요소를 받아 `<KIGAM50K_DIR>/raw/<YYYYMMDD>/` 에 적는다 (jikhanjung P01 §4, wetherilli 199).

문(`kigam.wfs_count`·`wfs_features`)으로 레이어마다 두 번 — 센 수(`hits`)와 본문 — 요청 사이 2 초. **문서에 없는 GeoServer 주소**다
(CLAUDE.md "두 개의 상류 주소"). **사람이 가끔(반년쯤) 부른다** — 주간 백업이 다달이 부르던 것을 뺐다(사용자, 2026-10-04, wetherilli 208).

- 받은 수가 센 수와 **모두** 같을 때만 적는다. 하나라도 모자라면 아무것도 적지 않고 멈춘다 — 반쪽 판이 가장 새 폴더가 되면 안 된다
- 레이어마다 본문(풀린 GeoJSON)의 sha256 이 가장 새 폴더의 매니페스트와 **모두 같으면 새 폴더를 만들지 않고** 그 매니페스트에
  확인한 날(`checked`)만 보탠다
- 옛 날짜 폴더는 지우지 않는다 — 받아온 것은 계속 보탠다(007). 가장 새 폴더가 이긴다(`kigam50k.latest`)
"""
import gzip
import hashlib
import json
import os
import shutil
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import fetchlog, kigam, kigam50k


class Command(BaseCommand):
    help = "KIGAM 5만 구조 요소(WFS) → <KIGAM50K_DIR>/raw/<날짜>/ (jikhanjung P01 §4, wetherilli 199)"

    def add_arguments(self, parser):
        parser.add_argument("--delay", type=float, default=2.0, help="요청 사이 쉬는 초 (기본 2)")

    def handle(self, *args, **opts):
        delay = max(0.0, opts["delay"])
        now = timezone.localtime()
        got = {}
        for i, name in enumerate(kigam50k.FETCH):
            if i:
                time.sleep(delay)
            try:
                matched = kigam.wfs_count(name)
                time.sleep(delay)
                body, url = kigam.wfs_features(name)
                features = json.loads(body).get("features") or []
            except (kigam.UpstreamError, ValueError) as exc:
                raise CommandError(f"{name}: {exc} — 아무것도 적지 않았다") from exc
            if len(features) != matched:
                raise CommandError(f"{name}: 받은 수 {len(features):,} 가 센 수 {matched:,} 와 다르다 — 아무것도 적지 않았다")
            got[name] = {"typeName": kigam.wfs_type(name), "url": url, "numberMatched": matched, "received": len(features),
                         "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "file": f"{name}.geojson.gz",
                         "_body": body}
            self.stdout.write(f"  {name}: {matched:,}")

        # 기록 표에 — 상류가 센 수 대 받은 수, 원본의 판(레이어 sha 를 이은 것의 sha) (jikhanjung P02)
        fetchlog.note(expected=sum(r["numberMatched"] for r in got.values()),
                      rows=sum(r["received"] for r in got.values()),
                      raw_sha256=hashlib.sha256("".join(got[n]["sha256"] for n in sorted(got)).encode()).hexdigest())
        prev = kigam50k.latest()
        manifest = _read(prev / "manifest.json") if prev else None
        if manifest and set((manifest.get("layers") or {})) == set(got) and all(
                manifest["layers"][n].get("sha256") == got[n]["sha256"] for n in got):
            manifest.setdefault("checked", []).append(now.isoformat(timespec="seconds"))
            _write_json(prev / "manifest.json", manifest)
            fetchlog.note(raw_path=f"kigam50k/raw/{prev.name}", changed=0)
            self.stdout.write(self.style.SUCCESS(f"앞 판({prev.name})과 같다 — 새 폴더를 만들지 않고 확인한 날만 적었다"))
            return

        raw = kigam50k.root() / "raw"
        day = now.strftime("%Y%m%d")
        work = raw / f".{day}.part"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        for name, row in got.items():
            with gzip.open(work / row["file"], "wb") as fh:
                fh.write(row.pop("_body"))
            os.chmod(work / row["file"], 0o664)
        _write_json(work / "manifest.json", {
            "source": "KIGAM GeoServer WFS (문서에 없는 주소, 키 없음) — CLAUDE.md \"두 개의 상류 주소\"",
            "endpoint": kigam.wfs_url(), "fetched_at": now.isoformat(timespec="seconds"), "crs": "EPSG:4326",
            "layers": got})
        dest = raw / day
        if dest.exists():          # 같은 날 두 번째 — 새로 받은 것이 이긴다
            shutil.rmtree(dest)
        work.rename(dest)
        fetchlog.note(raw_path=f"kigam50k/raw/{day}", changed=1)        # 새 판 — 바뀐 레이어 수는 세지 않고 "바뀌었다" 만
        self.stdout.write(self.style.SUCCESS(f"레이어 {len(got)} 개 → {dest}"))


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o664)
