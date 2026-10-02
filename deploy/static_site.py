#!/usr/bin/env python
"""연구소 밖 정적 판을 굽는다 — GitHub Pages 의 https://koprifossillab.github.io/GSM-open/ (wetherilli P11·162).

    python deploy/static_site.py <출력 폴더> [--baked <bake_static 의 출력>] [--prefix /GSM-open/]

서버 없이 도는 판이다. Django 로 지도 화면(map.html)을 `settings.STATIC_SITE` 를 켜고 **한 번** 그려 index.html 로 두고,
정적 파일을 모으고, 우리 파일에서 미리 구운 것(`manage.py bake_static`, wetherilli 160)을 그 자리에 얹는다.
WegenersDream 의 `deploy/static_site.py`(tupandactyl 029)와 같은 길이다.

- 카탈로그는 빈 DB 에 씨앗을 넣어 만든다(`seed_catalog`) — 운영 DB 를 읽지 않는다. 점묶음은 싣지 않는다
- 실을 지역·상류는 `REGIONS`·`UPSTREAMS` 가 정한다. 상류를 늘리려면 브라우저가 곧장 부르는 소스(`static-kinds.js`)나
  구운 파일이 먼저 있어야 한다. 연구실 내부용(`views.LAB_ONLY`)은 싣지 않는다
- 주소 앞머리: 그린 HTML 의 `/GSM/` 을 `--prefix` 로 바꾼다. 화면의 주소는 `location.pathname` 에서 세므로(`map.js` 의 BASE)
  앞머리만 맞으면 된다
- **뿌리는 소개, `map/` 은 지도, 영어판은 `en/`·`en/map/`**(wetherilli 167). 소개는 서버 화면(3D·온 지구·달·화성·수성)으로 가는 장면·문을
  빼고 그린다(`intro.html` 의 `static_site`). 정적 파일은 한 벌이다
- 인증키는 싣지 않는다 — KIGAM 은 보는 사람이 각자 넣는다
- **VWorld 는 공개 판용 키 하나**를 화면에 싣는다(검토 §10, wetherilli 164) — `--vworld-key-file` 이나 `GSM_STATIC_VWORLD_KEY`.
  **운영 키로 저절로 돌아가지 않는다** — 운영 키와 갈라 두라는 것이 검토의 권고다(남이 뽑아 써 하루 한도를 먹으면 운영도 멈춘다).
  둘 다 없으면 VWorld 를 빼고 굽는다(배경·찾기·좌표→주소·VWorld 레이어가 빠진다)
"""
import argparse
import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: 정적 판에 실을 지역 — 상류가 붙는 대로 늘린다(P11 §3)
REGIONS = ["korea"]
#: 정적 판에 실을 상류 — kigam 은 각자 키로 곧장(map.js 의 STATIC_KIGAM), vworld 는 공개 판용 키로 곧장(STATIC_VWORLD)
UPSTREAMS = ["kigam", "vworld"]
#: 구운 것(`--baked`)이 있으면 더 서는 극지 — 남극 GeoMAP·IBCSO·NPI 점, 얀마옌, 그린란드 포털 점, 스발바르 NPI 점,
#: 극지연구소 KPDC 점 (wetherilli 160·165). 브라우저가 곧장 부르는 극지 상류(`static-kinds.js`)가 오면 그 레이어도 함께 선다
BAKED_REGIONS = ["antarctica", "greenland", "svalbard", "jan_mayen", "arctic_ocean"]
#: 구운 타일로 통째로 서는 상류 — 점 레이어는 상류가 아니라 이름으로 싣는다(`views._static_catalog`)
BAKED_UPSTREAMS = {"geomap": "geomap", "ibcso": "ibcso"}


def baked_spec(baked: pathlib.Path) -> dict:
    """`bake_static` 의 manifest.json → 화면에 알릴 것. GeoMAP 레이어마다 마지막 줌, 점 레이어마다 영어판이 따로 있나."""
    manifest = json.loads((baked / "manifest.json").read_text(encoding="utf-8"))
    parts = manifest.get("parts") or {}
    geomap = {name: info["max_zoom"] for name, info in (parts.get("geomap") or {}).items()
              if isinstance(info, dict) and info.get("tiles")}
    points = {name: bool(info.get("lang")) for name, info in (parts.get("points") or {}).items()}
    return {"geomap": geomap, "points": points, "ibcso": bool(parts.get("ibcso"))}


def place_index(baked: pathlib.Path, out: pathlib.Path) -> dict:
    """구운 지명 덩이(`points/<상류>/<이름>.json`)에서 찾기 칸이 뒤질 가벼운 색인을 짓는다 (wetherilli 166).

    서버의 `placenames/` 가 하던 일이다 — 색인은 서버와 같은 `arcpoints.name_index` 로 짓고, 맞추기(`match_index`)는 화면이
    한다(`map.js` 의 `staticNames`). 한 줄은 `[이름들, 곁말, 위도, 경도, 앞세움]` — 접은 이름은 화면이 다시 접는다.
    돌려주는 것은 지역 → 색인 주소들(`views.PLACE_SOURCES` 의 차례)."""
    from viewer import arcpoints, views

    written = {}
    for name, (names, side, prefer) in views.PLACE_FIELDS.items():
        upstream, _, rest = name.partition(":")
        src = baked / "points" / upstream / f"{rest}.json"
        if not src.is_file():
            continue
        features = json.loads(src.read_text(encoding="utf-8")).get("features") or []
        rows = [[list(shown), sub, round(lat, 5), round(lon, 5), first]
                for _, shown, sub, lat, lon, first in arcpoints.name_index(features, names, side, prefer)]
        rel = f"placenames/{upstream}/{rest}.json"
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written[name] = rel
    return {region: [written[n] for n in names if n in written]
            for region, names in views.PLACE_SOURCES.items() if any(n in written for n in names)}


