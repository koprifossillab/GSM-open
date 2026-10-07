"""자료의 층은 둘이고, 둘은 섞이지 않는다.

    레이어군 > 레이어        상류가 주는 것. 사람이 만들지 않는다
    점묶음   > 점            내가 올리는 것. 상류를 타지 않는다

화면에서만 같은 레이어 패널에 나란히 선다. 자세한 것은 CLAUDE.md 의 "자료의 층".
"""
from django.db import models

from .sources import KINDS, RUNS_ON, SCHEDULES


#: 지역. 화면 위의 지역 탭이 이것으로 레이어 목록을 가른다 (devlog 016).
REGIONS = (("korea", "한국"), ("greenland", "그린란드"), ("antarctica", "남극"),
           # 얀마옌 — NPI 지질도를 우리가 그린다 (devlog 022)
           ("jan_mayen", "얀마옌"),
           # 스발바르 — NPI 지도 서버를 중계한다 (devlog 021). "북극" 탭은 지역이 아니라
           # 화면이 그린란드·스발바르·얀마옌을 묶어 보이는 것이라 여기 없다
           ("svalbard", "스발바르"),
           # 일본 — GSJ 심리스 지질도 (devlog 024). "동아시아" 탭도 북극처럼 묶음이라 여기 없다
           ("japan", "일본"),
           # 중국 — USGS geo3al 을 우리가 그린다 (devlog 025). 동아시아 묶음에도 들어간다
           ("china", "중국"),
           # 대만 — 경제부 지질조사·광업관리중심(GSMMA) 지질도 (wetherilli 136). 동아시아 묶음에도 들어간다
           ("taiwan", "대만"),
           # 북극해 — 스발바르·그린란드 밖의 북극. 지금은 KPDC 자료뿐이다 (devlog 076). 북극 묶음에도 들어간다
           ("arctic_ocean", "북극해"),
           # 노르웨이·핀란드 — NGU·GTK 기반암 지질도 (wetherilli 140). 북극 묶음에도 들어간다
           ("fennoscandia", "노르웨이·핀란드"),
           # 영국·프랑스 — BGS·BRGM 지질도 (wetherilli 143). "유럽" 탭은 둘을 모은 묶음이라 여기 없다
           ("uk", "영국"),
           ("france", "프랑스"),
           # 독일·스페인·아일랜드 — BGR·IGME·GSI(·GSNI) 지질도 (wetherilli 147). 유럽 묶음에 든다
           ("germany", "독일"),
           ("spain", "스페인"),
           ("ireland", "아일랜드"),
           # 남미 — 나라 탭 둘과 묶음 하나(wetherilli 191). 콜롬비아는 SGC 의 남미 1:500만(CGMW)·콜롬비아 1:50만(188),
           # 브라질은 SGB. 남미 1:500만은 콜롬비아 지역에 두고 브라질이 빌린다. 묶음 "남미" 는 DB 에 없다(유럽과 같다)
           ("colombia", "콜롬비아"),
           ("brazil", "브라질"),
           # 페루 — INGEMMET 1:5만·1:10만 (wetherilli 195). 남미 1:500만은 브라질처럼 콜롬비아 지역의 것을 빌린다
           ("peru", "페루"),
           # 아르헨티나 SEGEMAR·우루과이 DINAMIGE (wetherilli 196). 남미 1:500만은 콜롬비아의 것을 빌린다
           ("argentina", "아르헨티나"),
           ("uruguay", "우루과이"),
           # 에콰도르 — IIGE 일반 지질도 (wetherilli 198). 남미 1:500만은 브라질·페루처럼 빌린다
           ("ecuador", "에콰도르"),
           # 미국 — USGS SGMC·알래스카 SIM 3340 (wetherilli 205). 북미 묶음은 캐나다가 들어오면 세운다
           ("usa", "미국"),
           # 멕시코 — SGM 1:25만·1:5만 (wetherilli 206)
           ("mexico", "멕시코"),
           # 아프리카 — 대륙 판(CGMW–BRGM 1:1000만)이 바탕이라 탭 하나. 나라 판이 붙으면 그때 가른다 (wetherilli 207)
           ("africa", "아프리카"),
           # 캐나다 — NRCan 1:500만·온타리오 OGS (wetherilli 204). 화면은 캐나다 람베르트(3978)다. 묶음 "북미" 는 DB 에 없다(남미와 같다)
           ("canada", "캐나다"),
           # 호주 — Geoscience Australia 1:250만·1:100만 (wetherilli 212)
           ("australia", "호주"),
           # 이탈리아 ISPRA·포르투갈 LNEG·스위스 swisstopo (wetherilli 211). 유럽 묶음에 들고 EGDI 1:100만은 영국에서 빌린다
           ("italy", "이탈리아"),
           ("portugal", "포르투갈"),
           ("switzerland", "스위스"),
           # 아이슬란드 — 자연사연구소(NÍ) 1:60만·1:10만 (wetherilli 216). 3413 이라 북극 묶음에 든다
           ("iceland", "아이슬란드"),
           # 뉴질랜드 — GNS Science QMAP 1:25만·1:100만 (wetherilli 218). 호주와 묶음 "오세아니아" 에 든다(묶음은 DB 에 없다)
           ("new_zealand", "뉴질랜드"),
           # 몽골 — 국가지질조사소 MonGeoCat 의 국가지질도첩 (wetherilli 221). 동아시아 묶음에 든다
           ("mongolia", "몽골"),
           # 인도 — GSI 1:200만 (wetherilli 226)
           ("india", "인도"),
           # 사우디아라비아 — SGS 1:25만 합본 (wetherilli 227)
           ("saudi", "사우디아라비아"),
           # 동남아 — 인도네시아 ESDM·말레이시아 JMG·필리핀 MGB·태국 DMR (wetherilli 228). 묶음 "동남아" 는 DB 에 없다
           ("indonesia", "인도네시아"),
           ("malaysia", "말레이시아"),
           ("philippines", "필리핀"),
           ("thailand", "태국"),
           # 유럽 — 오스트리아·폴란드·네덜란드·벨기에(플랑드르·왈로니아) (wetherilli 237). 유럽 묶음에 든다
           ("austria", "오스트리아"),
           ("poland", "폴란드"),
           ("netherlands", "네덜란드"),
           ("belgium", "벨기에"),
           # 중앙아메리카·카리브 — 니카라과·도미니카공화국 (wetherilli 242). 푸에르토리코는 미국 탭(wetherilli 238)의 것을 묶음이 빌린다. 묶음 "중앙아메리카·카리브" 는 DB 에 없다
           ("nicaragua", "니카라과"),
           ("dominican_republic", "도미니카공화국"),
           # 카리브 — USGS 카리브 지질도로 쿠바·아이티·자메이카·소앤틸리스와 중미를 거칠게 덮는다 (wetherilli 248)
           ("caribbean", "카리브"),
           # 파나마 — STRI 가 디지털로 옮긴 MICI 1990 1:25만 (wetherilli 253)
           ("panama", "파나마"),
           # 파라과이 — 광업·에너지 차관실(VMME) 지질도 (wetherilli 256)
           ("paraguay", "파라과이"),
           # 프랑스 해외 영토(wetherilli 260) — 누벨칼레도니 Géorep, 프랑스령 폴리네시아 BRGM 스캔
           ("new_caledonia", "누벨칼레도니"), ("french_polynesia", "프랑스령 폴리네시아"))


