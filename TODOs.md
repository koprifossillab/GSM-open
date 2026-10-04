# 할 일

지금 무엇을 할 수 있는지 고르는 자리다. 왜 그렇게 했는지는 `devlog/`,
지금 어디까지 왔는지는 `HANDOFF.md`.

## 연구소 밖 정적 판 (P11)

- [ ] **(사람) 밖에서 쓸 KIGAM 키** — 휴대폰에서 안 뜬 까닭은 키였다: 키를 신청할 때 연구소 IP 를 적어 그 IP 밖에서는 KIGAM 이 거절한다
      (사용자 확인, 2026-10-04 — wetherilli 179 의 남은 갈래 (2)). 밖에서 쓰려면 IP 를 묶지 않은(또는 쓸 곳을 넓힌) 키를 따로 받는다.
      정적 판은 각자 키라 다른 사람은 자기 키로 본다. 키 창의 "주지 않았다" 안내가 이 경우를 말한다

## 다른 대륙 — 아메리카·아프리카 (2026-10-04 실측, [docs/다른_대륙_지질도.md](docs/다른_대륙_지질도.md))

세 대륙 30 여 후보를 찔러 본 것이다. 품은 상류 문 하나만 친 값이고, 탭을 새로 세우는 품은 따로 든다. **남미부터 연다**(사용자, 2026-10-04).

### 남미 — 연다

- [ ] **(사람) 남미 1:500만의 CGMW 이용 조건** — 남미 탭은 SGC 로 섰다(wetherilli 188). CGMW 는 지도를 판다 — 정적 판·밖에 열기 전에 읽는다.
      읽고 되면 정적 판에 싣는다(CORS 가 열려 있어 `static-kinds.js` 한 갈래)
- [ ] (사람) 운영에서 `manage.py fetch_sgb_units` 를 한 번 — 브라질 범례에 단위 이름·시대가 붙는다(없으면 기호만). 1:100만은
      WFS 열 번 남짓·1 초 간격 (wetherilli 191)
- [ ] (사람) 우루과이 DINAMIGE 1:50만의 이용 조건 — 탭은 섰다(wetherilli 196). Capabilities·MIEM 안내에 적힌 것이 없다. 밖에 열기 전에 읽는다
- [ ] (사람) 파라과이 VMME 지질도의 이용 조건 — 탭은 섰다(wetherilli 256). 서비스·대시보드에 적힌 것이 없다. 밖에 열기 전에 읽는다
- [ ] (사람) 프랑스령 기아나 BRGM 1:50만 셰이프(`Guyane.zip`, 6.7 MB)를 InfoTerre DROM 양식으로 받아 NAS 에 — 이름·전자우편을 적는다.
      받으면 파일을 한 덩이로 내는 문(얀마옌 꼴)으로 기아나 탭을 세운다. 반나절 (wetherilli 256)
- [ ] 대만 지질운 자료 목록(`geologycloud.tw/data/zh-tw`)에 WMS 가 없는 것 — 5만 탄층(CoalSeam)·토석류 퇴적·선상·유동구(DebrisFlow*)·낙석(RockFall)·
      GPS 상시 관측소(CGPS)·암석 강도·암체 등급(RockMass*). 열린자료(사성급)라 점·선을 한 덩이로 받아 그리는 꼴(카리브·파나마)로 붙일 수 있다. 반나절 (wetherilli 263)
- [ ] 누벨칼레도니 1:5만은 상류가 "재정비 중" 이라 적는다 — 새 판이 오면 범례에 1:5만(253 칸)을 더할지 본다 (wetherilli 260)
- 막힌 것(태평양, wetherilli 260): 피지(공개 서비스 없음 — 1:5만은 종이판)
- 막힌 것(2026-10-05 다시 봄, wetherilli 256): 칠레 SERNAGEOMIN(무응답·DNS 없음), 볼리비아(8080 거부 — 뷰어가 지금도 그 주소만 부른다.
  열리면 GeoServer 1:100만 `geologico:geologico_1M`), 수리남(토큰), 가이아나(신청해 받는 자료), 베네수엘라(서비스 없음).
  이 나라들은 남미 1:500만 둘(SGC·USGS)이 덮는다

### 북미

