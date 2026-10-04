"""지질도Navi 판 목록을 씨앗에 적는다 (wetherilli 171).

    manage.py fetch_geonavi                 Capabilities 한 장을 받아
    manage.py fetch_geonavi --from 파일.xml  받아 둔 것으로

`data/gsj_geonavi_layers.json` 에 판마다 이름·제목·범위·줌 끝·범례를 적는다. 사람이 단 `hide` 는 다시 받아도 지킨다.
상류에 묻는 것은 Capabilities 한 장뿐이다 — 판마다 묻지 않는다.
"""
import datetime
import json
import pathlib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from viewer import gsj


class Command(BaseCommand):
    help = "지질도Navi 판 목록을 씨앗에 적는다"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="source", help="받아 둔 WMTSCapabilities.xml")

    def handle(self, *args, **options):
        if options["source"]:
            xml = pathlib.Path(options["source"]).read_text(encoding="utf-8")
        else:
            try:
                xml = gsj.fetch_geonavi_capabilities()
            except gsj.GsjError as exc:
                raise CommandError(str(exc)) from exc
        layers = gsj.parse_geonavi(xml)
        if not layers:
            raise CommandError("판을 하나도 읽지 못했다 — Capabilities 꼴이 바뀌었나")
        path = settings.REPO_DIR / "data" / "gsj_geonavi_layers.json"
        hidden = {e["id"] for e in gsj.load_geonavi() if e.get("hide")}
        for e in layers:
            if e["id"] in hidden:
                e["hide"] = True
        meta = {"source": f"GSJ 지질도Navi WMTS Capabilities ({gsj.GEONAVI_CAPABILITIES})",
                "license": "정부표준이용규약 2.0 (출처 표시) — 地質図Navi © Geological Survey of Japan, AIST",
                "fetched": datetime.date.today().isoformat()}
        # 한 판에 한 줄 — 다시 받았을 때 차이가 판 단위로 보이게
        text = ('{"meta":' + json.dumps(meta, ensure_ascii=False) + ',\n"layers":[\n'
                + ",\n".join(json.dumps(e, ensure_ascii=False) for e in layers) + "\n]}\n")
        path.write_text(text, encoding="utf-8")
        unknown = sorted({gsj.split_title(e["title"])[0] for e in layers} - {s[0] for s in gsj.GEONAVI_SERIES})
        self.stdout.write(f"판 {len(layers)} 개를 적었다 (숨김 {len(hidden)})")
        if unknown:
            self.stdout.write("한글 이름이 없는 시리즈 — gsj.GEONAVI_SERIES 에 더한다: " + ", ".join(unknown))