class LayerGroup(models.Model):
    """레이어를 묶는 것. 씨앗의 `group` 문자열이 여기 행이 된다.

    이름은 **지역 안에서만** 겹치지 않는다 — 그린란드에도 "지질도" 가 있다.
    """

    name = models.CharField("이름", max_length=60)
    region = models.CharField("지역", max_length=20, choices=REGIONS, default="korea")
    order = models.IntegerField("차례", default=0)

    class Meta:
        ordering = ["region", "order", "name"]
        verbose_name = "레이어군"
        constraints = [models.UniqueConstraint(fields=["region", "name"],
                                               name="layergroup_name_per_region")]

    def __str__(self):
        return self.name


class Layer(models.Model):
    """상류 WMS 의 레이어 하나.

    `name` 은 상류에 그대로 넘기는 이름이다. 씨앗은 `geoOpen:` 워크스페이스
    접두사를 떼고 넣는다 — 문서화된 `/openapi/wms` 가 접두사 없는 이름을
    받기 때문이다(`L_250K_Geology_Map`).
    """

    name = models.CharField("레이어명", max_length=120, unique=True)
    title = models.CharField("제목", max_length=200)
    group = models.ForeignKey(LayerGroup, on_delete=models.PROTECT,
                              related_name="layers", verbose_name="레이어군")
    abstract = models.TextField("설명", blank=True)

    # EX_GeographicBoundingBox (EPSG:4326). 레이어로 범위를 맞출 때 쓴다.
    bbox_west = models.FloatField(null=True, blank=True)
    bbox_south = models.FloatField(null=True, blank=True)
    bbox_east = models.FloatField(null=True, blank=True)
    bbox_north = models.FloatField(null=True, blank=True)

    #: 어느 문으로 나가나. kigam → `kigam.py`, geus → `geus.py`, vworld → `vworld.py`,
    #: grportal → `grportal.py` (타일이 아니라 점을 통째로 받는다 — devlog 019),
    #: geomap → `geomap.py` (상류가 아니라 우리 디스크의 파일이다 — devlog 018),
    #: janmayen → `janmayen.py` (NPI 지질도 파일, 모양을 통째로 준다 — devlog 022),
    #: npolar → `npolar.py` (NPI 지도 서버 — 스발바르·드로닝모드랜드, devlog 021),
    #: gsj → `gsj.py` (일본 GSJ 심리스 지질도 — 타일을 z/x/y 로 받는다, devlog 024),
    #: geo3al → `geo3al.py` (USGS 동아시아 지질도 파일, 모양을 통째로 준다 — devlog 025),
    #: phyloserver → `phyloserver.py` (연구실 암맥 기록·한반도 지질도 — devlog 026),
    #: peninsula → `peninsula.py` (한반도 지질도 음영판 PDF 를 잘라 둔 타일 — devlog 027),
    #: gsmma → `gsmma.py` (대만 지질도 — 4326 WMS 를 받고 속성은 지질운 GeoJSON, wetherilli 136),
    #: ngu → `ngu.py`·gtk → `gtk.py` (노르웨이·핀란드 기반암 지질도 — 3575·3413 으로 곧장, wetherilli 140), sgu → `sgu.py` (스웨덴, 3413 으로 곧장, wetherilli 213),
    #: bgs → `bgs.py`·brgm → `brgm.py`·egdi → `egdi.py` (영국·프랑스·범유럽 1:100만 지질도, wetherilli 143),
    #: bgr → `bgr.py`·igme → `igme.py`·gsi → `gsi.py`·gsni → `bgs.py` 의 GSNI (독일·스페인·아일랜드, wetherilli 147),
    #: sgc → `sgc.py` (남미·콜롬비아 지질도, wetherilli 188), sgb → `sgb.py` (브라질 지질도, wetherilli 191),
    #: ingemmet → `ingemmet.py` (페루 지질도 — REST 타일 캐시, wetherilli 195)
    #: segemar → `segemar.py` (아르헨티나 지질도), dinamige → `dinamige.py` (우루과이 지질도, wetherilli 196)
    #: iige → `iige.py` (에콰도르 지질도, wetherilli 198),
    #: mrdata → `mrdata.py` (미국 지질도 — USGS SGMC·알래스카, wetherilli 205), sgm → `sgm.py` (멕시코 지질도 — REST export, wetherilli 206),
    #: sigeom → `sigeom.py`·ygs → `ygs.py` (퀘벡·유콘 지질도, wetherilli 210),
    #: cgmw → `brgm.py` 의 CGMW (아프리카 1:1000만), aga → `bgs.py` 의 AGA (아프리카 지하수 지도책 나라별 지질, wetherilli 207)
    #: nrcan → `nrcan.py` (캐나다 1:500만), ogs → `ogs.py` (온타리오 1:25만, wetherilli 204)
    #: ispra → `ispra.py`·lneg → `lneg.py`·swisstopo → `swisstopo.py` (이탈리아·포르투갈·스위스 지질도, wetherilli 211)
    #: natt → `natt.py` (아이슬란드 지질도 1:60만·1:10만, wetherilli 216)
    #: gns → `gns.py` (뉴질랜드 QMAP·1:100만, 남극 남빅토리아랜드, wetherilli 218)
    #: mris → `mris.py` (몽골 국가지질도첩 지질도·단층, wetherilli 221)
    #: gsiindia → `gsiindia.py` (인도 1:200만 — 그림 BGS, 속성 GSI, wetherilli 226)
    #: sgs → `sgs.py` (사우디 1:25만 합본, wetherilli 227)
    #: esdm·jmg·mgb·dmr → `esdm.py`·`jmg.py`·`mgb.py`·`dmr.py` (인도네시아·말레이시아·필리핀·태국, wetherilli 228)
    #: geosphere·pig·tno·dov·spw → 오스트리아·폴란드·네덜란드·플랑드르·왈로니아 지질도 (wetherilli 237)
    #: ineter → `ineter.py` (니카라과 지질도·단층, wetherilli 242)
    #: georep → `georep.py` (누벨칼레도니 지질도 1:100만·1:20만·1:5만, wetherilli 260)
    #: vmme → `vmme.py` (파라과이 지질도 — 면을 한 덩이로, wetherilli 256)
    #: stri → `stri.py` (파나마 지질도 1:25만 — 면·단층을 한 덩이로, wetherilli 253)
    #: usgscarib → `usgscarib.py` (USGS 카리브 지질도 — 면을 한 덩이로, wetherilli 248)
    #: bcgs → `bcgs.py` (브리티시컬럼비아, 캐나다 탭), calgs → `calgs.py` (캘리포니아, 미국 탭 — `cgs` 는 남아공이 쓴다, wetherilli 231)
    upstream = models.CharField("상류", max_length=20, default="kigam")
    #: 어떻게 그리나. wms → 상류가 그린 타일을 얹는다. vector → 모양을 받아
    #: 우리가 그린다 (단층, devlog 020). 거의 전부가 wms 다
    kind = models.CharField("그리는 법", max_length=10, default="wms",
                            choices=(("wms", "타일"), ("vector", "벡터")))

    queryable = models.BooleanField("클릭해 속성을 읽을 수 있다", default=True)
    enabled = models.BooleanField("레이어 패널에 보인다", default=True)
    order = models.IntegerField("차례", default=0)

    # 문서화된 `/openapi/wms` 로 실제로 그려짐을 확인한 때.
    # 씨앗은 문서에 없는 주소(GetCapabilities)에서 왔으므로, 이것이 비어 있는
    # 레이어는 "상류가 안다고 말했을 뿐 오픈API 로 열렸는지는 모르는" 것이다.
    verified_at = models.DateTimeField("확인한 때", null=True, blank=True)
    verify_note = models.CharField("확인 기록", max_length=200, blank=True)

    class Meta:
        ordering = ["group__order", "order", "title"]
        verbose_name = "레이어"

    def __str__(self):
        return f"{self.title} ({self.name})"

    @property
    def bbox(self):
        vals = (self.bbox_west, self.bbox_south, self.bbox_east, self.bbox_north)
        return list(vals) if all(v is not None for v in vals) else None


