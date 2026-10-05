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
                (settings.GEUSARC_CATALOG_SEED, "그린란드 (GEUS ArcGIS)", "greenland", "geusarc"),
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
                (settings.GSJOWS_CATALOG_SEED, "일본 (GSJ WMS)", "japan", "gsjows"),
                # 대만 — 경제부 지질조사·광업관리중심(GSMMA) 지질도 (wetherilli 136)
                (settings.GSMMA_CATALOG_SEED, "대만 (GSMMA)", "taiwan", "gsmma"),
                # 북극해 — EMODnet 해저 퇴적물·해저 지질. 스발바르 탭도 빌려 보인다 (wetherilli 135)
                (settings.EMODNET_CATALOG_SEED, "북극해 (EMODnet)", "arctic_ocean", "emodnet"),
                # 노르웨이·핀란드 — NGU·GTK 기반암 지질도. 북극 묶음에도 든다 (wetherilli 140)
                (settings.NGU_CATALOG_SEED, "노르웨이 (NGU)", "fennoscandia", "ngu"),
                (settings.GTK_CATALOG_SEED, "핀란드 (GTK)", "fennoscandia", "gtk"),
                (settings.SGU_CATALOG_SEED, "스웨덴 (SGU)", "fennoscandia", "sgu"),   # wetherilli 213
                # 아이슬란드 NÍ 1:60만·1:10만 (wetherilli 216)
                (settings.NATT_CATALOG_SEED, "아이슬란드 (NÍ)", "iceland", "natt"),
                # 영국·프랑스 — BGS·BRGM, 그리고 넓게 볼 때 까는 EGDI 1:100만(영국에 두고 프랑스가 빌린다) (wetherilli 143)
                (settings.EGDI_CATALOG_SEED, "유럽 (EGDI)", "uk", "egdi"),
                (settings.BGS_CATALOG_SEED, "영국 (BGS)", "uk", "bgs"),
                (settings.BGSGI_CATALOG_SEED, "영국 (BGS GeoIndex)", "uk", "bgsgi"),
                # 유럽 바다 — EMODnet 의 제4기 퇴적층·지질 사건. 영국에 두고 유럽 탭들이 빌린다 (wetherilli 176)
                (settings.EMODNET_EUROPE_CATALOG_SEED, "유럽 바다 (EMODnet)", "uk", "emodnet"),
                (settings.BRGM_CATALOG_SEED, "프랑스 (BRGM)", "france", "brgm"),
                # 독일·스페인·아일랜드 — BGR·IGME·GSI, 북아일랜드 GSNI 는 아일랜드 탭에 (wetherilli 147)
                (settings.BGR_CATALOG_SEED, "독일 (BGR)", "germany", "bgr"),
                (settings.IGME_CATALOG_SEED, "스페인 (IGME)", "spain", "igme"),
                (settings.GSI_CATALOG_SEED, "아일랜드 (GSI)", "ireland", "gsi"),
                (settings.GSNI_CATALOG_SEED, "북아일랜드 (GSNI)", "ireland", "gsni"),
                # 남미 — SGC 남미 1:500만·콜롬비아 1:50만 (wetherilli 188)
                (settings.SGC_CATALOG_SEED, "남미 (SGC)", "colombia", "sgc"),
                # 브라질 — SGB 1:250만(2025)·1:100만·1:25만 (wetherilli 191)
                (settings.SGB_CATALOG_SEED, "브라질 (SGB)", "brazil", "sgb"),
                # 페루 — INGEMMET 1:5만·1:10만 통합판 (wetherilli 195)
                (settings.INGEMMET_CATALOG_SEED, "페루 (INGEMMET)", "peru", "ingemmet"),
                # 아르헨티나 SEGEMAR 1:250만·1:25만, 우루과이 DINAMIGE 1:50만 (wetherilli 196)
                (settings.SEGEMAR_CATALOG_SEED, "아르헨티나 (SEGEMAR)", "argentina", "segemar"),
                (settings.DINAMIGE_CATALOG_SEED, "우루과이 (DINAMIGE)", "uruguay", "dinamige"),
                # 에콰도르 — IIGE 일반 지질도 (wetherilli 198)
                (settings.IIGE_CATALOG_SEED, "에콰도르 (IIGE)", "ecuador", "iige"),
                # 미국 — USGS SGMC(본토)·SIM 3340(알래스카) (wetherilli 205)
                (settings.MRDATA_CATALOG_SEED, "미국 (USGS)", "usa", "mrdata"),
                # 멕시코 — SGM 1:25만·1:5만 (wetherilli 206)
                (settings.SGM_CATALOG_SEED, "멕시코 (SGM)", "mexico", "sgm"),
                # 호주 — Geoscience Australia 1:250만·1:100만 (wetherilli 212)
                (settings.GA_CATALOG_SEED, "호주 (GA)", "australia", "ga"),
                # 호주의 주 판 — 퀸즐랜드 GSQ·빅토리아 GSV·남호주 GSSA (wetherilli 225)
                (settings.GSQ_CATALOG_SEED, "퀸즐랜드 (GSQ)", "australia", "gsq"),
                (settings.GSV_CATALOG_SEED, "빅토리아 (GSV)", "australia", "gsv"),
                (settings.GSSA_CATALOG_SEED, "남호주 (GSSA)", "australia", "gssa"),
                (settings.MRT_CATALOG_SEED, "태즈메이니아 (MRT)", "australia", "mrt"),
                (settings.GSNSW_CATALOG_SEED, "뉴사우스웨일스 (GSNSW)", "australia", "gsnsw"),
                # 뉴질랜드 GNS QMAP 1:25만·1:100만, 같은 서버의 남극 남빅토리아랜드 1:25만 (wetherilli 218)
                (settings.GNS_CATALOG_SEED, "뉴질랜드 (GNS)", "new_zealand", "gns"),
                (settings.GNS_ANTARCTICA_CATALOG_SEED, "남빅토리아랜드 (GNS)", "antarctica", "gns"),
                # 몽골 — 국가지질도첩 지질도·단층 1:50만 (MonGeoCat, wetherilli 221)
                (settings.MRIS_CATALOG_SEED, "몽골 (MonGeoCat)", "mongolia", "mris"),
                # 인도 — GSI 1:200만, 그림은 BGS(OneGeology) (wetherilli 226)
                (settings.GSIINDIA_CATALOG_SEED, "인도 (GSI)", "india", "gsiindia"),
                # 사우디아라비아 — SGS 1:25만 합본 (wetherilli 227)
                (settings.SGS_CATALOG_SEED, "사우디아라비아 (SGS)", "saudi", "sgs"),
                # 동남아 — 인도네시아 ESDM·말레이시아 JMG·필리핀 MGB·태국 DMR (wetherilli 228)
                (settings.ESDM_CATALOG_SEED, "인도네시아 (ESDM)", "indonesia", "esdm"),
                (settings.JMG_CATALOG_SEED, "말레이시아 (JMG)", "malaysia", "jmg"),
                (settings.MGB_CATALOG_SEED, "필리핀 (MGB)", "philippines", "mgb"),
                (settings.DMR_CATALOG_SEED, "태국 (DMR)", "thailand", "dmr"),
                # 아프리카 — CGMW–BRGM 1:1000만, BGS 지하수 지도책 나라별 1:500만 지질 (wetherilli 207)
                (settings.CGMW_CATALOG_SEED, "아프리카 (CGMW–BRGM)", "africa", "cgmw"),
                (settings.AGA_CATALOG_SEED, "아프리카 나라별 (BGS AGA)", "africa", "aga"),
                # 아프리카 나라 판 — 남아공 CGS·나미비아 GSN 1:100만 (wetherilli 209). 탭은 아프리카 하나에 얹는다
                (settings.CGS_CATALOG_SEED, "남아공 (CGS)", "africa", "cgs"),
                (settings.GSN_CATALOG_SEED, "나미비아 (GSN)", "africa", "gsn"),
                # 부르키나파소 BUMIGEB·카메룬 IRGM 1:100만 (wetherilli 246)
                (settings.BUMIGEB_CATALOG_SEED, "부르키나파소 (BUMIGEB)", "africa", "bumigeb"),
                (settings.IRGM_CATALOG_SEED, "카메룬 (IRGM)", "africa", "irgm"),
                # 캐나다 — NRCan 1:500만(Wheeler)·온타리오 OGS 1:25만 (wetherilli 204)
                (settings.NRCAN_CATALOG_SEED, "캐나다 (NRCan)", "canada", "nrcan"),
                (settings.OGS_CATALOG_SEED, "온타리오 (OGS)", "canada", "ogs"),
                # 퀘벡 SIGÉOM·유콘 YGS (wetherilli 210)
                (settings.SIGEOM_CATALOG_SEED, "퀘벡 (SIGÉOM)", "canada", "sigeom"),
                (settings.YGS_CATALOG_SEED, "유콘 (YGS)", "canada", "ygs"),
                # 사스카치원·노바스코샤·앨버타 (wetherilli 235)
                (settings.SKGS_CATALOG_SEED, "사스카치원 (SGS)", "canada", "skgs"),
                (settings.NSGS_CATALOG_SEED, "노바스코샤 (NRR)", "canada", "nsgs"),
                (settings.AGS_CATALOG_SEED, "앨버타 (AGS)", "canada", "ags"),
                # 브리티시컬럼비아 BCGS(캐나다 탭)·캘리포니아 CGS(미국 탭) (wetherilli 231)
                (settings.BCGS_CATALOG_SEED, "브리티시컬럼비아 (BCGS)", "canada", "bcgs"),
                (settings.CALGS_CATALOG_SEED, "캘리포니아 (CGS)", "usa", "calgs"),
                # 네바다·워싱턴·오리건 (wetherilli 291) — 한 문(`usstates.py`)에 셋
                (settings.NBMG_CATALOG_SEED, "네바다 (NBMG)", "usa", "nbmg"),
                (settings.WADNR_CATALOG_SEED, "워싱턴 (DNR)", "usa", "wadnr"),
                (settings.DOGAMI_CATALOG_SEED, "오리건 (DOGAMI)", "usa", "dogami"),
                # 유럽 — 오스트리아 GeoSphere·폴란드 PIG·네덜란드 TNO·벨기에(플랑드르 DOV·왈로니아 SPW) (wetherilli 237)
                (settings.GEOSPHERE_CATALOG_SEED, "오스트리아 (GeoSphere)", "austria", "geosphere"),
                (settings.PIG_CATALOG_SEED, "폴란드 (PIG-PIB)", "poland", "pig"),
                (settings.TNO_CATALOG_SEED, "네덜란드 (TNO)", "netherlands", "tno"),
                (settings.DOV_CATALOG_SEED, "플랑드르 (DOV)", "belgium", "dov"),
                (settings.SPW_CATALOG_SEED, "왈로니아 (SPW)", "belgium", "spw"),
                # 중앙아메리카·카리브 — 니카라과 INETER·도미니카공화국 SGN(IGME 서버) (wetherilli 242)
                (settings.INETER_CATALOG_SEED, "니카라과 (INETER)", "nicaragua", "ineter"),
                (settings.IGME_DR_CATALOG_SEED, "도미니카공화국 (SGN)", "dominican_republic", "igme"),
                # 카리브 — USGS 카리브 지질도(French & Schenk 2004), 면을 한 덩이로 (wetherilli 248)
                (settings.USGSCARIB_CATALOG_SEED, "카리브 (USGS)", "caribbean", "usgscarib"),
                # 대앤틸리스 — USGS SIM 3534(옛 판 OFR 2019-1036), 우리가 구운 sqlite (wetherilli 254)
                (settings.SIM3534_CATALOG_SEED, "대앤틸리스 (USGS)", "caribbean", "sim3534"),
                # 파나마 — STRI 의 MICI 1990 1:25만, 면·단층을 한 덩이로 (wetherilli 253)
                (settings.STRI_CATALOG_SEED, "파나마 (STRI)", "panama", "stri"),
                # 파라과이 — 광업·에너지 차관실 지질도, 남미 — USGS 1:500만(콜롬비아 지역에 두고 남미 탭들이 빌린다) (wetherilli 256)
                (settings.VMME_CATALOG_SEED, "파라과이 (VMME)", "paraguay", "vmme"),
                (settings.USGSCARIB_SA_CATALOG_SEED, "남미 (USGS)", "colombia", "usgscarib"),
                # 누벨칼레도니 — 정부 Géorep 의 DIMENC 지질도 (wetherilli 260)
                (settings.GEOREP_CATALOG_SEED, "누벨칼레도니 (Géorep)", "new_caledonia", "georep"),
                # 프랑스 해외 영토 BRGM 스캔 — 지역은 씨앗이 적는다(카리브·프랑스령 폴리네시아·아프리카·캐나다) (wetherilli 260)
                *((path, f"BRGM 해외 ({path.stem})", "caribbean", "brgm") for path in settings.BRGM_OVERSEAS_CATALOG_SEEDS),
                # 이탈리아 ISPRA·포르투갈 LNEG·스위스 swisstopo (wetherilli 211)
                (settings.ISPRA_CATALOG_SEED, "이탈리아 (ISPRA)", "italy", "ispra"),
                (settings.LNEG_CATALOG_SEED, "포르투갈 (LNEG)", "portugal", "lneg"),
                (settings.SWISSTOPO_CATALOG_SEED, "스위스 (swisstopo)", "switzerland", "swisstopo"),
                # 중국 — USGS geo3al, 우리 디스크의 셰이프파일 (025)
                (settings.GEO3AL_CATALOG_SEED, "중국 (USGS)", "china", "geo3al"),
                # KIGAM 5만 구조 요소 — 받아 둔 WFS 파일의 화석산지·시료·광산·도폭 틀 (wetherilli 199, jikhanjung P01)
                (settings.KIGAM50K_CATALOG_SEED, "KIGAM 5만 구조 요소", "korea", "kigam50k"),
                # 연구실의 암맥 기록 — phyloserver (026)
                (settings.PHYLOSERVER_CATALOG_SEED, "암맥 (phyloserver)", "korea", "phyloserver"),
                # 한반도 지질도 음영판 — 우리 디스크의 PDF 를 잘라 둔 타일 (027)
                (settings.PENINSULA_CATALOG_SEED, "한반도 음영판", "korea", "peninsula"),
                # 남극 IBCSO 자료 출처(TID) — 우리 디스크의 격자를 잘라 둔 타일 (071)
                (settings.IBCSO_CATALOG_SEED, "남극 IBCSO", "antarctica", "ibcso"),
                # 남극 자력 이상 ADMAP-2 — 우리가 칠해 잘라 둔 3031 타일 (wetherilli 262)
                (settings.ADMAP_CATALOG_SEED, "남극 ADMAP-2", "antarctica", "admap"),
                # PGC 경사·등고선 — 극지 지질도 위에 겹친다 (wetherilli 099). 지역은 씨앗이 적는다
                *((path, f"PGC ({path.stem})", "greenland", "pgc") for path in settings.PGC_CATALOG_SEEDS),
                # 남극 — BAS 의 Bedmap3 빙저 지형·얼음 두께·윗면 (wetherilli 261)
                (settings.BAS_CATALOG_SEED, "남극 (BAS Bedmap3)", "antarctica", "bas"),
                # 극지연구소 — 암석 시료·운석·KPDC 자료·기지·해안선 (053–057). 지역은 씨앗이 적는다
                *((path, f"극지연구소 ({path.stem})", "antarctica", "kopri")
                  for path in settings.KOPRI_CATALOG_SEEDS),
                # 지구 자료 점 — 모아 둔 화석 산지·화산·지진·고생태 산지를 지역의 네모만큼 (wetherilli 185). 지역은 씨앗이 적는다
                *((path, f"지구 자료 ({path.stem})", "korea", "earth") for path in settings.EARTH_CATALOG_SEEDS)):
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
