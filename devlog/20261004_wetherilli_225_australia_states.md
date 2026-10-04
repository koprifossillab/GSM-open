# 호주 — 주 지질조사소 판 셋(퀸즐랜드·빅토리아·남호주)

2026-10-04 · `feature/australia-states` · wetherilli

판 세션이 맡겼다. 근거는 TODOs 의 "호주 GA 탭은 섰다(주 지질조사소 판·GA 의 다른 서비스는 다음)" 줄이다(wetherilli 212). 열려 있고 조건이
분명한 것만 고르고, 애매한 것은 (사람) 으로 남기라고 했다.

## 1. 쟀다 (2026-10-04, 요청 사이 2 초, 마흔 번 남짓)

| 주 | 주소 | 지질도 | 조건 | 고름 |
|---|---|---|---|---|
| 퀸즐랜드 GSQ | `spatial-gis.information.qld.gov.au/arcgis/rest/services/GeoscientificInformation/` | `GeologyState` 1:200만, `GeologyDetailed` 1:10만, `GeologyRegional` 분지별 1:50만·1:100만 | 서비스엔 "© State of Queensland" 뿐. data.qld.gov.au 의 이 WMS 항목이 CC BY 4.0 | ○ |
| 빅토리아 GSV | `opendata.maps.vic.gov.au/geoserver/wms` | 이음매 없는 지질도 1:25만·1:5만(GeoSciML 포트레이얼), 1:100만·1:400만 | Capabilities 는 none. discover.data.vic.gov.au "Geological polygons (1:250,000)" 가 CC BY 4.0 | ○ |
| 남호주 GSSA | `sarigdata.pir.sa.gov.au/geoserver/ows` | `gsmlp:GeologicUnitView`, 단층(`ShearDisplacementStructureView`) | AccessConstraints 가 CC BY 4.0 을 적는다 | ○ |
| 서호주 GSWA | `services.slip.wa.gov.au/public/…/Geology_and_Soils_Map/MapServer` | 해석 기반암 1:250만·1:50만·1:10만, 신생대 지질 | 저작권 칸 "SLIP Transaction — Personal Use Licence" | × (사람) |
| 뉴사우스웨일스 | `gs.geoscience.nsw.gov.au/geoserver` | 없음 — 시추공·광산·광업권뿐(AccessConstraints 는 CC BY 4.0) | | × |
| 태즈메이니아 MRT | `data.stategrowth.tas.gov.au/ags/rest/services/MRT/` | 없음 — 도폭 색인·시추공·산사태 | | × |
| 노던테리토리 NTGS | `geology.data.nt.gov.au/geoserver` | 없음 — 시추공·광산·광업권 | | × |

GA 의 다른 서비스는 서비스 목록(`/gis/rest/services`)이 403 이다. 이름을 짐작해 부른 둘도 403 — 이름을 알아야 부를 수 있어 이번에는 두었다.

- **퀸즐랜드 WMS 의 레이어 이름에 숫자 꼬리가 붙는다**(`State_Surface_Geology55055`, `Detailed_faults_and_shear_zones17471`). ArcGIS 가 판을 다시
  올리면 바뀔 수 있는 이름이라 WMS 를 버리고 REST `export`·`identify` 를 번호로 부른다(남아공 `cgs.py` 와 같다). 1:10만은 1:150만보다 가까울 때만
  그린다(300 km 네모는 빈 그림) — 줌 9 부터. 한 장 1–5 초
- **빅토리아**는 1:25만 주 전체 한 장이 12.6 초라 줌 8 부터, 1:5만은 덮는 곳이 일부라 줌 11 부터. 가까우면 2 초
- **남호주**는 1:250만보다 넓으면 빈 그림이고, 1:140만 남짓에서 한 장 13 초다 — 줌 9 부터
- 속성은 GeoServer 둘이 기하를 함께 보내(빅토리아 한 점 38 KB) `propertyName` 으로 열만 받는다. 퀸즐랜드 identify 는 열 이름이 사람이 읽는
  이름이다(`Rock Unit Name`, `Lithological Summary`)

## 2. 문 — 한 파일에 셋(`austates.py`)

주마다 서버도 꼴도 다르지만 하는 일은 작다. BGS 문이 GSNI·AGA·GSN 을 한 파일에 두듯 셋을 한 파일에 두고 상류 이름은 따로 했다(`gsq`·`gsv`·`gssa`)
— 딱지와 기관 이름이 제 주로 뜬다. 빅토리아·남호주는 같은 GeoSciML 포트레이얼(`GeologicUnitView`)이라 손질 하나(`gs_friendly`)가 둘을 다 읽는다
— 빅토리아는 열이 작은 글자, 남호주는 낙타 꼴이라 작은 글자로 맞춰 읽는다.

- **시대** — GeoSciML 은 ICS 주소(`…/ischart/LowerOrdovician`)를 준다. 꼬리를 낱말로 갈라 ICS 영어로 하고, 계(Series)의 Lower·Upper 는
  `i18n.age_ko` 가 아는 Early·Late 로 바꾼다. 퀸즐랜드는 대문자 영어(`DEVONIAN - CARBONIFEROUS`)라 첫 글자만 크게 해 옮긴다. 남호주는 숫자 연대
  (`numericOlderAge`)도 준다
- **범례** — 빅토리아는 SGB 처럼 보는 범위에 칠한 칸만 JSON 으로 온다(`hideEmptyRules`). 규칙 이름이 단위 이름이라("Bacchus Marsh Formation (Pxb)")
  이름표를 모아 둘 일도 없다. 남호주는 같은 물음에 빈 JSON 이 오고, 퀸즐랜드 REST 범례는 칸이 수천이다 — 둘은 범례를 아직 두지 않았다(TODOs)
- 레이어군은 주마다 하나다. 씨앗 파일이 상류마다 하나라 한 레이어군에 넣으면 차례가 섞인다

## 3. 버린 것

- 서호주 — 저작권 칸이 개인 이용 허락이다. 같은 자료가 data.wa.gov.au 에 CC BY 4.0 으로 있는지는 이 세션에서 읽지 않았다. (사람) 으로 남겼다
- 퀸즐랜드 분지별 1:50만·1:100만(`GeologyRegional`, 열두 분지) — 1:200만과 1:10만 사이를 메우지만 레이어가 분지마다 따로라 여럿이 된다
- 구조선(퀸즐랜드 단층·습곡, 남호주 단층) — 남호주 단층은 누른 자리에 걸리지 않았다. 다음에 단층만 따로 더한다
- 정적 판 — 조건은 열렸지만 `static-kinds.js` 에 이 꼴을 아직 두지 않았다

## 4. 확인

- `test_austates` — 셋의 손질(시대 옮기기·ICS 주소·숫자 연대), 퀸즐랜드 export·identify, GeoServer 의 `propertyName`, 빅토리아 범례(담아 둠·넓으면 422).
  전체 시험 통과
- 문으로 상류를 불러 봤다 — 브리즈번 둘레 "Bunya Phyllite · DCy · 데본기~석탄기", 멜버른 서쪽 "Newer Volcanic Group — basalt flows · 마이오세~홀로세",
  애들레이드 둘레 "Pleistocene calcrete · 0.011–1.66 Ma", 빅토리아 범례 29 칸
