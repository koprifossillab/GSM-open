"""자료의 층은 둘이고, 둘은 섞이지 않는다.

    레이어군 > 레이어        상류가 주는 것. 사람이 만들지 않는다
    점묶음   > 점            내가 올리는 것. 상류를 타지 않는다

화면에서만 같은 레이어 패널에 나란히 선다. 자세한 것은 CLAUDE.md 의 "자료의 층".
"""
from django.db import models


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
           ("belgium", "벨기에"))


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

    class Meta:
        ordering = ["-day", "upstream"]
        constraints = [models.UniqueConstraint(fields=["day", "upstream"],
                                               name="upstream_day_once")]

    def __str__(self):
        return f"{self.day} {self.upstream} {self.ok}/{self.fail}/{self.blocked}"
