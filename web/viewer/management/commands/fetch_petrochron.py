"""PetroChron Antarctica 를 받아 `<PETROCHRON_DIR>/raw/<날짜>/` 에 두고 점 한 덩이로 굽는다 (wetherilli 419).

문(`petrochron.py`)으로 Zenodo 의 파일 둘(엮은 표 9 MB·참고문헌 0.8 MB)을 1 초 간격으로 받는다. 원본은 `rawstore` 가 날짜 폴더에 —
판이 같으면 확인한 때만 보탠다. 2021 년 판에서 멈춘 자료라 cron 에 두지 않고 사람이 부른다.

    manage.py fetch_petrochron            받고 굽는다
    manage.py fetch_petrochron --offline  받지 않고 가장 새 원본에서 다시 굽는다(굽는 법을 고쳤을 때)
"""
import gzip
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import fetchlog, petrochron, rawstore


class Command(BaseCommand):
    help = "PetroChron Antarctica → <PETROCHRON_DIR>/petrochron.json (wetherilli 419)"

    def add_arguments(self, parser):
        parser.add_argument("--offline", action="store_true", help="받지 않고 가장 새 원본에서 다시 굽는다")

    def handle(self, *args, **opts):
        raw = petrochron.data_dir() / "raw"
        if opts["offline"]:
            folder = rawstore.latest(raw)
            if not folder:
                raise CommandError(f"받아 둔 원본이 없다 — {raw}")
            bodies = {key: _read(folder / f"{key}.{ext}.gz") for key, ext in (("db", "csv"), ("refs", "bib"))}
        else:
            self.stdout.write("Zenodo 에서 PetroChron Antarctica 를 받는다 …")
            try:
                bodies = petrochron.download()
            except petrochron.PetroChronError as exc:
                raise CommandError(str(exc)) from exc
            entries = {key: {"file": f"{key}.{ext}.gz", "from": name, "body": bodies[key]}
                       for (key, name), ext in zip(petrochron.FILES, ("csv", "bib"))}
            folder, fresh = rawstore.save(raw, entries, {"source": petrochron.RECORD, "license": petrochron.LICENSE},
                                          timezone.now(), where="petrochron/raw")
            self.stdout.write(f"원본 → {folder}" + ("" if fresh else " (같은 판, 확인한 때만 보탰다)"))
        try:
            data = petrochron.build(bodies["db"], bodies["refs"])
        except (petrochron.PetroChronError, UnicodeDecodeError) as exc:
            raise CommandError(str(exc)) from exc
        dest = petrochron.save(data)
        features = data["features"]
        dated = sum(1 for f in features if "age" in f["properties"])
        linked = sum(1 for f in features if "doi" in f["properties"])
        fetchlog.note(rows=len(features), upstream_version=petrochron.VERSION)
        self.stdout.write(f"점 {len(features):,} (연대 {dated:,} · DOI {linked:,}) → {dest}")


def _read(path: Path) -> bytes:
    with gzip.open(path, "rb") as fh:
        return fh.read()
