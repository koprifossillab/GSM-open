# 정적 판 점검 — 오늘 붙은 상류 가운데 고를 수 있는 것

2026-10-05 · `feature/static-optional` · wetherilli

판 세션이 준 일 — 오늘 붙은 상류 가운데 조건이 열리고(CC BY·CC0·공공 도메인) CORS 가 되는 것을 `static_site.py` 의 `OPTIONAL` 후보로.
싣는 것은 사람이 정하므로 기본값은 그대로 두고 `--with <이름>` 으로만 둔다. 목록은 #153 에 한 덩이로 적었다.

## 1. 먼저 고친 것 — 이미 있던 `--with` 둘이 오늘 넓힌 레이어를 못 따라갔다

정적 판의 카탈로그(`views._static_catalog`)는 **상류 이름으로** 레이어를 고른다. 그래서 문에 레이어를 더하면 정적 판에도 저절로 선다 —
그런데 브라우저 쪽 손질(`static-kinds.js`)은 저절로 따라오지 않는다.

- **`--with australia`** — GA 의 지질구·핵심 광물·지구물리 격자(wetherilli 241)는 다른 서비스인데, 표(`ga.layers`)에는 지표 지질도 넷만
  있었다. 정적 판은 그 레이어를 **빈 레이어 이름으로** 물었을 것이다. 표에 `other`(주소·레이어·누르기)를 더하고, 누르기는 서버의
  `ga.queryable` 처럼 거르고, 손질에 `other_friendly` 를 옮겼다. 지질구·광물은 범례 그림도 서버처럼 받는다
- **`--with usa`** — 광물 자원 MRDS·광산 기호 USMIN·연대 기록(247)과 하와이·푸에르토리코(238)는 그림은 섰지만 팝업 손질이 본토 SGMC 갈래로
  떨어져 칸이 거의 비었을 것이다. `mrdata.friendly` 의 갈래 다섯과 `_island_age` 를 옮겼다

둘 다 node 대조 시험(`test_static_kinds`)에 견본을 더해 파이썬과 같은 답을 내는지 본다.

## 2. 새로 둔 것 — 유럽 넷

| `--with` | 상류 | 조건 | CORS (2026-10-05, 한 번씩) |
|---|---|---|---|
| `netherlands` | TNO 지표 지질도 | CC0 | `*` |
| `belgium` | 플랑드르 DOV·왈로니아 SPW | 무료 재사용 표준 라이선스 / CC BY 4.0 | `*` / Origin 을 되비춘다 |
| `austria` | GeoSphere 1:100만 지질·단층 | CC BY 4.0 | Origin 을 되비춘다 |
| `poland` | PIG-PIB 1:50만·1:5만 | "접근·이용 조건 없음" | Origin 을 되비춘다 |

다섯 문이 모두 `arcwms.Door` 를 쓴다. 그래서 상류마다 KIND 를 따로 짓지 않고 **표 하나·손 하나**로 했다 — 표(`static_tables.ARC`)는 문의
주소·레이어·누르기·속성 꼴·더 붙일 변수(`propertyName`)를 그대로 뜨고, JS 의 `arcKind` 가 서버의 `arcwms.Door` 처럼 1.1.1 로 묻는다. 상류마다
다른 것은 팝업 손질뿐이라 그것만 JS 에 옮겼다. 시대는 넷 다 `i18n.age_local`(독일어·네덜란드어·폴란드어·프랑스어)을 거쳐 표째 실어
JS 로 옮겼다(`ageLocal`). 범례는 서버의 `get_legend` 가 고르는 WMS 레이어를 표에 떠 둔다 — 지오스피어는 첫 레이어, 폴란드는 마지막,
왈로니아는 서버도 두지 않는다.

- **지오스피어 1:5만은 빠진다** — WMS 가 꺼져 서버가 REST `export`·`identify` 로 옮기는 레이어라 브라우저가 곧장 부를 꼴이 아니다.
  카탈로그가 `arc_layers` 에 없는 레이어를 거른다
- 타일 다섯은 JS 가 짓는 변수 그대로 서버에서 한 장씩 받아 보았다(모두 200 PNG). TNO 의 속성도 `propertyName` 을 붙여 받아 보았다.
  시험 브라우저는 이 망에서 밖의 https 를 못 받아(KOPRI 가로채기) 화면으로는 보지 않았다
- 실제로 `--with netherlands --with belgium --with austria --with poland --with australia --with usa` 로 구워 보았다(21.4 MB)

## 3. 후보로만 적은 것 — 품이 더 든다

- **캐나다**(NRCan OGL–Canada·사스카치원·앨버타·노바스코샤) — 조건은 열렸고 CORS 도 되지만 3978 이고 문마다 꼴이 달라(geojson·REST export·
  피처 서비스 query) KIND 를 하나씩 지어야 한다. 탭의 다른 상류(OGS·BCGS·YGS·SIGÉOM)는 서지 않으니 반쪽 탭이 된다
- **카리브 USGS 1:250만·파나마 STRI**(공공 도메인 / CC BY-SA 4.0, CORS `*`) — 피처 서비스라 그림이 없어 서버가 면을 한 덩이로 받아 준다.
  정적 판에는 `bake_static` 이 구워 실어야 한다(얀마옌·극지 점과 같은 길). STRI 는 SA(같은 조건으로 나눔)라 사람이 한 번 더 본다
- **대앤틸리스 SIM 3534**(#240) — 서버가 파일에서 그리는 타일이라 타일째 구워야 한다
- 같은 날 붙은 니카라과 INETER 는 조건 글이 없고, 부르키나파소·카메룬은 비상업이라 후보에서 뺐다
