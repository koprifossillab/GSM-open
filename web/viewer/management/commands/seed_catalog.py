"""레이어 카탈로그를 씨앗에서 채운다.

    manage.py seed_catalog                  저장소에 든 씨앗으로 (평소)
    manage.py seed_catalog --from-upstream  상류에서 다시 뽑아 씨앗도 갱신

**사람이 손질한 것을 덮지 않는다.** 이미 있는 레이어는 제목·레이어군·차례를
건드리지 않고 범위(bbox)와 설명만 새로 받는다. 상류가 준 제목이 마음에
안 들어 고쳐 둔 것을 다시 뽑을 때마다 되돌리면 손질할 마음이 안 난다.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from viewer import catalog, kigam
from viewer.models import Layer, LayerGroup


class Command(BaseCommand):
    help = "레이어 카탈로그를 씨앗에서 채운다"

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-upstream", action="store_true",
            help="상류 GetCapabilities 에서 다시 뽑는다 (문서에 없는 주소를 탄다)")
        parser.add_argument(
            "--reset-titles", action="store_true",
            help="사람이 손질한 제목까지 상류 것으로 되돌린다")

    def handle(self, *args, **options):
        if options["from_upstream"]:
            seed = self._from_upstream()
        else:
            seed = self._from_file()

        order = seed.get("레이어군순서") or catalog.GROUP_ORDER
        layers = seed.get("레이어") or []
        if not layers:
            raise CommandError("씨앗에 레이어가 없다")

        made, touched = self._apply(layers, order, options["reset_titles"])

        self.stdout.write(self.style.SUCCESS(
            f"카탈로그 {len(layers)}개 — 새로 생긴 것 {made}, 손본 것 {touched}"))
        # 다른 상류의 씨앗 — 그린란드(GEUS·정부 포털, 019), 남극(GeoMAP, 018), 한국의 "지질 참고"(VWorld, 020).
        # 상류를 타지 않고 저장소의 표만 쓴다
        for path, label, region, upstream in (
                # KIGAM 낱레이어를 엮은 것(층리 뺀 5만 지질도) — 같은 "지질도" 레이어군에 든다
                (settings.KIGAM_COMPOSED_CATALOG_SEED, "KIGAM 엮은 레이어", "korea", "kigam"),
                (settings.GEUS_CATALOG_SEED, "그린란드", "greenland", "geus"),
                (settings.VWORLD_CATALOG_SEED, "VWorld", "korea", "vworld"),
                (settings.GRPORTAL_CATALOG_SEED, "그린란드 정부 포털", "greenland", "grportal"),
                (settings.GEOMAP_CATALOG_SEED, "남극", "antarctica", "geomap"),
                # 얀마옌(NPI 지질도, 022) — GeoMAP 처럼 우리 디스크의 파일을 읽는다
                (settings.JANMAYEN_CATALOG_SEED, "얀마옌", "jan_mayen", "janmayen"),
                # 노르웨이 극지연구소(NPI, 021) — 스발바르, 그리고 남극의 드로닝모드랜드
                (settings.NPOLAR_CATALOG_SEED, "스발바르 (NPI)", "svalbard", "npolar"),
                (settings.NPOLAR_DML_CATALOG_SEED, "드로닝모드랜드 (NPI)", "antarctica", "npolar"),
                # 일본 — GSJ 심리스 지질도 (024)
                (settings.GSJ_CATALOG_SEED, "일본 (GSJ)", "japan", "gsj"),
                # 일본 — 국토지리원 주제 타일(활단층도·화산토지조건도). 브라우저가 곧장 부른다 (wetherilli 172)
                (settings.GSITILE_CATALOG_SEED, "일본 (국토지리원)", "japan", "gsitile"),
                # 동·동남아시아 — CCOP 200만 지질도, GSJ 새 호스트의 WMS (wetherilli 108)
                (settings.CCOP_CATALOG_SEED, "동아시아 (CCOP)", "china", "ccop"),
                # 대만 — 경제부 지질조사·광업관리중심(GSMMA) 지질도 (wetherilli 136)
                (settings.GSMMA_CATALOG_SEED, "대만 (GSMMA)", "taiwan", "gsmma"),
                # 북극해 — EMODnet 해저 퇴적물·해저 지질. 스발바르 탭도 빌려 보인다 (wetherilli 135)
                (settings.EMODNET_CATALOG_SEED, "북극해 (EMODnet)", "arctic_ocean", "emodnet"),
                # 노르웨이·핀란드 — NGU·GTK 기반암 지질도. 북극 묶음에도 든다 (wetherilli 140)
                (settings.NGU_CATALOG_SEED, "노르웨이 (NGU)", "fennoscandia", "ngu"),
                (settings.GTK_CATALOG_SEED, "핀란드 (GTK)", "fennoscandia", "gtk"),
                # 영국·프랑스 — BGS·BRGM, 그리고 넓게 볼 때 까는 EGDI 1:100만(영국에 두고 프랑스가 빌린다) (wetherilli 143)
                (settings.EGDI_CATALOG_SEED, "유럽 (EGDI)", "uk", "egdi"),
                (settings.BGS_CATALOG_SEED, "영국 (BGS)", "uk", "bgs"),
                # 유럽 바다 — EMODnet 의 제4기 퇴적층·지질 사건. 영국에 두고 유럽 탭들이 빌린다 (wetherilli 176)
                (settings.EMODNET_EUROPE_CATALOG_SEED, "유럽 바다 (EMODnet)", "uk", "emodnet"),
                (settings.BRGM_CATALOG_SEED, "프랑스 (BRGM)", "france", "brgm"),
                # 독일·스페인·아일랜드 — BGR·IGME·GSI, 북아일랜드 GSNI 는 아일랜드 탭에 (wetherilli 147)
                (settings.BGR_CATALOG_SEED, "독일 (BGR)", "germany", "bgr"),
                (settings.IGME_CATALOG_SEED, "스페인 (IGME)", "spain", "igme"),
                (settings.GSI_CATALOG_SEED, "아일랜드 (GSI)", "ireland", "gsi"),
                (settings.GSNI_CATALOG_SEED, "북아일랜드 (GSNI)", "ireland", "gsni"),
                # 중국 — USGS geo3al, 우리 디스크의 셰이프파일 (025)
                (settings.GEO3AL_CATALOG_SEED, "중국 (USGS)", "china", "geo3al"),
                # 연구실의 암맥 기록 — phyloserver (026)
                (settings.PHYLOSERVER_CATALOG_SEED, "암맥 (phyloserver)", "korea", "phyloserver"),
                # 한반도 지질도 음영판 — 우리 디스크의 PDF 를 잘라 둔 타일 (027)
                (settings.PENINSULA_CATALOG_SEED, "한반도 음영판", "korea", "peninsula"),
                # 남극 IBCSO 자료 출처(TID) — 우리 디스크의 격자를 잘라 둔 타일 (071)
                (settings.IBCSO_CATALOG_SEED, "남극 IBCSO", "antarctica", "ibcso"),
                # PGC 경사·등고선 — 극지 지질도 위에 겹친다 (wetherilli 099). 지역은 씨앗이 적는다
                *((path, f"PGC ({path.stem})", "greenland", "pgc") for path in settings.PGC_CATALOG_SEEDS),
                # 극지연구소 — 암석 시료·운석·KPDC 자료·기지·해안선 (053–057). 지역은 씨앗이 적는다
                *((path, f"극지연구소 ({path.stem})", "antarctica", "kopri")
                  for path in settings.KOPRI_CATALOG_SEEDS)):
            if not path.exists():
                continue
            extra = json.loads(path.read_text(encoding="utf-8"))
            made, touched = self._apply(extra["레이어"], extra["레이어군순서"], options["reset_titles"],
                                        region=extra.get("_지역", region),
                                        upstream=extra.get("_상류", upstream),
                                        first=extra.get("_레이어군차례", 0))
            self.stdout.write(self.style.SUCCESS(
                f"{label} {len(extra['레이어'])}개 — 새로 생긴 것 {made}, 손본 것 {touched}"))

        unverified = Layer.objects.filter(verified_at__isnull=True, upstream="kigam").count()
        if unverified:
            self.stdout.write(
                f"아직 /openapi/wms 로 확인하지 않은 레이어 {unverified}개. "
                "인증키가 생기면 `verify_layers` 로 대조한다.")

    def _from_file(self) -> dict:
        path = settings.CATALOG_SEED
        if not path.exists():
            raise CommandError(
                f"씨앗이 없다: {path}\n"
                "상류에서 뽑으려면 --from-upstream 을 준다.")
        return json.loads(path.read_text(encoding="utf-8"))

    def _from_upstream(self) -> dict:
        self.stdout.write(self.style.WARNING(
            "문서에 없는 주소로 씨앗을 뽑는다 — CLAUDE.md '두 개의 상류 주소'"))
        try:
            xml = kigam.fetch_capabilities()
        except kigam.UpstreamError as exc:
            raise CommandError(str(exc)) from exc

        seed = catalog.parse(xml)
        path = settings.CATALOG_SEED
        path.parent.mkdir(parents=True, exist_ok=True)
        keep = {}
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            keep = {k: v for k, v in old.items() if k.startswith("_")}
        keep["_뽑은날"] = _today()
        keep["_출처"] = settings.CAPABILITIES_URL
        path.write_text(json.dumps({**keep, **seed}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        self.stdout.write(f"씨앗을 새로 적었다: {path}")
        return seed

    @transaction.atomic
    def _apply(self, layers, order, reset_titles, region="korea", upstream="kigam", first=0):
        """`first` 는 레이어군 차례의 시작. 한 지역에 씨앗이 둘이면(한국의 KIGAM
        과 VWorld) 뒤의 것이 앞의 것과 차례가 겹치지 않게 띄운다."""
        groups = {}
        for index, name in enumerate(order, start=first):
            group, _ = LayerGroup.objects.get_or_create(
                name=name, region=region, defaults={"order": index})
            if group.order != index:
                group.order = index
                group.save(update_fields=["order"])
            groups[name] = group

        made = touched = 0
        for index, row in enumerate(layers):
            group = groups.get(row["group"]) or LayerGroup.objects.get_or_create(
                name=row["group"], region=region, defaults={"order": len(groups)})[0]
            groups.setdefault(row["group"], group)

            bbox = row.get("bbox") or [None] * 4
            fields = {
                "abstract": row.get("abstract") or "",
                "bbox_west": bbox[0], "bbox_south": bbox[1],
                "bbox_east": bbox[2], "bbox_north": bbox[3],
                # 그리는 법은 사람이 손질하는 것이 아니라 상류가 무엇을 주느냐다
                "kind": row.get("kind") or "wms",
            }
            layer = Layer.objects.filter(name=row["name"]).first()
            if layer is None:
                extra = {}
                # 씨앗을 만들 때 한 장씩 쏴 본 것(VWorld)은 그날을 확인한 때로 둔다
                if row.get("확인한날"):
                    extra = {"verified_at": _day(row["확인한날"]),
                             "verify_note": "씨앗을 만들 때 타일·속성을 받아 봤다"}
                Layer.objects.create(
                    name=row["name"],
                    title=row.get("title") or row["name"],
                    group=group, order=index, upstream=upstream, **fields, **extra)
                made += 1
                continue

            # 사람이 손질한 자리는 그대로 둔다
            if reset_titles and row.get("title"):
                fields["title"] = row["title"]
            for key, value in fields.items():
                setattr(layer, key, value)
            layer.save()
            touched += 1
        return made, touched


def _day(text: str):
    """씨앗의 `2026-09-27` → 그날 정오(지역 시각)."""
    import datetime

    from django.utils import timezone
    day = datetime.date.fromisoformat(text)
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(12)))


def _today() -> str:
    from django.utils import timezone
    return timezone.localdate().isoformat()