- [ ] **(사람)** 캐나다 탭(NRCan 1:500만·온타리오 OGS, wetherilli 204)을 정적 판에 실을지 — OGL 이고 CORS 가 되비친다(#153)
- [ ] 브리티시컬럼비아(BCGS)는 줌 11 부터 그린다(wetherilli 231). 넓게도 칠하려면 색 스타일(640 KB)을 줄여 SLD 로 보내거나, openmaps 에 작은 축척 판이 있는지 찾는다(훑지 않았다). 다른 주(앨버타·서스캐처원·매니토바·노바스코샤…)는 아직
- [ ] 캐나다 지구물리(자력·중력 격자) — NRCan 지도 서버에 없다. GSC 의 CAGDB WMS(`wms.agg.nrcan.gc.ca/wms2/wms2.aspx`)는 2026-10-05 에
      60 초 안에 답하지 않았다 — 살아나면 캐나다 탭에(wetherilli 250). 편찬 지질도 CGMC 는 래스터라 누르면 칸 번호뿐이다 — 번호 → 단위 표를 찾으면 누르게
- [ ] 캐나다 주 판 — **(사람)** 뉴브런즈윅(`gis-erd-der.gnb.ca/…/OpenData/NBGS_Bedrock_Geology`
      WMS·WFS 가 열려 있다)·뉴펀들랜드래브라도(`dnrmaps.gov.nl.ca/…/GeoAtlas/Bedrock_Geology_All` WMS)는 조건을 읽지 못했다 — 뉴브런즈윅 조건
      쪽은 우리에게 403, WMS 의 조건 칸은 둘 다 비었다. 매니토바(`maps.gov.mb.ca`)는 2026-10-04 에 502. 노스웨스트준주는 ArcGIS Online 의
      피처 서비스(`MapD1860A_NWTGeology`)뿐이라 그림이 없다 — 우리가 그려야 한다. 누나부트는 서비스를 찾지 못했다
- [ ] 미국 — 3978 이라 하와이가 50° 남짓 돌아 보인다(wetherilli 238) — 바로 세우려면 섬 탭을 따로 두거나 미국 탭의 투영을 고른다
      (투영을 바꾸는 일이라 미뤘다)
- [ ] 멕시코 SGM 지자기(`DatosAbiertos/DatosAbiertos` 7 `Campo magnético esc 1:250,000`). 2026-10-05 에 다시 쟀다(wetherilli 244) — 나라를 다 덮지만 **타일 한 칸(256 px)이 줌과 상관없이
      10 초 넘게**(줌 5 54 초·6 25 초·8 11 초·10·12 10 초) 걸린다. 그리는 시간이 아니라 요청마다 드는 값이다 — 1024 px 한 장(줌 8 칸 열여섯)이
      21.6 초다. 캐시가 없고 값도 색 칸(0–16)뿐이라 nT 를 모른다. 쓰려면 큰 장을 받아 잘라 담는 길(메타타일)과 미리 데우기를 새로 지어야 해
      두었다. 고생물·광산 점은 그림 기호라 범례가 없다
- 막힌 것: USGS 북미 지질도 GMNA(403), ScienceBase(503), NGMDB(지도 API 없음)

### 중앙아메리카·카리브 (2026-10-05 실측, [docs/다른_대륙_지질도.md](docs/다른_대륙_지질도.md) 끝 절)

- [ ] 니카라과 INETER·도미니카공화국 SGN 1:25만은 섰다(wetherilli 242, 묶음 "중앙아메리카·카리브" — 푸에르토리코는 미국 탭의 것을 빌린다). **(사람)** INETER·SGN 의
      조건 문구가 없다(AccessConstraints NONE·빈 칸) — 밖에 열기 전에 읽는다
- [ ] 프랑스령 앤틸리스 BRGM 1:5만 스캔(`GEOL_MART`·`GEOL_GUAD_*`) — `brgm.py` 에 이름만, 줌 12 부터. 탭을 어디에 둘지(묶음에 지역 하나 더)
- [ ] **(사람)** 자메이카 MGD 웹맵의 지질 면(조건 없음)·트리니다드 Latinum(교육용 한정) — 조건을 묻는다
- 막힌 것: 과테말라·온두라스·벨리즈·쿠바(서비스 없음·DNS·시간 초과), 엘살바도르 SNET(522 — 다시 볼 것), 코스타리카(UCR 여백 붙은 스캔·DGM 빈 응답)

- [ ] 남미 광물·지구물리(wetherilli 265·277) — 브라질 광물 산출·콜롬비아 금속광상도/지구물리·아르헨티나 광상·페루 광물·지구물리는 섰다. 남은 것:
      브라질 opendata 의 광업 권역(ANM)·항공 지구물리 조사 범위, SEGEMAR 자력 이상(나라 전체 면 47 개뿐이라 뺐다), 페루 광업 권리(`SERV_CATASTRO_MINERO`)·
      지화학 지도첩(`SERV_ATLAS_GEOQUIMICO`)·산업 광물(`SERV_ROCAS_MINERALES_INDUSTRIALES`)

- [ ] 캐나다 주 광물(wetherilli 288) — BC·유콘 MINFILE, 온타리오 MDI, 퀘벡 가동 광산·사업, 사스카치원 SMDI 는 섰다. 남은 것: 앨버타 금속·산업 광물 산지는
      ArcGIS Online 피처 서비스(`Metallic_Mineral_Occurrences`·`Industrial_Mineral_Occurrences`)뿐이라 그림 길이 없다 — 파나마(stri)처럼 한 덩이로 받아
      화면이 그릴지. 노바스코샤는 광물 산지 서비스를 찾지 못했다. 퀘벡의 광물 산지(gîte)는 WMS 에 없다(SIGÉOM 의 다른 서비스를 찾을 것)

- [ ] 아시아 광물(wetherilli 280) — 인도네시아·필리핀·태국·사우디·몽골 희토류는 섰다. 남은 것: 말레이시아 MyGEMS 는 `rest/services` 목록이 허브 쪽으로
      넘어가 광물 서비스를 찾지 못했다, 인도 GSI 는 Bhukosh 가 나라 밖에서 닿지 않는다. 몽골 `Atlas/AtlasPoints` 의 광상 레이어(6–9)는 우물 자료를
      돌려준다 — 고쳐지면 금속·비금속·연료·전략 광상. 태국 지구물리 탐사 지점·사우디 지구물리 사업 범위는 범위뿐이라 뺐다.
      다섯 곳 모두 이용 조건이 적혀 있지 않다 — 정적 판에 싣기 전에 사람이 읽는다

- [ ] 아프리카 광물(wetherilli 285) — 남아공 광업·석탄·우라늄 지역(DPME 사본)만 섰다. 나미비아 GSN·부르키나파소 BUMIGEB(BGS OneGeology)·카메룬 IRGM(BRGM)
      WMS 는 지질 단위·단층뿐이고, BGS ArcGIS 의 아프리카 폴더는 지하수뿐이다(`Ghana`·`Kenya` 폴더는 비었다). CGS 자신의 서버(`maps.geoscience.org.za`)는
      여전히 시간 초과다. 광상 점은 SIGAfrique(BRGM)·나라 지질조사소 포털에 물어야 한다

- [ ] 오세아니아 광물·지구물리(wetherilli 269) — 퀸즐랜드·빅토리아·남호주·뉴질랜드 중력은 섰다. 남은 것: 뉴질랜드 광물 산지 GERM(`gns:GERM_ERML_VIEW`)은
      가까이 봐도 빈 그림이다(스타일이 없거나 축척 제한) — GNS 에 물을지. 빅토리아 중력 측점(`gravity`)·자력 선형(`lineaments_tmi`), 남호주 지구물리(SARIG 영상)

- [ ] 북유럽 광물·지구물리(wetherilli 270) — GTK·FODD·SGU 는 섰다. 노르웨이 NGU 의 광물·지구물리 서비스 주소를 못 찾았다(`geo.ngu.no/mapserver/*` 이름 짐작은 404·빈 map). 스웨덴 중력은 측정 범위뿐

### 아프리카

- [ ] **(사람) 아프리카 1:1000만의 CGMW 이용 조건** — 아프리카 탭은 CGMW–BRGM 1:1000만과 BGS 지하수 지도책으로 섰다(wetherilli 207).
      CGMW 는 인쇄판을 판다 — 정적 판·밖에 열기 전에 읽는다(남미 1:500만과 같다). CORS 가 `*` 라 되면 `static-kinds.js` 한 갈래
- [ ] 아프리카 지하수 지도책의 수리지질(`<ISO3>_BGS_5M_Hydrogeology`) — 같은 서버·같은 조건(CC BY-SA). 지질 탭에 둘지 사람이 본다
- [ ] **(사람) 콩고민주공화국·르완다·부룬디 — 벨기에 RMCA GeoServer**(`edit.africamuseum.be/geoserver`) — DRC 1:200만(`COD_RMCA_2M_*`)·르완다·부룬디
      1:25만(`RWABDI_RMCA_250K_*`)·카탕가 1:20만(`geco_geology`)·PROMINES 2015 DRC 지질도(`METAFRO_RDC_Mining`)가 3857·CORS `*` 로 열려 있다
      (wetherilli 246). 조건이 "© RMCA, Other restrictions" 이고 PROMINES 판은 "공개 자료가 아니다" 라는 글도 있다 — maps@africamuseum.be 에 묻고 정한다.
      이집트 웨스턴미시간대 Nubian 사업 서버(EGSMA 1:200만)도 조건 미상이라 함께 둔다. 보츠와나·잠비아·짐바브웨·케냐·우간다·가나·에티오피아·
      말리·세네갈·마다가스카르는 지도 서비스를 찾지 못했다(정부 지질조사소 포털이 없거나 닿지 않는다 — BGS AGA·CGMW 가 덮는다)
- [ ] **(사람) 탄자니아 GMIS 1:150만** — 서버(`gmis-tanzania.com`)가 중간 인증서를 빼먹어 바깥에서도 TLS 검증이 실패하고, 연구소 망은
      "UNTRUSTED CERT ALERT" 로 다시 서명한다(2026-10-04, wetherilli 209). TLS 검증을 끄지 않고는 받을 수 없다 — 끌지(그 호스트만), 서버가
      고칠 때까지 둘지 사람이 정한다(#153)
- [ ] (사람) 남아공 CGS·나미비아 GSN 을 서버 캐시에 담아도 되는지 — 둘 다 자료를 파는 곳이라 지금은 담지 않고 그때그때 받는다(`views.NO_STORE`).
      남아공의 넓은 그림은 한 장에 11 초까지 걸린다
- 막힌 것: SIGAfrique(호스트 없음), USGS certmapper(403), OneGeology 포털(닫힘), 모로코·나이지리아(서비스 없음)

### 아시아·오세아니아·북대서양 섬 (2026-10-04 실측, [docs/아시아_오세아니아_지질도.md](docs/아시아_오세아니아_지질도.md))

- [ ] **(사람)** 밖에 열기 전에 조건을 읽는다 — 몽골 MonGeoCat(wetherilli 221)·인도 GSI(226, Bhukosh 가 막혀 못 읽었다)·사우디 SGS(227)·
      동남아 넷(228 — 인도네시아 ESDM·말레이시아 JMG·필리핀 MGB·태국 DMR)은 조건이 적혀 있지 않다
- [ ] **(사람)** 정적 판에 실을지 — 아이슬란드 NÍ(wetherilli 216, CC BY 4.0·CORS `*`)·뉴질랜드 GNS(218, 속성 CORS 가 막혀 타일만 된다)
- [ ] **(사람)** 아이슬란드 ÍSOR 1:10만·페로 Jarðfeingi — 조건을 묻고 나서 붙인다
- 막힌 것: 인도 Bhukosh·러시아 VSEGEI·카자흐스탄·튀르키예 MTA·이란·이스라엘(나라 밖 차단), 파푸아뉴기니 MRA(등록제),
베트남·라오스·캄보디아·미얀마·오만(서비스 없음 — CCOP 200만으로), 카타르·쿠웨이트·이라크·파키스탄·네팔·스리랑카·방글라데시·아프가니스탄(서비스 없음·닿지 않음,
wetherilli 249 — 네팔 DMG GeoServer 는 열렸지만 행정 경계·도폭뿐)

## 지역 — 극지 (016·017·018·019·021·022)

- [ ] 그린란드 지구물리(wetherilli 259) — GEUS ArcGIS 의 방사능(`Geophysics_Radiometry`)은 국지 조사 몇 곳뿐이라, 공중 자력(`Geophysics_Aeromag_Magnetic`·
      `_AWI`·`Aem_Magnetic`)·1:250만·1:10만 지질도(`Geological_map_2500k`·`_100k_SSW`·`_100k_Karrat`)는 같은 서버에 있어 더할 수 있다.
      지도 화면의 광물 산지 v3(`mineral_occurrences_v3_external`)는 WMS 이름이 403 — 포털(grportal)의 광물 산지가 같은 뿌리다
- [ ] **(사람)** 그린란드 50만 지질도는 GEUS 가 추린 판(`_search`)이다. 원본
      (`grl_g500_lithostr_units`)을 WMS 로 열어 주는지 GEUS 에 묻는다 —
      써 보고 빈 곳이 거슬리면 사람이 메일을 쓴다. 같은 메일에 정부 포털 시료가
      딱 2 만 점에서 잘린 것과 시료 좌표가 1 km 가량 어긋나는 것도 묻는다 (019)
- [ ] 배포 뒤 `manage.py fetch_grportal` 을 한 번 — 시료 2 만 점을 처음 켜는 사람이
      17 초를 기다리지 않게 (019). **NPI 점·지명·도폭 경계도 이제 같은 명령이 받는다** (029). 그린란드·드로닝모드랜드
      지명도 받는다 — 안 받아 두면 그린란드 첫 지명 찾기가 24 초 걸린다 (wetherilli 096)
- [ ] EOX Sentinel-2 는 비상업(CC BY-NC-SA) 조건이다 — 밖에 열 때 다시 본다.
      3857 이라 북위 85° 위가 둥글게 빈다 (017)
- [ ] Esri Antarctic Imagery 는 Esri 이용 조건(Master License Agreement)이다 — EOX 처럼 밖에 열 때 다시 본다 (040)
- [ ] (검토) DiaRUGA·ForGIA 의 남극·남빙양 지점과 잇기 — CLAUDE.md 대로 DB 는 나누지 않고 `Locality.lat/lon` 을
      내보내 점묶음으로 받는다. 수심 읽기(070)가 섰다 — 올리면 수심이 붙는다 (사람, 2026-09-29, 047)
- [ ] **(사람)** KPDC 공개 정책을 보고 `LAB_ONLY` 에서 `kopri` 를 뺄지 정한다 (053). 본문은 2026-09-30 에 읽었다
      (영문, 제10–11조). "과학적 목적으로 자유롭게" 공개하되, **자료를 쓰려는 이는 범위·목적을 적어 신청하고**
      (14 일 안에 심사), 알린 범위 안에서만 쓰며 출처를 밝히고 결과를 알린다(11조, "추가 논의 필요" 로 적혀 있다).
      우리가 보이는 것은 자료 자체가 아니라 목록(제목·위치·키워드)과 지도 서버의 선이다 — 목록은 AMD 에 올리라고
      한 메타데이터라 공개 쪽으로 읽히지만, 암석 시료·운석 목록을 밖에 다시 내주는 것이 "이용" 인지는 정책이 말하지
      않는다. 밖에 열기 전에 kpdc@kopri.re.kr 에 묻는 것이 안전하다
- [ ] 운영에서 `manage.py fetch_kopri` 를 가끔 — 새로 올라온 KPDC 자료만 받는다(목록 여덟 장 + 새 상세). 처음 모은 것은
      2026-09-29 밤 `/srv/GSM/db/kopri/` 에 두었다 (053)
- [ ] (사람) 아라온 해양 자료 백여 건이 같은 기본 네모(북위 60–80°, 160°E–150°W)만 적어 북극해 지도에서 빠진다 —
      항적이 따로 있는지 KPDC 에 묻는다. Midtre Lovénbreen 의 경도 부호(075 §5)와 같은 메일에 (076)
- [ ] 암석 시료의 상세(암상·박편·3D 모델) — 상세 페이지가 로그인 없이는 비어 있다. 극지연구소에 묻는다 (053)
- [ ] KPDC 의 다른 묶음 — PAMC 미생물 균주(2 만 2 천)·KVH 식물 표본(3 천 8 백). 지질과 거리가 있어 미뤘다 (053)
- [ ] **(사람)** BAS 의 ArcGIS Online 피처 서비스 — 암석 표본 목록 `geology_collection`(14 만 3 천)·해양·호수·이탄 코어(966·…)·빙하 코어(84)·
      SCAR 지명 사전 `SCAR_CGA_PLACE_NAMES_SIMPLIFIED`(남극 전체의 지명 찾기 — 지금은 드로닝모드랜드뿐). 열려 있고 CORS 도 되지만 항목에
      **이용 조건 글이 없다**. BAS·SCAR 에 묻거나 UK PDC 의 원자료 조건을 읽고 정한다. 14 만 점은 한 덩이로 받기 무거워 극지연구소처럼 모아 둔다 (wetherilli 261)

## 지역 — 일본·동아시아 (024)

- [ ] **GSM 을 밖에 열기 전에 geo3al(중국)을 내린다** — "내부 용도만, 가공물 포함 재배포 금지" (025).
      스위치가 생겼다 — `GSM_PUBLIC=1`(또는 `<DB 옆>/public`)이면 geo3al·한반도 지질도·암맥이 내려간다 (029)
- [ ] 중국지질조사국 1:250만 수치지질도(`10.23650/data.H.2017.NGA121474`) — 사람이 받을 수
      있는지·조건을 확인 중. 오면 geo3al 을 밀어낸다 (025). 자료 출판 시스템(dcc)이 국외에서 응답하지 않아 조건을 읽지 못했다.
      GeoCloud 지도 서비스는 국외 차단·신청제라 붙일 수 없다 — [docs/중국_GeoCloud.md](docs/중국_GeoCloud.md)
- [ ] (사람) P04 §5 — 어디까지 자르나·어느 탭에 두나. Dropbox 묶음을 받을 때 안의 조건 글도 본다

- [ ] GSJ 는 호출 제한 수치를 밝히지 않는다 — `upstream_stats` 의 `gsj` 를 지켜본다
- [ ] GSJ 의 다른 WMS — 1:200만 지질도·중력은 누르면 기호 번호뿐(wetherilli 255). 범례의 번호 → 이름 표를 뜨면 누르게 할 수 있다.
      지구화학도 53 원소·공중 자력 편집도 셋은 섰다(wetherilli 266)

## 달 (P05)

대돌여지도 아이콘의 숨은 차림 → 둥근 달(CesiumJS). 지역 탭이 아니다. 테마는 흑백.

- [ ] (사람) P05 §8 — 달 시대 한국어 표기를 본다(지금 `trek.AGES_KO`), 다누리 KGRS 자료가 열려 있는지,
      원소·광물 레이어군을 둘지, Trek 이용 조건
- [ ] (사람) Kaguya(JAXA) 자료의 이용 조건을 읽는다 — 밖에 열기 전에 (043)
- [ ] (사람) 창어 2 호(CE-2 CCD, CNSA/CLEP) 정사 모자이크의 이용 조건 — 극 평면의 고해상 배경이다. Trek 을 거쳐
      받지만 자료의 주인은 중국 달 탐사 계획이다. 밖에 열기 전에 (052)
- [ ] (사람) 달 Trek 판 한글 제목 초안(몸 전체를 덮는 114 판)을 읽고 고친다 — `data/moon_trek_layers.json` 의 `ko` (060)
- [ ] (사람) SPA 지질도 원본(Zenodo 10.5281/zenodo.19728952 의 `GeoMap.tif.zip`·`Mapplate.zip`)을 NAS `sources/moon/` 에 둔다.
      운영 `db/moon/` 에는 두었다 (wetherilli 081)

## 온 지구 (P06·P07)

(2026-09-30 운영 `/srv/GSM/db/earth/` 에 옛 해안선·화석 산지·맨틀을 두었다. 화석 산지는 가끔 `fetch_pbdb` 로 새로 받는다)

- [ ] **(사람)** RGI 7.0 빙하 **윤곽** — NSIDC-0770 은 NASA Earthdata 로그인 뒤에만 받힌다. 계정을 만들어 `RGI2000-v7.0-G-global` 셰이프를 받아 NAS
      `sources/earth/rgi7/` 에 두면 `glaciers.py` 의 점을 면으로 바꾼다(지금은 속성 표의 가운데·넓이로 넓이만 한 원) (wetherilli 289)
- [ ] **(사람)** GEOROC 암석 지화학 시료(wetherilli 293 으로 받은 일) — 조건은 **CC BY-SA 4.0**(GEOROC Compilation 미리 엮은 파일, 일에 적힌 CC BY 가
      아니다). 파일은 모두 GRO.data(`data.goettingen-research-online.de`, "Rock Types" doi:10.25625/2JETOA, 356 MB zip 90 개)에 있는데 **이 서버에서는
      TLS 연결이 끊긴다**(2026-10-05, 여러 번·CA 묶음으로도 SSLEOF). GEOROC 2.0 API 는 접근 열쇠가 든다. 다른 망에서 zip 을 받아 NAS
      `sources/earth/georoc/` 에 두면 지열류 꼴의 점 sqlite 로 굽는다

- [ ] **(사람)** 충돌구의 자세한 표 — Kenkmann 2021(MAPS, 75 항목·연대·지름)은 **CC BY-NC 4.0**, Osinski 외 2022(Impact Earth)는 **CC BY-NC-ND 4.0** 이다.
      지금은 Wikidata(CC0, 지름 3 분의 1·연대 열 곳)뿐이다. 비상업 조건을 받아들이면 Kenkmann 표로 바꿔 충돌구도 그때의 지구에 옮길 수 있다 (wetherilli 283)

- [ ] **(사람)** 전 지구 변형률 GSRM v2.1(Kreemer 외 2014, `geodesy.unr.edu/GSRM/` — 0.1° 격자 87 MB·셀 평균 3.7 MB, 압축 `.Z`)은
      README 가 "인용해 달라" 고만 하고 **이용 조건을 적지 않는다**. 저자(UNR)에게 묻거나 조건이 적힌 판을 찾으면 지각 두께 꼴의 격자로 둔다 (wetherilli 273)


## 인증키 뒤에 남은 것

- [ ] 호출 제한 수치를 KIGAM 에 묻는다 — 사람이 게시판부터 본다

## 영어판 — 남은 것 (008)

`manage.py i18n_missing` 이 잡지 못하는 것이다.

- [ ] **사람이 훑어본다.** 초안은 Claude 가 적었다. 특히 레이어 제목
      (좋은물지도 14 종·해저지질도 10 종), 속성 이름(`PROP_EN`), 설정 화면의
      `Ink brown`·`Hanji`. 고칠 자리는 `viewer/i18n.py` 하나다
- [ ] 속성 이름은 레이어 61 개를 두세 곳씩 눌러 모은 46 개다. 다른 자리에서
      처음 보는 열이 나오면 한국어로 뜬다 — 보이면 `PROP_EN` 에 더한다

**옮기지 않기로 한 것** — 속성 값(지층명·암석명·도폭명·사람 이름), 판 이력,
타일 안의 글자, 레이어 설명(한국어 제목을 되풀이한 것이라 영어판에서 숨긴다),
상류 오류의 자세한 문구(영어판은 `Could not get it from the source` 한 줄).

## VWorld 로 더 할 것 — 값 대비 쓸모 차례 (004)

조사는 끝났고 **쏴 보고 확인한 것들**이다. 자세한 것은 devlog 004.

- [ ] (운영) VWorld GetCapabilities 를 2026-09-27 의 187 종과 다시 견준다 — 개발 기계에는 열쇠가 없어 보지 못했다 (wetherilli 275)

### 품이 좀 드는 것

- [ ] 단층 `legend` 1·2 의 뜻 — VWorld 가 밝히지 않았다. 알면 `VECTOR_STYLES` 와
      `vworld.FRIENDLY` 두 자리만 고친다 (020)

## 노는 자료 — 이미 가진 API 로 더 할 수 있는 것 (2026-09-30 조사)

열쇠·문이 이미 있는데 받지 않는 자료다. [실측] 은 2026-09-30 에 한 번 불러 본 것, [문서] 는 목록에 이름만 본 것이다.
**품은 코드를 읽고 다시 쟀다** — 선례 코드와 바뀌는 파일을 세었다. 같은 틀을 타는 것끼리 묶었고, 묶음 안에서는 첫 건이
틀을 만들고 뒤의 것은 싸다. 단위는 1–2시간·반나절·하루·이틀.

### 달 — Trek ImageServer

- [ ] 누른 자리의 값 — 남은 것(wetherilli 236). 뜻을 모르는 Diviner 짝 셋(`c3_c7`·`c4_c7`·`c6_c8`)과 NAC DEM(Site D)을 남겼다.
      SMFe 의 단위가 밝혀지면 `VALUES["smfe"]` 를 고친다.
      **남극 짝(`sp_feo_mlemelin_031417`·`sp_ice_depth_*`)은 2026-09-30·10-02 둘 다 답이 없다** — 살아나면 `EXTRA_ITEMS` 에 북극 셋처럼.
      KGRS 의 단위가 밝혀지면 `VALUES` 의 이름·단위를 고친다. 점묶음 열(새 JSONField, 이주)은 아직. Kaguya 는 JAXA 조건(043)
- [ ] 고운 지형 — 남은 것(wetherilli 150·240). 아폴로 15 PanCam 셋은 256 ppd 와 평균 ±15 m·흩어짐 23–52 m 라
      자리가 어긋난 판으로 보여 뺐다. 메트릭 카메라 1024 ppd(`Apollo17_…`·`ApolloZone_…`, 30 m)는 256 ppd 보다 120 m 남짓 낮다 —
      기준면이 다른 까닭을 알면 맞춰 넣는다. 그 밖에 뺀 것 — 아르테미스 C(+91 m)·G(−10 m)는 턱이 일정해 기준면만 다른 판으로 보인다(까닭을 알면 배율·턱을 넣는다). B·북위 89° NAC·IM-1 은
      흩어짐 51–65 m. 피카르·말굽·`20191118_demmos` 는 수 km 다르다. 남극 85° 10·20 m(`ldem_85s_*`)는 한 점씩은 같은데 `exportImage` 로는
      흩어짐 1.3 km — 극 판(`_SP`)으로 받는 길을 본다. 후보 D(`LRO_NAC_DEM_4_57mpp_SiteD`)는 기준면을 모른다
- [ ] 화성 고운 지형 — 남은 것(wetherilli 274). 빅토리아 분화구 1 m(`DEM_1m_VictoriaCrater`)는 200 m 판과 바깥 테에서 −19 m·흩어짐 7 m 로
      턱이 일정하다 — 기준면이 다른 까닭을 알면 턱을 넣는다. 수성은 665 m 판뿐이라 고운 판이 없다

### 한국 — 시료 지점 칸·KIGAM 자료

- [ ] **KIGAM `/openapi/data` 를 지도에** — 모은 자료(`fetch_kigam_data`, wetherilli 169) 가운데 무엇을 올릴지는 이슈 #153 —
      지어 본 레이어(모음마다 점·면, 행정구역 가운데 표본)는 `feature/kigam-data-layers` 가지에. CC BY-NC, DOI 로 출처,
      밖에 열 때 `LAB_ONLY` 를 정한다
  - 표본(시료·분석) 점 레이어 — 연대·지질단위·채취지·보관처. 이틀
  - 누른 자리를 덮는 도폭의 저자·발간일·DOI — 같은 모으기라 반나절 더. `/openapi/file` 은 확인 못 했다
  - ("더 나중에" 의 데이터셋 검색 API 가 이 묶음이다)

### 더 큰 것

- [ ] (사람) 그린란드 50만 지질도 원본 면 [실측] 102 859 면 — 브라우저로 못 보낸다. moonmap·marsmap 틀로 sqlite 에 굽는다.
      이틀–사흘. GEUS WMS 와 받아온 길이 달라 섞을지 사람이 정한다
- [ ] **(사람) KIGAM GeoServer 에만 있는 레이어 338 개** [실측] — 5만 지질도의 층리·엽리·절리·선구조·화석·시료·광산
      (`Geology_map:l_50k_geology_*_latest`), 노두(`outcrop_korea`), 응력도, 방사능, Li·U 지화학, **5만 원도 스캔 50 장**
      (`Geology_origin_raster_50k:*_rectified`), 탄전 지질도 126, 드론 음영기복도. `/openapi/wms` 는 `geoOpen` 에 묶여
      `LayerNotDefined` 다. KIGAM 에 열어 달라 묻거나 속성처럼 예외로 둘지 사람이 정한다. 예외면 `kigam._endpoint` 를 레이어 단위로
      바꿔 이틀 넘게, 열어 주면 씨앗·영어만 하루. 값은 가장 크다
      구조 요소는 WFS 로 받아 우리가 그린다([docs/KIGAM_5만_구조요소.md](docs/KIGAM_5만_구조요소.md)) — 이 항목에 남는 것은 그림 레이어
      (원도 스캔·탄전 지질도·음영기복도)다
- [ ] (사람) jikhanjung P01 §8 — 5만 층리·엽리·절리(jikhanjung 004·005)의 레이어군 이름, 밖에 열 때 KIGAM 에 알릴지, NAS 사본

개발 머신에서 그린란드 포털(`services5.arcgis.com`)을 부르면 인증서가 막힌다(사내망이 끼워 넣는 인증서) —
`REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt` 를 주면 돈다. 운영과는 상관없다.
phyloserver 는 이 저장소만으로 더 할 것이 없다 — 도폭(`MapSheet`) JSON API 를 그쪽에 먼저.

## 캐시·미리 받기 (007·010)

2026-09-30 에 타일이 어디서 어떻게 캐시되는지 훑었다. 캐시를 더 적극적으로 쓰기로 했다(사람). 차례는 위에서 아래로.

- [ ] (사람) **PGC 음영·Trek 영상을 서버에 담아도 되는지** — 조건을 읽었지만 분명하지 않다(wetherilli 200, 이슈 #153). PGC 는 ArcticDEM 자료가 CC BY 4.0(AWS 공개 자료 목록)이지만 음영을 그려 주는 서비스(Esri 의 `di-pgc.img.arcgis.com`)에
      조건이 없다. Trek 은 안내에 조건이 없고 배경에 JAXA(Kaguya)·ESA(HRSC)·ASU(LROC) 자료가 섞였다. PGC 에 묻거나 NASA 단독 배경만 고른다.
      EOX(비상업)·Esri·VWorld 는 그대로 곧장
- [ ] **무엇을 미리 받을지 정한다.** 남한 전체 줌 12 까지는 싸다(5만 지질도
      7 천 장, 0.4 GB, 호출 450 번 남짓). 줌 13~14 는 10 만 장·5 GB 라 디스크
      상의(맨 위)와 함께 본다. 줌 15 위는 전국으로는 받지 않고 현장 권역만

## 더 나중에

- [ ] (사람) 국토지반정보 시추공을 한국 레이어로 올릴지 — 공공데이터포털 지층 파일이 엑셀 행 한계에서 잘려 있다.
      검토는 [docs/국토지반정보_시추공.md](docs/국토지반정보_시추공.md) §6

- [ ] 유럽 광물·지구물리 — BGS GeoIndex(영국)는 섰다(wetherilli 258). EGDI 의 광물 목록 MIN4EU 는 공개 WMS 를 찾지 못했다(뷰어가 안쪽 경로로만
      부른다)이고 조건이 **CC BY-NC-ND 4.0** 이다. ProMine·EGDI 지구물리도 WMS 주소를 못 찾았다. BGS 의 지화학(G-BASE)·지하수는 같은 서버에 있다
- [ ] 유럽 — EGDI 1:100만의 시대 판 속성이
      되살아나면(2026-10-04 에도 DB 오류, 지금은 암상 판에 묻는다 — wetherilli 177) 그쪽으로. BGS 1:62만 5천이 WMS 로 열리면 영국 탭의 넓은 줌을 그것으로. 독일의 줌 9 전은 EGDI·IGME5000(1:500만)이다 —
      그 사이 축척의 BGR 판(GÜK 2000?)이 있는지. **(사람)** BGR 판(GÜK·GK·IGME5000)을 정적 판에 실을지 — BGR 약관(AGB 3조)은 공중에 내놓을
      권리를 넘기지 않는다고 적고, 연방 지리정보 무료 이용 규정(GeoNutzV)이 이 WMS 에 걸리는지는 서비스에 적혀 있지 않다. BGR 에 묻고 나서 (wetherilli 217). 밖에 열기 전에 LNEG 의 조건(적힌 것이 없다)과 ISPRA 의 "열람 자유" 를 사람이 읽는다(211).
      폴란드 1:5만은 디지털로 올린 도폭만 있다(바르샤바·크라쿠프는 비었다, wetherilli 239)
- [ ] **(사람)** 체코 ČGS — 1:50만 영어판(`geologicka_mapa500_CR_en`)이 ICS 영어라 붙이기 좋다. 그런데 데이터셋 메타데이터는 "Copyright (všechna práva
      vyhrazena)", 저작권 페이지(cgs.gov.cz/copyright)는 CC BY 4.0 이라 말이 엇갈린다 — 사람이 읽고 정한다. 1:5만은 나라 줌 한 장에 22 초다(wetherilli 237)
- [ ] **(사람)** 덴마크 GEUS — 지표 퇴적층도 1:20만·1:2.5만. GEUS 조건(terms_20140620.pdf)이 "자기 용도만, 공개는 서면 동의" 이고 익명 타일 요청은 403 이다.
      도로청이 다시 내는 ArcGIS(`kort.vd.dk`)는 기술로는 쉽다 — 조건을 사람이 읽은 뒤에(wetherilli 237)
- [ ] (사람) 왈로니아 SPW 서비스의 조건 PDF(LicServicesSPW.pdf)와 오스트리아 1:100만 서비스 자체의 메타데이터는 읽지 않았다 — 자료는 CC BY 4.0 으로
      적혀 있다(wetherilli 237)
- [ ] (사람) 서호주 GSWA 지질도 — SLIP 공개 서비스(`services.slip.wa.gov.au/public/…/Geology_and_Soils_Map/MapServer`, 1:250만·1:50만·1:10만
      해석 기반암)는 열려 있지만 저작권 칸이 "SLIP Transaction — Personal Use Licence" 다. 같은 자료가 다른 곳에서 CC BY 4.0 으로 열렸는지 읽고 정한다 (wetherilli 225)
- [ ] 호주의 남은 것 — 뉴사우스웨일스(GSNSW GeoServer 에는 시추공·광산·광업권뿐, 이음매 없는 지질도의 주소를 못 찾았다)·태즈메이니아
      (MRT 서비스에 지질도가 없다, 도폭 색인뿐)·노던테리토리(NTGS GeoServer 에 시추공·광산뿐)는 지질도 서비스를 찾지 못했다. GA 의 다른 서비스
      가운데 확인 자원(`AustraliasIdentifiedMineralResources`, 광종 스물아홉 레이어)·지하수가 남았다 — 목록이 403 이라 ecat 에서 이름을 찾는다(wetherilli 241)
- [ ] **OneGeology 포털이 GSJ 아래에서 다시 열리면**(2026 년 중) 각국 WMS 를 한 목록에서 고른다. 중국 GeoCloud WMS 주소,
      VSEGEI(403)는 막혀 있다 ([docs/새_상류_후보.md](docs/새_상류_후보.md) §2·§3)

- [ ] 데이터셋 검색 API(`/openapi/data`) 붙이기 — 시료 자료를 지도에서 바로 찾기.
      이번 판은 WMS 만 쓴다
- [ ] (사람) 한반도 지질도의 출처·판·이용 조건을 **김선호 님께** 묻는다 — 밖에 열기 전에.
      단서: NAS `KimSunho/3차원에 섞을 것.cdr` 이 같은 지도의 CorelDRAW 벡터다(2023-05-31,
      `kopri`). 어느 출판 지도를 따라 그렸는지를 묻는다. 스캔이 아니면 레이어 이름의 "(스캔)" 을 고친다 (026)
- [ ] (사람) QGIS 프로젝트의 원본(GeoTIFF·벡터)을 받을 수 있는지 김선호 님께 묻는다 — 음영판의 좌표는
      해안선에 대 고쳐 쓰고 있다(027). 원본이 오면 고친 값을 버리고 그것을 믿는다. 제주가 빠진 것도 함께
- [ ] (phyloserver 저장소) dikesync DRF 가 쓰기(POST·DELETE)까지 권한 없이 열려 있다 — 그쪽에서 막는다
- [ ] (사람) 김선호 님께 민판의 월드파일 기준점과 제주가 든 판이 있는지 묻는다 (028)
- [ ] (사람) 민판의 색↔지층 표 — **CorelDRAW 원본에는 표가 없다**(wetherilli 245). 면 1 만 3 천 개에 채움색 90 가지뿐이고 범례·글·면 이름이
      없다(레이어 이름만 — Stratigraphy·Intrusion·지질경계선·단층선 …). 색의 이름(지층)은 원본을 그린 이가 따른 출판 지도의 범례에 있다 —
      김선호 님께 어느 지도인지 묻는 위 줄과 같은 답이다. 범례를 받으면 색 90 가지(`map3d.svg` 에서 뜬다)에 이름을 붙여 누른 자리의 픽셀 색으로 읽는다 (028)
- [ ] 도폭 경계를 phyloserver `MapSheet` 로 — JSON API 가 생기면 (지금은 KIGAM 도곽으로 충분)

## 하지 않기로 한 것

적어 두지 않으면 나중에 또 꺼내게 된다.

- **공간 연산 (GDAL·shapely·geopandas)** — 이 뷰어는 겹쳐 보고 클릭해 읽을 뿐이다.
  넣는 순간 web 이미지가 200 MB 대를 벗어난다. 필요해지면 그때 devlog 를 쓰고 더한다
- **DiaRUGA·ForGIA 와 DB 를 나누기** — 저장소도 배포도 따로다. 시추 지점을
  지도에 올리고 싶어지면 `Locality.lat/lon` 을 내보내 `PointSet` 으로 받는다
- **제품이 `/mgeo/geoserver` 를 타기** — 문서에 없는 주소다. 타일·범례는
  인증키로 `/openapi/wms` 를 탄다. **속성만은 예외로 탄다** — `/openapi/wms`
  가 막아 두었기 때문이다 (CLAUDE.md "두 개의 상류 주소", devlog 006)
- **네이버·카카오 지도를 배경으로 쓰기** — 둘 다 자기 렌더러를 들고 오는
  JS SDK 라, 쓰려면 OpenLayers 를 버리고 레이어 쌓기·투명도·속성 읽기
  ·점묶음을 그쪽 API 로 다시 짜야 한다. 배경지도 하나에 뷰어의 심장을 바꿀
  일이 아니다 (003)
- **OpenStreetMap 을 서버로 중계하기** — 화면은 살지만 그것이야말로 OSM 이
  막는 행동이다. 이번엔 서버 IP 가 막힌다 (003)
