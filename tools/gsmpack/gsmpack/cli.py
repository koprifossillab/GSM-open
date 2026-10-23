"""`gsmpack` 명령 — GSM 없이 노트북에서 묶음을 굽고 들여다본다 (wetherilli P16·407).

    gsmpack bake data/offline_boxes.json jangseong --via http://paleolab/GSM/ --dry-run
    gsmpack bake data/offline_boxes.json jangseong --via http://paleolab/GSM/          # 연구소 망 안, 키 없이
    GSM_KIGAM_KEY_FILE=~/kigam_key GSM_VWORLD_KEY_FILE=~/vworld_key \\
      gsmpack bake data/offline_boxes.json jangseong --direct                            # 제 키로 상류를 곧장
    gsmpack info out/jangseong-20261021.gsmpack

- `--via` 는 GSM 판 1.2 부터 — 주소의 꼴(`offline/plan/`)과 지층 면(`offline/units/`)을 GSM 에 묻는다. 서버 캐시를 함께 쓴다
- `--direct` 는 키를 환경변수로만 받는다(`GSM_KIGAM_KEY`·`GSM_VWORLD_KEY`, 또는 `*_FILE`). 레이어 제목은 박스 표 옆의 `kigam_layers.json`
- 빠르기는 굽는 고리가 지킨다 — 상류에 1 초에 한 번. 멈추면 `<출력>/.<박스>.parts.sqlite` 에 남고, 같은 명령을 다시 부르면 이어진다
- **묶음은 연구실 안에서만 나눈다** — VWorld 이용약관 제19조 ⑥ (README)
"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__, bake, boxes, format, grid
from .sources import direct, via_gsm


def _titles(path):
    if not path or not Path(path).is_file():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["name"]: row.get("title") or row["name"] for row in data.get("레이어", [])}


def _sources(o, box, parts, log):
    """박스의 레이어마다 소스 — 지을 수 없는 것은 건너뛴다고 적는다."""
    sources, skipped = {}, []
    if o.via:
        for name in box["layers"]:
            try:
                sources[name] = via_gsm.GsmSource(o.via, name, via_gsm.plan(o.via, name), parts)
            except via_gsm.GsmError as exc:
                skipped.append(f"{name} ({exc})")
        return sources, skipped
    catalog = o.catalog or Path(o.boxes).with_name("kigam_layers.json")
    titles = _titles(catalog)
    kigam_key, vworld_key = direct.key_from_env("GSM_KIGAM_KEY"), direct.key_from_env("GSM_VWORLD_KEY")
    for name in box["layers"]:
        try:
            if name.startswith("vworld:"):
                sources[name] = direct.VWorldDirect(name, vworld_key, parts)
            else:
                sources[name] = direct.KigamDirect(name, kigam_key, parts, titles.get(name))
        except ValueError as exc:
            skipped.append(str(exc))
    if not o.dry_run:
        if any(isinstance(s, direct.KigamDirect) for s in sources.values()) and not kigam_key:
            raise SystemExit("KIGAM 인증키가 없다 — GSM_KIGAM_KEY 또는 GSM_KIGAM_KEY_FILE")
        if any(isinstance(s, direct.VWorldDirect) for s in sources.values()) and not vworld_key:
            raise SystemExit("VWorld 키가 없다 — GSM_VWORLD_KEY 또는 GSM_VWORLD_KEY_FILE")
    return sources, skipped


def cmd_bake(o):
    table = boxes.load(o.boxes)
    if o.box not in table:
        raise SystemExit(f"박스가 없다: {o.box} — {', '.join(table)}")
    box = table[o.box]
    out_dir = Path(o.out)
    parts = bake.NoParts() if o.dry_run else bake.Parts(bake.parts_path(out_dir, o.box))
    try:
        sources, skipped = _sources(o, box, parts, print)
    except bake.FetchError as exc:
        raise SystemExit(f"GSM 에 닿지 못했다: {exc}") from exc
    if skipped:
        print("건너뛴다: " + "; ".join(skipped), file=sys.stderr)
    if not sources:
        raise SystemExit("구울 레이어가 없다")
    plan = bake.Plan(o.box, box, sources, rate=o.rate)
    for line in plan.lines:
        print(line)
    if o.dry_run:
        return
    names = [n for n in box.get("units", []) if n in sources and not n.startswith("vworld:")]
    if o.via:
        gather = lambda bbox, gap: via_gsm.units(o.via, names, bbox)
    else:
        gather = lambda bbox, gap: direct.units(names, bbox, gap)
    try:
        done = bake.bake(plan, out_dir, parts, units=gather, extra={"gsmpack": __version__})
    except bake.BakeError as exc:
        raise SystemExit(str(exc)) from exc
    path = done["path"]
    print(f"{path} — 타일 {done['tiles']:,} 장, {path.stat().st_size / 1024 / 1024:.1f} MB, "
          f"물은 것 {done['asked']:,} 번, 실패 {done['fails']}")


def cmd_info(o):
    path = Path(o.pack)
    header, _ = format.read_header(path)
    west, south, east, north = header["bbox"]
    print(f"{path.name} — {path.stat().st_size / 1024 / 1024:.1f} MB · {header.get('title')} · 구운 날 {header.get('built')}")
    print(f"  범위 {west}–{east}°E, {south}–{north}°N · 덜어 냄 {header.get('dropped') or '없음'}")
    keys = [k for k in header["tiles"] if not k.startswith("@")]
    for name, layer in header["layers"].items():
        mine = [k for k in keys if k.startswith(name + "/")]
        print(f"  {name:32s} 격자 줌 {layer['zooms'][0]}–{layer['zooms'][1]} ({layer['tile_size']} px) 타일 {len(mine):,}")
    outside = 0
    for k in keys:
        name, z, x, y = k.rsplit("/", 3)
        on = grid.GRIDS.get(header["layers"].get(name, {}).get("grid"), grid.MERCATOR)
        if not _overlaps(int(z), int(x), int(y), header["bbox"], on):
            outside += 1
    print(f"  박스 밖 타일 {outside}")
    for name, unit in (header.get("units") or {}).items():
        print(f"  지층 면 {name}: {', '.join(unit['types'])} · {header['tiles'][unit['key']][1] / 1024:.0f} KB")


def _overlaps(z, x, y, bbox, on=grid.MERCATOR):
    west, south, east, north = on.projected_bbox(bbox)
    left, bottom, right, top = on.cell_extent(z, x, y)
    return left < east and right > west and bottom < north and top > south


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gsmpack", description="GSM 오프라인 묶음(.gsmpack)을 굽고 들여다본다")
    parser.add_argument("--version", action="version", version=f"gsmpack {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("bake", help="박스 하나를 묶음 하나로 굽는다")
    p.add_argument("boxes", help="박스 표 (data/offline_boxes.json 꼴)")
    p.add_argument("box", help="박스 이름")
    way = p.add_mutually_exclusive_group(required=True)
    way.add_argument("--via", metavar="GSM 주소", help="GSM 을 거친다 (예: http://paleolab/GSM/) — 키 없음")
    way.add_argument("--direct", action="store_true", help="제 키로 상류를 곧장 (GSM_KIGAM_KEY·GSM_VWORLD_KEY)")
    p.add_argument("--dry-run", action="store_true", help="받지 않고 장수·크기만 어림한다")
    p.add_argument("--out", default=".", help="출력 폴더 (기본: 지금 폴더)")
    p.add_argument("--rate", type=float, default=1.0, help="1 초에 몇 번 묻나 (최대 1)")
    p.add_argument("--catalog", help="곧장 굽을 때 레이어 제목을 읽을 kigam_layers.json (기본: 박스 표 옆)")
    p.set_defaults(func=cmd_bake)
    p = sub.add_parser("info", help="묶음 하나의 머리를 본다")
    p.add_argument("pack")
    p.set_defaults(func=cmd_info)
    o = parser.parse_args(argv)
    o.func(o)


if __name__ == "__main__":
    main()
