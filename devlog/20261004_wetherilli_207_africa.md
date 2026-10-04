# 아프리카 — CGMW–BRGM 1:1000만과 BGS 아프리카 지하수 지도책으로 탭을 연다

2026-10-04 · `feature/africa` · wetherilli

docs/다른_대륙_지질도.md 의 "아프리카" 절, TODOs "다른 대륙 › 아프리카" 의 첫 두 줄이다. 판 세션(gsm-31)이 다음 대륙으로 맡겼다.

## 1. 쟀다 (2026-10-04, 요청 사이 2 초)

| | CGMW–BRGM 아프리카 1:1000만 | BGS 아프리카 지하수 지도책(AGA) |
|---|---|---|
| 서버 | `mapsref.brgm.fr/wxs/1GG/IGC35_CGMW_BRGM_Africa_Geology` (MapServer) | `map.bgs.ac.uk/arcgis/services/AGA/BGS_Groundwater` (ArcGIS WMS) |
| 3857 GetMap | 나이로비 둘레 256² 2.1 초·18 KB | 동아프리카 넷 256² 1.7 초·26 KB |
| 속성 | `application/vnd.ogc.gml` — `NOTATION`·`STRATI`·`AGE`·`LITHO` | `text/xml` 의 `<FIELDS KenGLG="Igneous Volcanic" …/>` |
| 범례 | `GetLegendGraphic` 은 빈 예외 — Capabilities 의 정적 PNG(`cgmwafrica_fgeol_legend.png`, 490 KB) | 한 나라의 `GetLegendGraphic` |
| 조건 | Fees `none`·AccessConstraints 빈 칸. 인쇄판은 CGMW 가 판다 | AccessConstraints 에 **CC BY-SA 4.0** 전문 |
| CORS | `*` | 없음 |

지도책은 38 나라 레이어를 쉼표로 이어 한 번에 물어도 그림·속성이 온다(GFI 도 38 레이어를 함께 받는다).

## 2. 문 — 새로 내지 않고 기존 문에 따로 상류로

판 세션이 견줘 달라던 것이다.

- **CGMW–BRGM 은 `brgm.py` 안에 `cgmw` 로** — 서버가 BRGM 의 것(mapsref)이다. 상류마다 문이 하나라는 규칙은 "고칠 자리를 하나로" 가 뜻이라,
  BRGM 이 주소를 바꾸면 한 파일만 보면 된다. 그러나 **상류 이름은 `cgmw` 로 갈랐다** — 지도의 주인과 조건(CGMW, Etalab 이 아님)·출처 문구·
  범례 받는 법(정적 PNG)·속성 꼴(GML)이 프랑스 지질도와 다르다. `bgs.py` 가 GSNI 를 `gsni` 로 따로 두는 꼴(147)을 그대로 따랐다 —
  `brgm.CGMW` 가 `views._Door` 의 셋(`get_map`·`get_feature_info`·`get_legend`)을 낸다
- **지도책은 `bgs.py` 안에 `aga` 로** — 같은 BGS 서버다. 조건이 CC BY-SA 4.0 으로 영국 1:5만(OGL)과 달라 상류 이름을 갈랐다
- 버린 길 — 새 문 둘(`cgmw.py`·`aga.py`). 문 목록이 서른여섯에서 서른여덟이 되고, 같은 기관의 주소가 두 파일로 나뉜다

## 3. 지역 — 탭 하나

판 세션의 말대로 대륙 판이 바탕이라 `africa` 탭 하나로 둔다. 나라 판(남아공 CGS·나미비아 GSN 따위)이 붙으면 남미(188 §3·191)처럼 나라 탭과
묶음으로 가른다. 마이그레이션 0027. 빛깔은 사바나 황토와 바오바브 적갈.

## 4. 레이어

| 이름 | 판 | 범례 |
|---|---|---|
| `cgmw:AFR_CGMW_BRGM_10M_GeologicUnits` | 지질 단위 1:1000만 | 정적 PNG |
| `cgmw:AFR_CGMW_BRGM_10M_Faults` | 단층 1:1000만 | 지질 단위의 PNG(단층이 거기 든다) |
| `cgmw:AFR_CGMW_BRGM_10M_Oceanic_crust_domain` | 해양 지각 1:1000만 | 정적 PNG(바다) |
| `aga:geology` | 나라별 암상 1:500만, 38 나라 | 한 나라(케냐)의 것 |

- **지도책을 레이어 하나로** — 나라 38 개를 따로 두면 패널이 나라 이름으로 덮인다. 나라마다 같은 암상 갈래(열 남짓)라 하나로 묶고, 문이 이어
  묻는다(`bgs.AGA_LAYERS`). 수단·모리타니·보츠와나는 기반암·표층으로 갈려 기반암을 쓴다(표층이 기반암을 덮는다). 남아공·이집트·리비아·
  나미비아 따위는 지도책에 없다 — 그 자리는 1:1000만이 메운다
- **속성** — CGMW 는 기호·지질시대(ICS v2016 영문이라 한국어판이면 `i18n.age_ko` 로. `Paleogene to Pleistocene` 은 남미 판처럼 `A - B` 로
  이어 "고진기~플라이스토세")·연대(`66 - 0.012 Ma`)·암석. 지도책은 나라마다 열 이름이 달라(`KenGLG`·`EthGLG`) `…GLG` 로 끝나는 열을 암상으로 읽는다.
  암상·암석 값은 영어 그대로 둔다
- 수리지질(`_Hydrogeology`)·CGMW 의 바다 나머지 넷(대륙–해양 경계·해양 고원·해양 구조선)은 이번에 넣지 않았다(TODOs)

## 5. 조건

- **CGMW 1:1000만** — 서버의 조건 칸은 비었고 메타데이터는 "License Not Specified" 다. CGMW 는 인쇄판을 판다. 출처를 "© CGMW/BRGM" 과 DOI 로
  적고 **정적 판에 싣지 않는다** — 남미 1:500만(188)과 같은 자리다. TODOs 에 (사람) 줄
- **지도책** — CC BY-SA 4.0. 출처에 적었다. CORS 가 없어 정적 판에 실으려면 서버가 필요하다 — 지금은 싣지 않는다

## 6. 그 밖에

3D 허용 목록(`MAP3D_WMS`), prewarm 의 `PROJECTED`, CLAUDE.md(지역·구조·조건·상류 목록), 영어(i18n).

## 7. 확인

- `test_africa` — GML·FIELDS 읽기, 시대 옮기기(한국어·영어), 38 나라, 씨앗의 지역·출처, CGMW 타일·GML 속성·정적 범례, 지도책의 이어 묻기·속성,
  3D 목록. 전체 시험 1 391 개 통과
- 개발 서버로 아프리카 탭을 열어 나이로비를 눌렀다 — 지도책 "Igneous Volcanic", CGMW "Qv · 제4기 · 2.6 - 0 Ma · Volcanic" 과 그 밑의
  "NPm · 신원생대"·"Nv · 신진기". CGMW 범례 그림이 섰다