class PointSet(models.Model):
    """올린 좌표 묶음 하나. CSV 한 장이 점묶음 하나가 된다."""

    #: 어느 몸의 위경도인가 (devlog 037). 달 좌표를 지구 화면에 그리면 엉뚱한 곳에 뜬다 —
    #: 지구 화면은 `earth` 만, 달 화면은 `moon` 만, 화성 화면은 `mars` 만 읽는다 (058)
    BODIES = (("earth", "지구"), ("moon", "달"), ("mars", "화성"), ("mercury", "수성"))

    name = models.CharField("이름", max_length=120)
    body = models.CharField("몸", max_length=10, choices=BODIES, default="earth", db_index=True)
    source_filename = models.CharField("올린 파일", max_length=255, blank=True)
    color = models.CharField("색", max_length=7, default="#e4572e")
    created_at = models.DateTimeField("올린 때", auto_now_add=True)
    visible = models.BooleanField("지도에 보인다", default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "점묶음"

    def __str__(self):
        return f"{self.name} ({self.points.count()}점)"


class Point(models.Model):
    """점 하나. 위경도는 지구면 EPSG:4326 이다 — 화면이 3857 이어도 그렇다. 달 점묶음이면
    달 경위도(IAU_2015:30100)다 (`PointSet.body`)."""

    pointset = models.ForeignKey(PointSet, on_delete=models.CASCADE,
                                 related_name="points", verbose_name="점묶음")
    label = models.CharField("이름표", max_length=200, blank=True)
    lat = models.FloatField("위도")
    lon = models.FloatField("경도")
    # 원본의 나머지 열. 클릭하면 그대로 표로 뜬다.
    props = models.JSONField("딸린 속성", default=dict, blank=True)
    # 표고 타일에서 읽은 고도(P03). `props` 에 넣지 않는다 — 원본의 `고도` 열(실측)과
    # 섞이면 어느 것이 잰 것인지 가를 수 없다. 출처·기준은 `elevation.SOURCES`
    elev = models.FloatField("표고 (m)", null=True, blank=True)
    elev_source = models.CharField("표고 출처", max_length=40, blank=True)
    elev_datum = models.CharField("높이 기준", max_length=20, blank=True)
    # VWorld 에서 읽은 둘레(074) — 도로명·지번·읍면동·가장 가까운 단층·둘레 지명. 표고처럼 `props` 에
    # 넣지 않는다 — 원본의 `주소` 열과 섞이면 어느 것이 적은 것인지 가를 수 없다. 키는 `vworld.point_facts`
    # 의 것에 받은 날(`at`)을 더한다. 비어 있으면 아직 묻지 않은 것이다
    place = models.JSONField("둘레 (VWorld)", default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "점"

    def __str__(self):
        return self.label or f"({self.lat:.5f}, {self.lon:.5f})"


class Shape(models.Model):
    """점묶음에 딸린 선·면 하나. 조사 경로·권역·잡아 둔 범위 같은 것이다.

    점(`Point`)과 가른 까닭 — **점은 위경도 하나**라는 뜻을 흐리지 않으려는
    것이다(CLAUDE.md "자료의 층"). 기하는 GeoJSON 그대로(EPSG:4326) 둔다.
    공간 연산을 하지 않으므로(TODOs "하지 않기로 한 것") 그릴 수만 있으면 된다.
    `lat`·`lon` 은 범위의 한가운데 — 목록·이름표·범위 맞추기가 쓴다. devlog 012.
    """

    KINDS = (("line", "선"), ("polygon", "면"))

    pointset = models.ForeignKey(PointSet, on_delete=models.CASCADE,
                                 related_name="shapes", verbose_name="점묶음")
    kind = models.CharField("갈래", max_length=10, choices=KINDS)
    geometry = models.JSONField("기하 (GeoJSON)")
    label = models.CharField("이름표", max_length=200, blank=True)
    lat = models.FloatField("가운데 위도")
    lon = models.FloatField("가운데 경도")
    props = models.JSONField("딸린 속성", default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "모양"

    def __str__(self):
        return self.label or f"{self.get_kind_display()} ({self.lat:.5f}, {self.lon:.5f})"


class PointSetDeletion(models.Model):
    """지운 점묶음의 기록 — 누가(접속한 곳)·언제·무엇을.

    **지운 것의 사본(GeoJSON)도 남긴다.** 점묶음은 사람이 올리거나 찍은 것이라
    상류에서 다시 받을 길이 없다. 잘못 지웠으면 `manage.py deleted_pointsets
    --restore <번호>` 로 되살린다. devlog 014.
    """

    name = models.CharField("이름", max_length=120)
    body = models.CharField("몸", max_length=10, choices=PointSet.BODIES, default="earth")
    color = models.CharField("색", max_length=7, blank=True)
    source_filename = models.CharField("올린 파일", max_length=255, blank=True)
    created_at = models.DateTimeField("올린 때", null=True, blank=True)
    deleted_at = models.DateTimeField("지운 때", auto_now_add=True)
    client = models.CharField("지운 곳 (접속 주소)", max_length=64, blank=True)
    points = models.PositiveIntegerField("점", default=0)
    lines = models.PositiveIntegerField("선", default=0)
    polygons = models.PositiveIntegerField("면", default=0)
    snapshot = models.JSONField("사본 (GeoJSON)", default=dict)
    restored_at = models.DateTimeField("되살린 때", null=True, blank=True)

    class Meta:
        ordering = ["-deleted_at"]
        verbose_name = "지운 점묶음"

    def __str__(self):
        return f"{self.deleted_at:%Y-%m-%d %H:%M} {self.name}"


class UpstreamDay(models.Model):
    """상류에 하루 몇 번 물었나. **한계를 재지 않고 지켜보려고** 둔다.

    KIGAM 은 호출 제한의 수치를 밝히지 않는다("지나치게 잦은 호출"). 걸릴
    때까지 두드려 재면 걸리는 순간 서버 IP 가 막힌다. 그래서 두드리지 않고
    평소에 얼마나 묻는지, 차단 조짐(403·429·`Request Blocked`)이 있었는지를
    날마다 센다. `manage.py upstream_stats` 가 보여준다. devlog 010.
    """

    day = models.DateField("날짜")
    upstream = models.CharField("상류", max_length=20)     # kigam · vworld
    ok = models.PositiveIntegerField("성공", default=0)
    fail = models.PositiveIntegerField("실패", default=0)
    blocked = models.PositiveIntegerField("차단 조짐", default=0)
    # 걸린 시간 (wetherilli 290) — 문이 받은 응답의 `elapsed`(보내고 머리를 받기까지). 잰 건수·합(초)과 칸마다의 건수.
    # 칸의 위 끝은 `usage.TIME_BUCKETS` 다(0.5·1·2·3·5·8·13·21·34 초, 마지막 칸은 그 너머). p95 는 칸에서 어림한다
    # db 에도 기본값을 둔다 — 판을 v0.59 로 되돌려도 이 열을 모르는 옛 코드가 행을 넣을 수 있게 (wetherilli 299)
    timed = models.PositiveIntegerField("잰 건수", default=0, db_default=0)
    seconds = models.FloatField("걸린 시간 합(초)", default=0.0, db_default=0.0)
    t0 = models.PositiveIntegerField(default=0, db_default=0)
    t1 = models.PositiveIntegerField(default=0, db_default=0)
    t2 = models.PositiveIntegerField(default=0, db_default=0)
    t3 = models.PositiveIntegerField(default=0, db_default=0)
    t4 = models.PositiveIntegerField(default=0, db_default=0)
    t5 = models.PositiveIntegerField(default=0, db_default=0)
    t6 = models.PositiveIntegerField(default=0, db_default=0)
    t7 = models.PositiveIntegerField(default=0, db_default=0)
    t8 = models.PositiveIntegerField(default=0, db_default=0)
    t9 = models.PositiveIntegerField(default=0, db_default=0)
    # 그 가운데 화면이 아니라 손으로 부른 명령(대조·미리 데우기·받기)이 낸 것 (wetherilli 363) — 대조 하루는 화면 하루보다 수가 커서 덮였다(347)
    batch = models.PositiveIntegerField("명령이 낸 것", default=0, db_default=0)

    class Meta:
        ordering = ["-day", "upstream"]
        constraints = [models.UniqueConstraint(fields=["day", "upstream"],
                                               name="upstream_day_once")]

    def __str__(self):
        return f"{self.day} {self.upstream} {self.ok}/{self.fail}/{self.blocked}"


# ── 데이터소스 (jikhanjung P03) ─────────────────────────────────────────
#
# 받아 두는 바깥 자료의 명세와 받은 차례의 기록. 둘 다 처음엔 파일이었다(P02 — `<DB 옆>/sources.json`·`store.sqlite` 의 `fetch_log`).
# 명세는 사람이 정하는 것이라 화면(지금은 admin)에서 고치고 이력을 남기려고, 기록은 명세와 잇고 표 구조를 마이그레이션이 맡게 하려고
# 여기로 옮겼다. 받은 판의 정보(파일·sha256·받은 때)는 원본 폴더의 `manifest.json` 에 그대로 둔다(`rawstore.py`).
# 검사·씨앗·화면은 `sources.py`, 기록을 읽고 쓰는 것은 `fetchlog.py` 가 맡는다 — 바깥에 내는 꼴(줄의 dict)은 파일 시절 그대로다.

class DataSource(models.Model):
    """명세 한 줄 — 무엇을 받나(조건·주기·돌리는 곳·명령·산출물·원본 자리)."""

    id = models.CharField("id", max_length=64, primary_key=True)
    order = models.PositiveIntegerField("차례", default=0)
    name_ko = models.CharField("이름", max_length=200)
    name_en = models.CharField("영어 이름", max_length=200)
    org = models.CharField("기관", max_length=300, blank=True, default="")
    # 고를 수 있는 값은 `sources` 의 표 하나 — admin 이 고르게 하고, 검사(`problems_of`)와 같은 것을 본다
    kind = models.CharField("갈래", max_length=16, choices=[(k, k) for k in KINDS])
    runs_on = models.CharField("돌리는 곳", max_length=16, choices=[(k, k) for k in RUNS_ON])
    schedule = models.CharField("주기", max_length=32, choices=[(k, k) for k in SCHEDULES])
    license = models.CharField("조건", max_length=500)
    flags = models.JSONField("표시", default=list, blank=True)
    commands = models.JSONField("명령", default=list, blank=True)
    outputs = models.JSONField("산출물", default=list, blank=True)
    raw = models.CharField("원본 자리", max_length=300, blank=True, default="")
    docs = models.JSONField("근거", default=list, blank=True)
    note = models.TextField("메모", blank=True, default="")
    updated_at = models.DateTimeField("고친 때", auto_now=True)
    updated_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+", verbose_name="고친 사람")

    #: 파일 시절의 줄(dict)과 오가는 칸 — `name` 만 두 칸으로 갈렸다
    ROW_KEYS = ("org", "kind", "commands", "runs_on", "schedule", "license", "flags", "outputs", "raw", "docs", "note")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "데이터소스"
        verbose_name_plural = "데이터소스"

    def __str__(self):
        return f"{self.id} — {self.name_ko}"

    def as_row(self) -> dict:
        row = {"id": self.id, "name": {"ko": self.name_ko, "en": self.name_en}}
        row.update({k: getattr(self, k) for k in self.ROW_KEYS})
        return row

    @classmethod
    def fields_of(cls, row: dict) -> dict:
        """줄(dict) → 모델의 칸. 빠진 칸은 비운다"""
        name = row.get("name") or {}
        out = {"name_ko": name.get("ko", ""), "name_en": name.get("en", "")}
        for k in cls.ROW_KEYS:
            default = [] if k in ("flags", "commands", "outputs", "docs") else ""
            out[k] = row.get(k, default)
        return out

    def clean(self):
        from django.core.exceptions import ValidationError

        from . import i18n, sources
        # admin 에서 목록 칸을 비우면 폼이 None 을 넘긴다 — 빈 목록으로 받는다 (#381 검토 7)
        for k in ("flags", "commands", "outputs", "docs"):
            if getattr(self, k) in (None, ""):
                setattr(self, k, [])
        found = sources.problems_of(self.as_row())
        if found:
            raise ValidationError([i18n.t(m) for m in found])


class DataSourceChange(models.Model):
    """명세의 이력 — 고칠 때마다 한 줄, 앞뒤 줄 전체를. 지운 줄도 남게 데이터소스를 글로 적는다."""

    ORIGINS = (("admin", "admin"), ("tab", "관리 화면"), ("seed", "씨앗"), ("import", "파일에서 옮김"))
    source = models.CharField("데이터소스", max_length=64, db_index=True)
    at = models.DateTimeField("때", auto_now_add=True)
    by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                           verbose_name="누가")
    # 계정을 지워도 누가 고쳤는지 남게 이름을 글로도 (#381 검토 5)
    by_name = models.CharField("누가(이름)", max_length=150, blank=True, default="")
    origin = models.CharField("어디서", max_length=16, choices=ORIGINS)
    before = models.JSONField("앞", null=True, blank=True)
    after = models.JSONField("뒤", null=True, blank=True)

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name = "데이터소스 명세의 이력"
        verbose_name_plural = "데이터소스 명세의 이력"

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.source} ({self.origin})"


class FetchRun(models.Model):
    """받은 차례 한 줄 — 언제·결과·걸린 초·마지막 말·센 수 대 받은 수·원본 자리와 sha·구운 판.

    데이터소스는 글이다 — 명세 밖의 것(명세에 없는 명령은 명령 이름)도 받게. 같은 (데이터소스·시작한 때·어디서)는 한 번만.
    호스트는 여기 쓰지 않는다 — 컨테이너가 호스트의 기록을 옮겨 적는다(`fetchlog.sync`).
    """

    source = models.CharField("데이터소스", max_length=64)
    command = models.CharField("명령", max_length=100, blank=True, default="")
    started_at = models.DateTimeField("시작한 때")
    seconds = models.FloatField("걸린 초", null=True, blank=True)
    result = models.CharField("결과", max_length=8)                # ok · fail · skip
    note = models.TextField("마지막 말", blank=True, default="")
    upstream_version = models.CharField("상류 판", max_length=300, blank=True, default="")
    expected = models.IntegerField("센 수", null=True, blank=True)
    rows = models.IntegerField("받은 수", null=True, blank=True)
    changed = models.IntegerField("바뀐 것", null=True, blank=True)
    raw_path = models.CharField("원본 자리", max_length=500, blank=True, default="")
    raw_sha256 = models.CharField("원본 sha256", max_length=64, blank=True, default="")
    built_at = models.CharField("구운 때", max_length=40, blank=True, default="")
    built_by = models.CharField("구운 것", max_length=200, blank=True, default="")
    estimated = models.BooleanField("어림", default=False)
    origin = models.CharField("어디서", max_length=16, default="container")   # container · hourly · host · backfill

    class Meta:
        ordering = ["-started_at", "-id"]
        verbose_name = "받은 차례"
        verbose_name_plural = "받은 차례"
        constraints = [models.UniqueConstraint(fields=["source", "started_at", "origin"], name="fetch_run_once")]
        indexes = [models.Index(fields=["source", "started_at"], name="fetch_run_source")]

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} {self.source} {self.result}"


class FetchRunMark(models.Model):
    """옮겨 적기가 기억할 것 — 호스트 기록(jsonl)을 어디까지 읽었나 따위. 열쇠·값 한 줄씩."""

    key = models.CharField(max_length=64, primary_key=True)
    value = models.CharField(max_length=200)
