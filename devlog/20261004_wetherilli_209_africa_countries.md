# 아프리카 나라 판 — 남아공 CGS·나미비아 GSN 1:100만 (탄자니아는 TLS 로 막혔다)

2026-10-04 · `feature/africa-countries` · wetherilli

판 세션이 207(아프리카 탭) 다음으로 맡긴 것이다. docs/다른_대륙_지질도.md 의 아프리카 "나라별" 절 §6·9·10, TODOs "다른 대륙 › 아프리카".
RMCA(콩고·르완다·부룬디)는 조건을 물어야 해 하지 않았다.

## 1. 쟀다 (2026-10-04, 요청 사이 2 초)

| | 남아공 CGS 1:100만 | 나미비아 GSN 1:100만 | 탄자니아 GMIS 1:150만 |
|---|---|---|---|
| 서버 | 정부 DPME 의 ArcGIS 11.3 `dpmegis.dpme.gov.za/…/Geology/MapServer` 레이어 5 (CGS 자신의 서버는 45 초 시간 초과) | `ogc.bgs.ac.uk/cgi-bin/BGS_GSN_Bedrock_Geology/wms` (BGS 가 대신 내주는 MapServer) | `gmis-tanzania.com/geoserver/gmis/wms` |
| 그림 | **WMS 가 꺼져** REST `export` — 요하네스버그 250 km 네모 10.9 초, 100 km 2–3 초 | 3857 GetMap 1.6 초 | — |
| 속성 | `identify` 1.8 초 — `STRAT_NAME`·`STRAT_PAR_`·`CHRONO_NAM`·`LITHO_1..5`·`LABEL` | `text/plain` — `AGE`·`SEQUENCE`·`GROUP`·`FORMATION`·`ROCKTYPES`·`MAPCODE` | — |
| 범례 | REST `legend` 시대 12 칸 | GetLegendGraphic | — |
| 조건 | `copyrightText` 빈 칸. 자료의 주인 CGS 는 자료를 판다 | AccessConstraints "available from the Geological Survey of Namibia, contact sales@…", Fees "N$283" | Fees·AccessConstraints NONE |

**탄자니아는 TLS 로 막혔다.** 이 서버에서는 인증서 검증이 실패했다 — 연구소 망의 가로채기 장비가 그 호스트의 인증서를 "UNTRUSTED CERT ALERT"
라는 이름으로 다시 서명한다(원래 인증서를 믿지 못할 때 그렇게 한다). 바깥(WebFetch)에서도 "unable to verify the first certificate" 다 — 서버가
중간 인증서를 빼먹었다. 브라우저는 AIA 로 메워 열지만 `requests` 는 그러지 않는다. **TLS 검증을 끄지 않고는 받을 수 없다.** 검증을 끄는 것은
사람이 정할 일이라 TODOs (사람) 줄과 #153 에 남기고 하지 않았다.

나미비아는 MapServer 라 `GetFeatureInfo` 에도 `STYLES`·`FORMAT` 이 있어야 한다 — 없으면 `MissingParameterValue` 다. 문이 채운다.

## 2. 문

- **남아공은 새 문 `cgs.py`** — 정부 부처의 ArcGIS 다. 화면은 다른 상류처럼 WMS 변수를 보내고(`npolarSource`), 문이 `export`·`identify` 로 옮긴다.
  NPI(021)·멕시코(206)와 같은 수지만 문은 서로를 타지 않아 따로 둔다
- **나미비아는 `bgs.py` 안의 `gsn`** — BGS 서버가 대신 내준다. GSNI(147)·AGA(207)와 같은 꼴로 상류 이름만 갈랐다(주인과 조건이 다르다)
- 문이 하나 늘었다(`cgs.py`)

## 3. 조건 — 자료를 파는 둘은 서버 캐시에 담지 않는다

둘 다 보기(WMS·REST)는 열어 두었지만 자료는 판다. 우리 서버는 받은 타일을 디스크에 담아 다시 내주는데(007), 파는 자료를 그렇게 쌓아 다시 내주는 것은
문서의 권고("캐시로 다시 내주지 않는다")와 어긋난다. 그래서 **`views.NO_STORE`** 를 두어 이 둘은 타일·속성을 담지 않고 그때그때 받아 보여 주기만 한다.
범례(칸 이름)는 지도 자료가 아니라 담는다. 브라우저의 하루 캐시는 그대로다(다시 내주는 것이 아니다). prewarm 에도 넣지 않았다 — 담지 않는 것을 미리 받을 까닭이 없다.
값 — 남아공의 넓은 그림은 매번 11 초까지 걸린다. 담아도 되는지는 사람이 정한다(TODOs).

출처 — "Council for Geoscience (via DPME GIS)", "Geological Survey of Namibia (served by BGS)". 정적 판에 싣지 않는다.

## 4. 지역 — 나라 탭으로 가르지 않았다

판 세션이 "나라 판이 셋 붙으면 남미처럼 나라 탭과 `africa` 묶음으로 가를지" 견줘 달라고 했다. 이번에 붙은 것이 둘이라 셋이 아니지만 미리 견줬다.

- **가르는 길**(남미 191) — `south_africa`·`namibia` 를 DB 지역으로, `africa` 를 묶음으로. 그러려면 대륙 판(CGMW·지도책)을 어느 한 나라 지역으로
  옮겨야 한다(묶음은 DB 에 없다). 남미는 SGC 의 1:500만을 SGC 의 나라(콜롬비아)에 두었는데, CGMW(국제 위원회)·BGS 지도책(영국)은 주인 나라가 이 셋에 없다 —
  남아공에 두면 "남아공 탭에 아프리카 지도책" 이 되어 읽는 사람이 헷갈린다. 묶음이 자기 자신을 품게(`includes: ["africa", …]`) 하는 길은
  지역 고르개(`parentOf`)가 그 탭을 세우지 못해 깨진다
- **탭 하나에 얹는 길**(고른 것) — 나라 판이 대륙 판과 같은 3857 이라 한 탭에서 겹쳐 보는 데 걸림이 없다. 걱정은 나라 판이 대륙 전체의 타일을 묻는 것
  (호출 제한, 010) — 묶음 탭이 쓰는 범위 거르기(024)를 아프리카에도 켰다(`REGIONS.africa.clip`). 넓은 화면에서도 남아공 타일은 남아공 둘레만 묻는다(개발 서버로 확인)
- 나라 판이 많아져 패널이 길어지거나 나라마다 홈·대표 레이어가 필요해지면 그때 가른다. 대륙 판을 둘 지역을 새로 정하는 일(예: "아프리카 전체" 를 DB 지역으로
  두고 묶음 열쇠를 따로)이 먼저다

## 5. 확인

- `test_africa_countries` — 열 옮기기(상류의 열 이름 오타 `LITH0_2` 까지), WMS 변수 → export, 서버 캐시에 담지 않음(두 번 물으면 두 번 간다), identify, MapServer 의
  styles·format, REST 범례. 전체 시험 1 415 개 통과
- 개발 서버로 아프리카 탭을 열었다 — 요하네스버그 "KLIPRIVIERSBERG (GRP) · VENTERSDORP · RANDIAN · ANDESITE, TUFF · Rk", 빈트후크 "Nk · Namibian · Damara ·
  Swakop · Khomas · Kuiseb · Mica schist …". 넓은 화면에서 남아공 export 가 남아공 둘레만 나갔다