def main():
    parser = argparse.ArgumentParser(description="연구소 밖 정적 판을 굽는다")
    parser.add_argument("out", help="출력 폴더 — 있으면 비운다")
    parser.add_argument("--baked", help="manage.py bake_static 의 출력 — 그 자리에 얹는다")
    parser.add_argument("--prefix", default="/GSM-open/", help="Pages 주소의 앞머리")
    parser.add_argument("--regions", default=",".join(REGIONS))
    parser.add_argument("--upstreams", default=",".join(UPSTREAMS))
    parser.add_argument("--vworld-key-file", help="공개 판용 VWorld 키 한 줄 — 없으면 GSM_STATIC_VWORLD_KEY")
    args = parser.parse_args()
    vworld_key = (pathlib.Path(args.vworld_key_file).read_text().strip() if args.vworld_key_file
                  else os.environ.get("GSM_STATIC_VWORLD_KEY", "").strip())

    out = pathlib.Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="gsm-static-"))

    # 빈 DB 에 씨앗만 — 운영 DB·타일 캐시를 건드리지 않는다
    os.environ["GSM_DB_PATH"] = str(work / "static.db")
    os.environ["GSM_TILE_CACHE_DIR"] = str(work / "tiles")
    os.environ.setdefault("GSM_SECRET_KEY", "static-site-build")
    os.environ.pop("GSM_KIGAM_KEY", None)
    os.environ.pop("GSM_VWORLD_KEY", None)          # 운영 키는 싣지 않는다 — 공개 판용 키만(`vworld_key`)
    sys.path.insert(0, str(ROOT / "web"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gsmweb.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.test import Client, override_settings

    call_command("migrate", verbosity=0)
    call_command("seed_catalog", verbosity=0, stdout=open(os.devnull, "w"))

    spec = {"regions": [r for r in args.regions.split(",") if r],
            "upstreams": [u for u in args.upstreams.split(",") if u and (u != "vworld" or vworld_key)]}
    if "vworld" in args.upstreams.split(",") and not vworld_key:
        print("공개 판용 VWorld 키가 없어 VWorld 를 빼고 굽는다 (--vworld-key-file 이나 GSM_STATIC_VWORLD_KEY)")
    if args.baked:
        # 구운 것을 화면에 알린다 — 마지막 줌·점 레이어·영어판 (wetherilli 165)
        spec["baked"] = baked_spec(pathlib.Path(args.baked))
        spec["regions"] += [r for r in BAKED_REGIONS if r not in spec["regions"]]
        spec["upstreams"] += [up for part, up in BAKED_UPSTREAMS.items()
                              if spec["baked"].get(part) and up not in spec["upstreams"]]
        # 극지의 지명 찾기 — 구운 지명에서 색인을 지어 화면이 뒤진다 (wetherilli 166)
        spec["baked"]["placenames"] = place_index(pathlib.Path(args.baked), out)
    with override_settings(STATIC_SITE=spec, DEBUG=False, ALLOWED_HOSTS=["*"], KIGAM_KEY="", VWORLD_KEY=vworld_key,
                           STATIC_ROOT=str(out / "static")):
        call_command("collectstatic", verbosity=0, interactive=False)
        # 지도와 소개를 말마다 한 번씩 그린다 (wetherilli 167) — 정적 판에는 쿠키를 읽을 서버가 없어 영어판을 `en/` 에 따로 둔다
        pages = {}
        for lang in ("ko", "en"):
            client = Client()
            client.cookies["gsm_lang"] = lang
            for path, name in (("/GSM/map/", "map"), ("/GSM/", "intro")):
                page = client.get(path)
                if page.status_code != 200:
                    sys.exit(f"{name}({lang}) 화면을 그리지 못했다: {page.status_code}")
                pages[lang, name] = page.content.decode("utf-8")

    for (lang, name), html in pages.items():
        # 정적 파일은 말과 상관없이 한 벌이다. 영어판의 다른 주소(소개·지도로 가는 길)는 `en/` 밑으로
        html = html.replace("/GSM/static/", args.prefix + "static/")
        html = html.replace("/GSM/", args.prefix + ("en/" if lang == "en" else ""))
        folder = (out / "en" if lang == "en" else out) / ("map" if name == "map" else "")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(html, encoding="utf-8")
    (out / ".nojekyll").write_text("")   # 밑줄로 시작하는 파일을 Jekyll 이 버리지 않게

    if args.baked:
        baked = pathlib.Path(args.baked)
        for item in baked.iterdir():
            target = out / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    # 정적 판에 쓰지 않는 무거운 정적 파일을 덜어 낸다 — Pages 는 사이트 1 GB
    for heavy in ("admin", "viewer/vendor/cesium"):
        shutil.rmtree(out / "static" / heavy, ignore_errors=True)

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"정적 판을 구웠다: {out} ({size / 1e6:.1f} MB, 지역 {spec['regions']}, 상류 {spec['upstreams']})")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
