# 남미 — 아르헨티나 SEGEMAR(1:250만·1:25만)와 우루과이 DINAMIGE(1:50만)

2026-10-04 · `feature/argentina-uruguay` · wetherilli

docs/다른_대륙_지질도.md 의 "아르헨티나 — SEGEMAR SIGAM"·"우루과이 — DINAMIGE" 절, TODOs "다른 대륙 › 남미". 남쪽 원뿔을 채운다.

## 1. 쟀다 (2026-10-04, 요청 사이 2 초)

| | 아르헨티나 SEGEMAR | 우루과이 DINAMIGE |
|---|---|---|
| 서버 | SIGAM GeoServer 2.17 (`sigam.segemar.gov.ar/geoserver217/ows`) | ArcGIS WMS (`geoportal.miem.gub.uy/arcgis1091/…/MapaBaseUnidadesGeologicasGeoS`) |
| 3857 GetMap | 멘도사 256² 2.4 초·53 KB, 실제 지질도 | 몬테비데오 둘레 256² 2.9 초·53 KB, 실제 지질도 |
| 속성 | `application/json` + `propertyName`(기하를 뗀다) 1.1 초·0.5 KB | `application/geo+json` 1.8 초 |
| 범례 | JSON 범례는 NPE, `hideEmptyRules`+범위는 2×1 빈 그림 | WMS 범례는 18×18 빈 그림, REST `legend?f=json` 35 KB(칸 61) |
| CORS | 없다 | Capabilities 만 Origin 을 되돌린다 — 그림·속성에는 없다 |

**우루과이의 WMS 번호는 REST 와 거꾸로다.** REST 는 0 암맥·1 선·2 지질 단위인데, WMS `2` 만 물으면 빈 그림이었다. 하나씩 그려 보니
WMS `0` 이 지질 단위였다. SGC(188)처럼 이름은 WMS 번호(`dinamige:0`)로 하고, 범례만 REST 번호로 옮겨 묻는다(`dinamige.REST_ID`).

아르헨티나 1:25만의 속성이 비어 온다던 문서의 메모는 지금은 아니다 — 멘도사 도폭(3369-II)의 이름·암석·연대가 온다.

## 2. 조건 — 둘 다 정적 판에 싣지 않는다

- **SEGEMAR** — AccessConstraints "SEGEMAR 의 재산. 크리에이티브 커먼즈 아르헨티나 라이선스로 쓸 때 저작자를 밝힌다", Fees "보기는 자유·무료".
  출처 표기(`segemar.ATTRIBUTION`)에 "CC Argentina, atribución" 을 적었다
- **DINAMIGE** — Capabilities 의 AccessConstraints·Fees 가 비었고, 서비스 설명·`copyrightText` 도 비었다. MIEM 의 지도 안내 쪽에도 조건이
  없다. 출처 "DINAMIGE (MIEM)" 를 밝히고, 밖에 열기 전에 사람이 읽는다(TODOs)
- 둘 다 **CORS 가 없다** — 정적 판의 브라우저가 곧장 부를 수 없다. 서버 문(`segemar.py`·`dinamige.py`)으로만 간다

## 3. 지역 — 나라 탭 둘, 그리고 "남쪽 원뿔" 안을 버린 까닭

191 의 꼴(나라 탭 + 묶음 `south_america`, 남미 1:500만은 콜롬비아 지역에 두고 빌림)을 따랐다 — `argentina`·`uruguay` 를 더하고 묶음이 넷을 품는다.

"남쪽 원뿔"(아르헨티나·우루과이·칠레·파라과이) 하나로 묶는 안도 견줬다.

- 좋은 점 — 탭이 덜 갈린다. 우루과이는 작아 탭 하나가 아깝다
- 버린 까닭 — (1) 지역은 DB 의 `LayerGroup.region` 이고 레이어군마다 하나다. 아르헨티나·우루과이 판이 한 지역에 들면 홈 범위·대표 레이어·
  예시 좌표를 하나로 정해야 한다. 우루과이를 보려면 매번 아르헨티나 넓이에서 들어가야 한다. (2) 191 이 이제 막 "나라 탭 + 묶음" 으로 갈랐다.
  남미에서만 꼴이 둘이 되면 읽는 사람이 헷갈린다. (3) 칠레·파라과이는 나라 판이 없다(칠레 연결 거부, 파라과이 서비스 없음) — 원뿔의 반이 비고,
  그 자리는 묶음 "남미" 가 1:500만으로 이미 메운다
