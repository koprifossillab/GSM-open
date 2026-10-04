# 호주 — Geoscience Australia 지표 지질도 1:250만·1:100만

2026-10-04 · `feature/australia` · wetherilli

판 세션이 캐나다(#192)를 기다리는 사이의 일로 호주를 맡겼다. 근거는 TODOs 의 "호주 GA WMS 는 응답한다" 한 줄과
[docs/새_상류_후보.md](../docs/새_상류_후보.md) 의 GA 주소다.

## 1. 쟀다 (2026-10-04, 몇 번만)

- `services.ga.gov.au/gis/services/GA_Surface_Geology/MapServer/WMSServer` — Capabilities 200(2.2 초). 레이어는 1:250만·1:100만 판마다
  암층층서·암상·연대로 칠한 단위 면, 접촉·단층·잡선, 그리고 5M 변성암·지질구
- AccessConstraints: "© Commonwealth of Australia (Geoscience Australia) 2016 … **CC BY 4.0**". Fees none. Origin 을 되비춘다
- **판이 축척에 따라 갈마든다** — REST 의 minScale·maxScale 로 1:250만 판은 1:150만보다 멀 때, 1:100만 판은 가까울 때만 그린다
- 대륙 줌(4) 512² 가 3.2 초, 퍼스 둘레(줌 9) 1.6 초. REST 에는 3857 타일 캐시도 있다(`singleFusedMapCache`) — 판의 모든 레이어를 한 장에 구운 것이라 쓰지 않았다
- 속성은 `application/geo+json` 로 기하 없이 2 KB — GeoSciML 꼴(name·description·geologicHistory·lithology·mapSymbol, 영어)
- 범례 그림은 198×4096. REST 칠하기 규칙은 `PLOTSYMBOL` 값마다(1:100만 294 칸, 1:250만 102 칸), 통계 질의가 된다 — 단, **열 이름을
  소문자로**(`plotsymbol`·`geolhist`) 물어야 한다. 큰 글자면 400 "Unable to complete operation"

## 2. 투영 — 3857

견준 것은 3857 과 호주 알베르스(3577)다. **3577 로 물으면 빈 그림(1 KB)** 이다 — Capabilities 의 CRS 에도 없다(3857·4326·UTM 들뿐).
서비스의 원래 투영이 3857(102100)이고, 호주는 남위 10–44° 라 3857 의 부풂이 남위 44° 에서 1.4 배 남짓이다(남미 탭과 비슷한 위도). 3577 을 쓰려면
화면이 3857 타일을 옮겨 그려야 하는데, 그럴 값이 없다. 그래서 3857 이다.

## 3. 레이어 하나가 두 판을 부른다

갈래(암층층서·연대·암상·단층)마다 레이어 하나를 두고, 문이 그 갈래의 1:250만·1:100만 WMS 레이어를 **함께** 묻는다(`LAYERS=…2500k…,…1M…`).
상류가 축척에 맞는 판만 그리므로 화면은 줌을 몰라도 된다. 판을 레이어 둘로 가르면 사람이 줌마다 바꿔 켜야 하고, 한쪽은 늘 빈 그림이다.

범례만은 판을 골라야 한다 — 범위의 너비가 6° 보다 넓으면 1:250만(REST 3·4·5), 좁으면 1:100만(REST 10·11·12)의 단위를 센다
(`ga.rest_layer`). 1:150만이 화면 너비로 6–8° 남짓이라 상류가 그리는 판과 맞는다. 칠하기 규칙은 판마다 30 일 담는다.

## 4. 그 밖

- 시대 — GeoSciML 의 `Cenozoic to Quaternary` 를 `Cenozoic - Quaternary` 로 이어 `i18n.age_ko`(신생대~제4기)
- 지역 `australia`(마이그레이션 0031 — 캐나다 0030 뒤). 빛깔은 그레이트배리어리프의 산호빛
- 3D 허용 목록·prewarm(`PROJECTED`)에 `ga`
- **정적 판** — CC BY 4.0 이고 Origin 을 되비춰 `OPTIONAL` 에 `australia` 를 두었다(기본값 아님). `static-kinds.js` 의 `KINDS.ga` 는 `wmsKind`
  그대로이고 속성 꼴만 geo+json 이다. 보는 범위의 범례는 서버 길이라 정적 판에는 없다 — 지도 화면이 정적 판에서 범례 칸을 그릴 때 상류 손에
  범례가 있으면 서버 길(`legendUrl`)보다 그쪽을 먼저 타게 고쳤다(호주는 "범례가 없다" 로 뜬다)

## 5. 확인

- DB 사본으로 호주 탭을 열었다 — 타일 200, 페이지 오류 없음. 퍼스 둘레를 누르면 "Czy · Cenozoic alluvium · 팔레오세~홀로세 · 1:2,500,000"
- 범례 — 퍼스 둘레 0.7° 는 1:100만 11 칸, 대륙 전체는 1:250만 102 칸 가운데 60 칸
- 시험 `test_ga` — 속성 손질, 판 고르기, 두 판을 함께 묻기, 범례의 판·열(소문자)·색. `test_static_kinds` — JS·파이썬 손질 대조
