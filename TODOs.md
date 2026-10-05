# 할 일

지금 무엇을 할 수 있는지 고르는 자리다. 왜 그렇게 했는지는 `devlog/`, 지금 어디까지 왔는지는 `HANDOFF.md`.

2026-10-05 에 다시 묶었다(wetherilli 319) — 오늘 병합된 PR(#214–#304)과 열린 PR(#305–#308)에 대 끝난 줄을 걷어 내고,
**결정 없이 할 수 있는 것**(값이 큰 차례)·**운영에서 할 것**·**(사람) 정할 것**·**지켜볼 것과 막힌 것**으로 나눴다.
열린 PR 이 끝낼 줄은 "(PR #n 이 한다)" 로 적었다 — 병합되면 지운다.

## 결정 없이 할 수 있는 것 — 값이 큰 차례

- [ ] **앨버타 금속·산업 광물 산지**(wetherilli 288) — ArcGIS Online 피처 서비스(`Metallic_Mineral_Occurrences`·`Industrial_Mineral_Occurrences`)뿐이라
      그림 길이 없다. 파나마(`stri`)·카리브(`usgscarib`)처럼 한 덩이로 받아 캐시에 담고 화면이 그린다. 캐나다 탭, OGL–Alberta
- [ ] **퀘벡 광물 산지(gîte)**(wetherilli 288) — SIGÉOM WMS 에는 가동 광산·사업뿐이다. SIGÉOM 의 다른 서비스(ArcGIS·WFS)에서 광물 산지를 찾는다
- [ ] **호주 GA 의 확인 자원**(`AustraliasIdentifiedMineralResources`, 광종 스물아홉 레이어)·지하수(wetherilli 241) — 목록이 403 이라 ecat 에서
      이름을 찾는다. 남은 주는 wetherilli 318 이 했다 — 태즈메이니아 지질(theLIST)·뉴사우스웨일스 광물 산지·광산이 섰다.
      뉴사우스웨일스 이음매 없는 지질도는 503, 노던테리토리는 지질도 서비스를 찾지 못했다.
      **(사람)** 태즈메이니아 theLIST 약관이 레이어 저작권 글로 미루는데 그 글이 비었다 — 정적 판에 싣기 전에 MRT 에 묻는다(#153)
- [ ] 남호주 지구물리의 값 누르기(wetherilli 329) — 영상 WMS(자력·중력·방사능 여섯)는 섰지만 누르면 RGB 뿐이다. 값을 보이려면 원본 격자를 받아 굽는다 — 방사능 합본(43 MB)이 가장 싸고, 중력은 4.7 GB(ADMAP 꼴)
- [ ] **대만 지질운 열린자료의 빈 칸 셋**(wetherilli 305) — 상류가 0.08° 네모로 나눠도 120 초를 넘겨 끊는 자리(파일의 `holes`): 토석류 유동
      121.91–121.98°E·24.94–25.03°N, 낙석 120.73–120.81°E·22.50–22.59°N, 120.97–121.05°E·23.91–24.00°N. 판마다
      `fetch_taiwan_open --api DebrisFlowTrack,RockFall` 로 다시 받아 본다. "암석 강도"(A–H)·"암체 강도 등급"(I–VII)의 뜻을 찾으면 범례에
- [ ] **독일 줌 9 전의 축척** — 지금은 EGDI·IGME5000(1:500만)이다. 그 사이 축척의 BGR 판(GÜK 2000?)이 있는지 찾는다
- [ ] 달 — 누른 자리의 값, 남은 것(wetherilli 236). 뜻을 모르는 Diviner 짝 셋(`c3_c7`·`c4_c7`·`c6_c8`)과 NAC DEM(Site D)을 남겼다.
      SMFe 의 단위가 밝혀지면 `VALUES["smfe"]` 를 고친다. KGRS 의 단위가 밝혀지면 `VALUES` 의 이름·단위를 고친다. 점묶음 열(새 JSONField, 이주)은 아직
- [ ] 달 고운 지형 — 남은 것(wetherilli 150·240). 아폴로 15 PanCam 셋은 256 ppd 와 평균 ±15 m·흩어짐 23–52 m 라 자리가 어긋난 판으로 보여 뺐다.
      메트릭 카메라 1024 ppd(`Apollo17_…`·`ApolloZone_…`, 30 m)는 256 ppd 보다 120 m 남짓 낮다 — 기준면이 다른 까닭을 알면 맞춰 넣는다. 그 밖에 뺀 것 —
      아르테미스 C(+91 m)·G(−10 m)는 턱이 일정해 기준면만 다른 판으로 보인다(까닭을 알면 배율·턱을 넣는다). B·북위 89° NAC·IM-1 은 흩어짐 51–65 m.
      피카르·말굽·`20191118_demmos` 는 수 km 다르다. 남극 85° 10·20 m(`ldem_85s_*`)는 한 점씩은 같은데 `exportImage` 로는 흩어짐 1.3 km — 극 판(`_SP`)으로
      받는 길을 본다. 후보 D(`LRO_NAC_DEM_4_57mpp_SiteD`)는 기준면을 모른다
- [ ] 화성 고운 지형 — 남은 것(wetherilli 274). 빅토리아 분화구 1 m(`DEM_1m_VictoriaCrater`)는 200 m 판과 바깥 테에서 −19 m·흩어짐 7 m 로
      턱이 일정하다 — 기준면이 다른 까닭을 알면 턱을 넣는다. 수성은 665 m 판뿐이라 고운 판이 없다
- [ ] 영어판 — 속성 이름은 처음 보는 열이 나오면 한국어로 뜬다. 보이면 `PROP_EN` 에 더한다(008)
- [ ] 브리티시컬럼비아 넓은 줌(wetherilli 231) — (PR #308 이 한다)
- [ ] GSJ 1:200만 지질도·중력을 누르면 이름이(wetherilli 255) — (PR #306 이 한다)
- [ ] 넓게 볼 때만 느린 레이어 — EMODnet folk_7·대만 자세 기호와 그 무리(wetherilli 298·308) — (PR #307 이 한다)

## 운영에서 할 것 — 판 세션이 배포한 자리에서

- [ ] `manage.py fetch_sgb_units` 를 한 번 — 브라질 범례에 단위 이름·시대가 붙는다(없으면 기호만). 1:100만은 WFS 열 번 남짓·1 초 간격 (wetherilli 191)
- [ ] 배포 뒤 `manage.py fetch_grportal` 을 한 번 — 시료 2 만 점을 처음 켜는 사람이 17 초를 기다리지 않게 (019). NPI 점·지명·도폭 경계도 같은 명령이
      받는다 (029). 그린란드·드로닝모드랜드 지명도 — 안 받아 두면 그린란드 첫 지명 찾기가 24 초 걸린다 (wetherilli 096)
- [ ] `manage.py fetch_kopri` 를 가끔 — 새로 올라온 KPDC 자료만 받는다(목록 여덟 장 + 새 상세). 처음 모은 것은 2026-09-29 밤 `/srv/GSM/db/kopri/` (053)
- [ ] VWorld GetCapabilities 를 2026-09-27 의 187 종과 다시 견준다 — 개발 기계에는 열쇠가 없어 보지 못했다 (wetherilli 275)

## (사람) 정할 것

### 조건을 읽거나 묻는다 — 밖에 열기·정적 판에 싣기 전에

- [ ] **밖에서 쓸 KIGAM 키** — 휴대폰에서 안 뜬 까닭은 키였다: 키를 신청할 때 연구소 IP 를 적어 그 IP 밖에서는 KIGAM 이 거절한다
      (사용자 확인, 2026-10-04 — wetherilli 179 의 남은 갈래 (2)). 밖에서 쓰려면 IP 를 묶지 않은(또는 쓸 곳을 넓힌) 키를 따로 받는다.
      정적 판은 각자 키라 다른 사람은 자기 키로 본다. 키 창의 "주지 않았다" 안내가 이 경우를 말한다
- [ ] **GSM 을 밖에 열기 전에 geo3al(중국)을 내린다** — "내부 용도만, 가공물 포함 재배포 금지" (025). 스위치는 `GSM_PUBLIC=1`(또는 `<DB 옆>/public`) (029)
- [ ] **CGMW 지도 둘** — 남미 1:500만(SGC 가 내는 것, wetherilli 188)·아프리카 1:1000만(CGMW–BRGM, wetherilli 207). CGMW 는 지도를 판다.
      읽고 되면 정적 판에 싣는다(둘 다 CORS 가 열려 있어 `static-kinds.js` 한 갈래)
- [ ] 조건 문구가 없는 상류 — 우루과이 DINAMIGE(196)·파라과이 VMME(256)·니카라과 INETER·도미니카공화국 SGN(242)·몽골 MonGeoCat(221)·
      인도 GSI(226, Bhukosh 가 막혀 못 읽었다)·사우디 SGS(227)·동남아 넷(228 — ESDM·JMG·MGB·DMR)·아시아 광물 다섯(280)·
      미국 주 셋(291 — NBMG·WA DNR·DOGAMI)·LNEG(211)·캘리포니아 CGS(231). 문서 `docs/상류_조건표.md` 의 **(사람) 읽을 것** 줄이 모두 여기다
- [ ] 남아공 CGS·나미비아 GSN 을 서버 캐시에 담아도 되는지 — 둘 다 자료를 파는 곳이라 지금은 담지 않고 그때그때 받는다(`views.NO_STORE`).
      남아공의 넓은 그림은 한 장에 11 초까지 걸린다
- [ ] **정적 판에 실을지** — 캐나다 NRCan 1:500만·온타리오 OGS(wetherilli 204, OGL·CORS 되비춤, #153)·아이슬란드 NÍ(216, CC BY 4.0·CORS `*`)·
      뉴질랜드 GNS(218, 속성 CORS 가 막혀 타일만 된다)·BGR 판(GÜK·GK·IGME5000 — AGB 3조는 공중에 내놓을 권리를 넘기지 않는다고 적고, GeoNutzV 가
      이 WMS 에 걸리는지는 서비스에 없다, wetherilli 217)
- [ ] 비상업·이용 조건이 걸린 배경 — EOX Sentinel-2(CC BY-NC-SA, 3857 이라 북위 85° 위가 빈다, 017)·Esri Antarctic Imagery(Esri MLA, 040)·
      PGC 음영·Trek 영상을 서버에 담아도 되는지(wetherilli 200, #153 — PGC 는 ArcticDEM 이 CC BY 4.0 이지만 음영 서비스에 조건이 없고, Trek 은 배경에
      JAXA·ESA·ASU 자료가 섞였다)
- [ ] 달 자료의 조건 — Kaguya(JAXA, 043)·창어 2 호 CE-2 CCD 정사 모자이크(CNSA/CLEP, 052)
- [ ] **KPDC 공개 정책을 보고 `LAB_ONLY` 에서 `kopri` 를 뺄지** (053) — 본문은 2026-09-30 에 읽었다(영문, 제10–11조). "과학적 목적으로 자유롭게"
      공개하되 자료를 쓰려는 이는 범위·목적을 적어 신청하고(14 일 안에 심사), 알린 범위 안에서만 쓰며 출처를 밝히고 결과를 알린다. 우리가 보이는 것은
      목록(제목·위치·키워드)과 지도 서버의 선이다 — 밖에 열기 전에 kpdc@kopri.re.kr 에 묻는 것이 안전하다
- [ ] 아이슬란드 ÍSOR 1:10만·페로 Jarðfeingi·자메이카 MGD 웹맵(조건 없음)·트리니다드 Latinum(교육용 한정) — 조건을 묻고 나서 붙인다
- [ ] **콩고민주공화국·르완다·부룬디 — 벨기에 RMCA GeoServer**(`edit.africamuseum.be/geoserver`) — DRC 1:200만(`COD_RMCA_2M_*`)·르완다·부룬디
      1:25만(`RWABDI_RMCA_250K_*`)·카탕가 1:20만(`geco_geology`)·PROMINES 2015 DRC 지질도(`METAFRO_RDC_Mining`)가 3857·CORS `*` 로 열려 있다
      (wetherilli 246). 조건이 "© RMCA, Other restrictions" 이고 PROMINES 판은 "공개 자료가 아니다" 라는 글도 있다 — maps@africamuseum.be 에 묻는다.
      이집트 웨스턴미시간대 Nubian 사업 서버(EGSMA 1:200만)도 조건 미상이라 함께 둔다
- [ ] 캐나다 주 판 — 뉴브런즈윅(`gis-erd-der.gnb.ca/…/OpenData/NBGS_Bedrock_Geology` WMS·WFS)·뉴펀들랜드래브라도(`dnrmaps.gov.nl.ca/…/GeoAtlas/Bedrock_Geology_All` WMS)는
      조건을 읽지 못했다(뉴브런즈윅 조건 쪽은 우리에게 403, WMS 의 조건 칸은 둘 다 비었다). 노스웨스트준주는 ArcGIS Online 피처 서비스
      (`MapD1860A_NWTGeology`)뿐이라 우리가 그려야 한다 — 조건을 읽으면 앨버타 광물 산지와 같은 길로
- [ ] 체코 ČGS 1:50만 영어판 — 메타데이터는 "Copyright (všechna práva vyhrazena)", 저작권 페이지는 CC BY 4.0 이라 엇갈린다. 1:5만은 나라 줌 한 장에 22 초(wetherilli 237)
- [ ] 덴마크 GEUS 지표 퇴적층도 1:20만·1:2.5만 — GEUS 조건이 "자기 용도만, 공개는 서면 동의" 이고 익명 타일은 403. 도로청이 다시 내는 ArcGIS(`kort.vd.dk`)는
      기술로는 쉽다(wetherilli 237)
- [ ] 왈로니아 SPW 서비스의 조건 PDF(LicServicesSPW.pdf)·오스트리아 1:100만 서비스의 메타데이터는 읽지 않았다 — 자료는 CC BY 4.0 으로 적혀 있다(wetherilli 237)
- [ ] 서호주 GSWA 지질도 — SLIP 공개 서비스(1:250만·1:50만·1:10만 해석 기반암)는 열려 있지만 저작권 칸이 "SLIP Transaction — Personal Use Licence" 다.
      같은 자료가 CC BY 4.0 으로 열린 곳이 있는지 읽는다 (wetherilli 225)
- [ ] BAS 의 ArcGIS Online 피처 서비스 — 암석 표본 `geology_collection`(14 만 3 천)·해양·호수·이탄 코어·빙하 코어·SCAR 지명 사전(남극 전체의 지명 찾기).
      열려 있고 CORS 도 되지만 이용 조건 글이 없다 (wetherilli 261)
- [ ] 충돌구의 자세한 표 — Kenkmann 2021(CC BY-NC 4.0)·Osinski 외 2022(CC BY-NC-ND 4.0). 지금은 Wikidata(CC0)뿐이다. 비상업을 받아들이면 Kenkmann 표로
      바꿔 그때의 지구에 옮길 수 있다 (wetherilli 283)
- [ ] 전 지구 변형률 GSRM v2.1(Kreemer 외 2014) — README 가 "인용해 달라" 고만 하고 이용 조건을 적지 않는다. 저자(UNR)에게 묻는다 (wetherilli 273)
- [ ] 뉴질랜드 광물 산지 GERM(`gns:GERM_ERML_VIEW`) — 가까이 봐도 빈 그림이다(스타일이 없거나 축척 제한). GNS 에 묻는다 (wetherilli 269)
- [ ] 탄자니아 GMIS 1:150만 — 서버가 중간 인증서를 빼먹어 TLS 검증이 실패한다(연구소 망은 "UNTRUSTED CERT ALERT" 로 다시 서명). 그 호스트만 검증을 끌지,
      서버가 고칠 때까지 둘지 (wetherilli 209, #153)

### 자료를 받아 오거나 묻는다

- [ ] 프랑스령 기아나 BRGM 1:50만 셰이프(`Guyane.zip`, 6.7 MB)를 InfoTerre DROM 양식으로 받아 NAS 에 — 이름·전자우편을 적는다. 받으면 파일을 한 덩이로
      내는 문(얀마옌 꼴)으로 기아나 탭을 세운다. 반나절 (wetherilli 256)
- [ ] RGI 7.0 빙하 **윤곽** — NSIDC-0770 은 NASA Earthdata 로그인 뒤에만 받힌다. 받아 NAS `sources/earth/rgi7/` 에 두면 `glaciers.py` 의 점을 면으로 (wetherilli 289)
- [ ] GEOROC 암석 지화학 시료(wetherilli 293) — 조건은 CC BY-SA 4.0. 파일(GRO.data, 356 MB zip 90 개)이 이 서버에서는 TLS 연결이 끊긴다. 다른 망에서 받아
      NAS `sources/earth/georoc/` 에 두면 지열류 꼴의 점 sqlite 로 굽는다
- [ ] SPA 지질도 원본(Zenodo 10.5281/zenodo.19728952)을 NAS `sources/moon/` 에 둔다 — 운영 `db/moon/` 에는 두었다 (wetherilli 081)
- [ ] 중국지질조사국 1:250만 수치지질도(`10.23650/data.H.2017.NGA121474`) — 받을 수 있는지·조건(dcc 가 국외에서 응답하지 않는다). 오면 geo3al 을 밀어낸다 (025).
      GeoCloud 는 국외 차단·신청제 — [docs/중국_GeoCloud.md](docs/중국_GeoCloud.md). P04 §5(어디까지 자르나·어느 탭에 두나)도 함께
- [ ] 그린란드 50만 지질도 원본(`grl_g500_lithostr_units`)을 WMS 로 열어 주는지 GEUS 에 묻는다 — 같은 메일에 정부 포털 시료가 2 만 점에서 잘린 것·
      시료 좌표가 1 km 가량 어긋나는 것 (019). 원본 면 102 859 개를 우리가 굽는 길(moonmap 틀, 이틀–사흘)은 GEUS WMS 와 섞을지 정한 뒤에
- [ ] 극지연구소에 묻는다 — 아라온 해양 자료 백여 건이 같은 기본 네모만 적은 것·Midtre Lovénbreen 경도 부호(075 §5, 076)·암석 시료 상세가 로그인 뒤에만
      보이는 것(053)
- [ ] 김선호 님께 묻는다 — 한반도 지질도의 출처·판·이용 조건(026), QGIS 원본(GeoTIFF·벡터, 027), 민판의 월드파일 기준점·제주가 든 판(028),
      민판 색↔지층 범례(CorelDRAW 원본에 표가 없다, wetherilli 245). 범례를 받으면 색 90 가지에 이름을 붙여 누른 자리의 색으로 읽는다
- [ ] KIGAM 에 묻는다 — 호출 제한 수치(게시판부터)·**GeoServer 에만 있는 레이어 338 개**(5만 원도 스캔 50 장·탄전 지질도 126·드론 음영기복도, `/openapi/wms`
      는 `geoOpen` 에 묶여 `LayerNotDefined`). 열어 주면 씨앗·영어만 하루, 예외로 두면 `kigam._endpoint` 를 레이어 단위로 이틀 넘게. 값은 가장 크다.
      구조 요소는 WFS 로 받아 우리가 그린다([docs/KIGAM_5만_구조요소.md](docs/KIGAM_5만_구조요소.md))

### 고르거나 훑는다

- [ ] **KIGAM `/openapi/data` 를 지도에** — 모은 자료(`fetch_kigam_data`, wetherilli 169) 가운데 무엇을 올릴지는 이슈 #153. 지어 본 레이어는
      `feature/kigam-data-layers` 가지에. CC BY-NC, DOI 로 출처, 밖에 열 때 `LAB_ONLY` 를 정한다. 표본 점 레이어(이틀)·누른 자리를 덮는 도폭의 저자·발간일·DOI(반나절)
- [ ] 무엇을 미리 받을지 — 남한 전체 줌 12 까지는 싸다(5만 지질도 7 천 장, 0.4 GB, 호출 450 번 남짓). 줌 13–14 는 10 만 장·5 GB, 줌 15 위는 현장 권역만 (007·010)
- [ ] 미국 탭의 하와이 — 3978 이라 50° 남짓 돌아 보인다(wetherilli 238). 섬 탭을 따로 두거나 미국 탭의 투영을 고른다
- [ ] 아프리카 지하수 지도책의 수리지질(`<ISO3>_BGS_5M_Hydrogeology`) — 같은 서버·같은 조건(CC BY-SA). 지질 탭에 둘지
- [ ] jikhanjung P01 §8 — 5만 층리·엽리·절리(jikhanjung 004·005)의 레이어군 이름, 밖에 열 때 KIGAM 에 알릴지, NAS 사본
- [ ] 달 — P05 §8(시대 한국어 표기 `trek.AGES_KO`, 다누리 KGRS 자료, 원소·광물 레이어군), Trek 판 한글 제목 초안(`data/moon_trek_layers.json` 의 `ko`, 060)
- [ ] 영어판을 사람이 훑는다 — 레이어 제목(좋은물지도 14 종·해저지질도 10 종), 속성 이름(`PROP_EN`), 설정 화면의 `Ink brown`·`Hanji` (008)
- [ ] VWorld 단층 `legend` 1·2 의 뜻 — VWorld 가 밝히지 않았다. 알면 `VECTOR_STYLES`·`vworld.FRIENDLY` 두 자리만 고친다 (020)
- [ ] 국토지반정보 시추공을 한국 레이어로 올릴지 — 공공데이터포털 지층 파일이 엑셀 행 한계에서 잘려 있다. [docs/국토지반정보_시추공.md](docs/국토지반정보_시추공.md) §6
- [ ] DiaRUGA·ForGIA 의 남극·남빙양 지점과 잇기 — DB 는 나누지 않고 `Locality.lat/lon` 을 내보내 점묶음으로 받는다. 수심 읽기(070)가 섰다 (047)
- [ ] KPDC 의 다른 묶음 — PAMC 미생물 균주(2 만 2 천)·KVH 식물 표본(3 천 8 백). 지질과 거리가 있어 미뤘다 (053)

## 지켜볼 것·막힌 것

되살아나거나 바뀌면 그때 한다.

- GSJ 는 호출 제한 수치를 밝히지 않는다 — `upstream_stats` 의 `gsj` 를 지켜본다
- 캐나다 지구물리(자력·중력 격자) — GSC 의 CAGDB WMS(`wms.agg.nrcan.gc.ca/wms2/wms2.aspx`)·자료 꾸러미(`gdr.agg.nrcan.gc.ca`)가 2026-10-05 에 두 번
  60 초 안에 답하지 않았다(`agg.nrcan.gc.ca` 전체). 살아나면 캐나다 탭에(wetherilli 250·319). 유콘은 50 m 잔류 자력을 타일로 따로 연다(OGL–Yukon)
- 몽골 `Atlas/AtlasPoints` 의 광상 레이어(6–9)는 우물 자료를 돌려준다 — 고쳐지면 금속·비금속·연료·전략 광상 (wetherilli 280)
- 누벨칼레도니 1:5만은 상류가 "재정비 중" — 새 판이 오면 범례에 1:5만(253 칸)을 더할지 본다 (wetherilli 260)
- EGDI 1:100만의 시대 판 속성이 되살아나면(DB 오류, 지금은 암상 판에 묻는다 — wetherilli 177) 그쪽으로. BGS 1:62만 5천이 WMS 로 열리면 영국 탭의 넓은 줌을 그것으로
- 달 남극 짝(`sp_feo_mlemelin_031417`·`sp_ice_depth_*`)은 2026-09-30·10-02 둘 다 답이 없다 — 살아나면 `EXTRA_ITEMS` 에 북극 셋처럼
- OneGeology 포털이 GSJ 아래에서 다시 열리면(2026 년 중) 각국 WMS 를 한 목록에서 고른다 ([docs/새_상류_후보.md](docs/새_상류_후보.md) §2·§3)
- 막힌 상류(2026-10-04·05 실측, [docs/다른_대륙_지질도.md](docs/다른_대륙_지질도.md)·[docs/아시아_오세아니아_지질도.md](docs/아시아_오세아니아_지질도.md))
  - 남미: 칠레 SERNAGEOMIN(무응답·DNS 없음), 볼리비아(8080 거부 — 열리면 GeoServer 1:100만 `geologico:geologico_1M`), 수리남(토큰), 가이아나(신청제),
    베네수엘라(서비스 없음). 남미 1:500만 둘(SGC·USGS)이 덮는다. 피지(공개 서비스 없음)
  - 북미: USGS GMNA(403)·ScienceBase(503)·NGMDB(지도 API 없음). 유타 UGS·애리조나 AZGS 는 이 서버에서 연결 시간 초과(나라 밖 차단으로 보인다, wetherilli 291).
    매니토바(502)·누나부트(서비스 없음)
  - 중앙아메리카: 과테말라·온두라스·벨리즈·쿠바(서비스 없음·DNS·시간 초과), 엘살바도르 SNET(522 — 다시 볼 것), 코스타리카(UCR 여백 붙은 스캔·DGM 빈 응답)
  - 아프리카: SIGAfrique(호스트 없음), USGS certmapper(403), OneGeology 포털(닫힘), 모로코·나이지리아(서비스 없음). 남아공 CGS 자신의 서버
    (`maps.geoscience.org.za`)는 시간 초과. 보츠와나·잠비아·짐바브웨·케냐·우간다·가나·에티오피아·말리·세네갈·마다가스카르는 지도 서비스를 찾지 못했다.
    광상 점(나미비아·부르키나파소·카메룬 서버에는 지질 단위·단층뿐, BGS 아프리카 폴더는 지하수뿐 — wetherilli 285)
  - 아시아: 인도 Bhukosh·러시아 VSEGEI·카자흐스탄·튀르키예 MTA·이란·이스라엘(나라 밖 차단), 파푸아뉴기니 MRA(등록제), 베트남·라오스·캄보디아·미얀마·
    오만(서비스 없음 — CCOP 200만으로), 카타르·쿠웨이트·이라크·파키스탄·네팔·스리랑카·방글라데시·아프가니스탄(wetherilli 249). 말레이시아 MyGEMS 의
    광물 서비스(목록이 허브로 넘어간다, wetherilli 280)
  - 유럽: EGDI 광물 목록 MIN4EU 는 공개 WMS 를 찾지 못했고 조건이 CC BY-NC-ND 4.0, ProMine·EGDI 지구물리도 WMS 주소를 못 찾았다. 폴란드 1:5만은
    디지털 도폭만(바르샤바·크라쿠프는 비었다, wetherilli 239)
  - 그린란드: 지도 화면의 광물 산지 v3(`mineral_occurrences_v3_external`)는 WMS 이름이 403 — 포털(grportal)의 광물 산지가 같은 뿌리다. 방사능은 국지 조사 몇 곳뿐
  - 호주: 뉴사우스웨일스 이음매 없는 지질도(503)·노던테리토리 지질도(서비스 없음) (wetherilli 318)
  - 남미 광물(wetherilli 265·277): 브라질 opendata 의 광업 권역(ANM)·항공 지구물리 조사 범위, SEGEMAR 자력 이상(면 47 개뿐). 페루 광업 권리는
    지질과 멀어 싣지 않는다(wetherilli 303)
  - 아시아 광물(wetherilli 280): 태국 지구물리 탐사 지점·사우디 지구물리 사업 범위는 범위뿐
- phyloserver — 도폭 경계를 `MapSheet` 로(JSON API 가 생기면, 지금은 KIGAM 도곽으로 충분). dikesync DRF 가 쓰기(POST·DELETE)까지 권한 없이 열려 있다 —
  그쪽 저장소에서 막는다
- 데이터셋 검색 API(`/openapi/data`) — 위 "KIGAM `/openapi/data` 를 지도에" 와 같은 묶음이다

개발 머신에서 그린란드 포털(`services5.arcgis.com`)을 부르면 인증서가 막힌다(사내망이 끼워 넣는 인증서) —
`REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt` 를 주면 돈다. 운영과는 상관없다.

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
- **넓은 줌의 자료를 숨기지 않으려 30 초씩 기다리기** — 한 칸이 10 초를 넘는 줌은 묻지 않고, 패널이 "줌 n 부터 그려진다" 를 적는다(wetherilli 313)