- 탭이 많아 보이는 것은 "+ 추가 지역" 에서 고르는 것이라 늘 서 있지 않다. 묶음 "남미" 를 열면 넷이 한 화면이다

빛깔 — 아르헨티나는 페리토 모레노 빙하의 청록(국기의 하늘색은 우루과이와 겹친다), 우루과이는 아르티가스의 마노·자수정 지오드의 보라.

## 4. 레이어

| 이름 | 판 | 그리는 줌 | 범례 |
|---|---|---|---|
| `segemar:e2.5M.UnidadesGeologicas` | 지질 단위 1:250만 | 늘 | 그림 |
| `segemar:e2.5M.Estructuras` | 구조선 1:250만 | 늘 | 그림 |
| `segemar:e2.5M.VolcanesInventario` | 화산 목록 | 늘 | 그림 |
| `segemar:e250K_UnidadGeologica` | 지질 단위 1:25만(간행 도폭) | 줌 9 부터 | 그림 |
| `segemar:e250K.Fallas` | 단층 1:25만(간행 도폭) | 줌 9 부터 | 그림 |
| `dinamige:0` | 지질 단위 1:50만 | 늘 | 목록 |
| `dinamige:1` | 단층·접촉·선구조 1:50만 | 늘 | 목록 |
| `dinamige:2` | 암맥 1:50만 | 늘 | 없음(칸 하나, 이름 없음) |

- **속성** — 값은 에스파냐어 그대로(콜롬비아·스페인과 같다). 지질시대도 `Pleistoceno inferior` 꼴이라 옮기는 표가 없다. 아르헨티나는
  아래·위 시대가 다르면 `아래 - 위` 로 잇는다. 우루과이는 통 > 계 > 대 > 누대 가운데 적힌 가장 잘게 가른 것을 쓴다
- **범례** — 아르헨티나는 상류의 그림 한 장(1:250만 554×3 280)을 그대로 낸다. 보는 범위의 범례(191)를 하고 싶었지만 이 GeoServer 판이 받지 못한다.
  우루과이는 REST 범례를 목록으로(`dinamige/legend/`) — 칸마다 상류의 견본 그림을 그대로 싣는다(무늬가 보인다). 이름은 `FORMACION DOLORES - Cuaternario
  Pleistoceno` 꼴이라 마지막 ` - ` 에서 이름과 시대로 가른다
- 버린 판 — 아르헨티나의 1:100만 북서부·주별 1:75만·국경 1:50만·말비나스, 물리탐사·자원·위험도 판(TODOs). 1:250만이 나라를 덮고 1:25만이 가까이를 맡는다

## 5. 그 밖에

- 3D 허용 목록(`MAP3D_WMS`)과 묶음(`BUNDLES.south_america`), `prewarm` 의 `PROJECTED` 에 둘을 더했다
- 마이그레이션 0025(지역 고르기에 둘). 같은 날 gsm-91 의 페루(wetherilli 195, #177)가 먼저 들어와 0024 를 가져갔다 — 그 뒤에 맞추고 지역 목록·묶음·문 목록을 합쳤다

## 6. 확인

- `test_segemar_dinamige` — 열 옮기기, 씨앗의 지역·줌·범례 갈래, 워크스페이스를 붙인 3857 타일, `propertyName` 으로 받는 속성, 우루과이 타일·속성(WMS 번호),
  REST 범례 목록(캐시·REST 번호), 3D 목록. 전체 시험 통과
- 개발 서버로 두 탭을 열었다 — 멘도사에서 "Qa Depósitos pedemontanos · Holoceno", 우루과이 남부(남위 34.3°)에서 "Q1_l FORMACION LIBERTAD · Pleistoceno".
  우루과이 범례가 견본 무늬와 함께 목록으로 섰다
