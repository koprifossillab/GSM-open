# 스웨덴 — SGU 기반암 1:100만·1:5만–25만을 노르웨이·핀란드 탭에

2026-10-04 · `feature/sweden-sgu` · wetherilli

판 세션이 맡겼다. 근거는 TODOs "다른 나라 지질도" 의 "스웨덴(SGU)이 오면 노르웨이·핀란드 탭에 더한다" 줄이다(wetherilli 140).

## 1. 쟀다 (2026-10-04, 요청 사이 2 초, 스무 번 남짓)

- **안내 문서의 주소는 Capabilities 만 준다.** `resource.sgu.se/service/wms/130/berggrund_1M` 은 GetMap·GetFeatureInfo·GetLegendGraphic 을
  물어도, 변수 이름을 대문자로 바꿔도 Capabilities(25 KB)를 돌려준다. 그 Capabilities 의 `OnlineResource` 가 가리키는 GeoServer
  `maps3.sgu.se/geoserver/berg/ows` 가 실제로 그린다. 이 주소를 쓴다. 문서에 없는 뒷문이 아니라 SGU 의 Capabilities 가 적은 주소다
- **투영** — Capabilities 는 3006·3857·4326 만 적는다. 그런데 GeoServer 라 3413·3575 도 그려 준다(스톡홀름 둘레 300 km 가 꽉 찼다). GTK(140)처럼
  탭의 3413 으로 곧장 받는다. NGU 처럼 3575 로 돌아갈 까닭이 없다
- **판 둘** — 1:100만(`SE.GOV.SGU.BERGGRUND_NA10`, 면)과 1:5만–25만(`SE.GOV.SGU.BERG.GEOLOGISK_ENHET.YTA.50K` 외 220 레이어)이다.
  5만 판은 **1:50만 남짓보다 가까울 때만** 그린다(1:42만에서 꽉 차고 1:56만부터 빈 그림). 덮지 않은 곳도 있다
- **속성** — `application/json`. 1:100만은 스웨덴어 열 옆에 **영어 열**(`lithology`·`tect_unit`·`subunit`)을 따로 준다. 5만은 스웨덴어뿐이고
  빈 칸을 `Null:okänt`·`Null:saknas` 로 채운다. GeoServer 는 누른 둘레의 이웃 면을 너덧 함께 준다
- **범례** — GetLegendGraphic 이 온다. 1:100만은 555×5 576 으로 길다
- CORS `*`, 한 장 1–2 초
- **조건** — Fees·AccessConstraints `NONE`. SGU 는 **2024-06-09 부터 모든 지질 자료를 CC0 1.0** 으로 열었다(EU 고가치 자료 규정,
  sgu.se "Licensvillkor för SGU:s geologiska data")

## 2. 레이어 하나가 두 판을 — GA 와 같은 꼴

판 세션이 "5만 220 판은 화면 줌으로 갈라 1:100만과 함께 묶는 꼴(GA·EGDI 처럼)" 로 생각해 달라고 했다. 두 판을 한 번에 물으니
(`layers=NA10,…YTA.50K`) GeoServer 가 1:100만 위에 5만을 얹어 그린다 — 멀면 5만이 비어 1:100만만 보이고, 가까우면 5만이 덮은 곳은 5만,
안 덮은 곳은 1:100만이 비친다. 줌 갈림을 우리가 셈하지 않아도 상류의 축척 규칙이 해 준다. 그래서 카탈로그 레이어는 둘이다.

- `sgu:bedrock` — 기반암 (1:100만 · 가까우면 1:5만–25만). 범례는 1:100만 판의 것(5만은 칸이 수천)
- `sgu:deformation` — 변형대 (1:100만). 선이 가늘어 둘레 40 픽셀로 물어도 걸리지 않아 누르기를 껐다(`queryable: False`)

**버린 것** — 5만의 220 레이어(층리·구조선·광물 산출지 따위)를 낱낱이 싣는 것. 노르웨이·핀란드도 기반암 면과 선 한둘만 실었다.
필요해지면 `sgu.LAYERS` 에 한 줄씩 더한다. 5만 판을 따로 켜는 레이어(1:100만 없이)도 두지 않았다 — 멀리서 빈 레이어가 되어 헷갈린다.

속성은 자세한 판부터 묻고(`query_layers` 를 거꾸로) **판마다 첫 하나**만 남긴다. 둘레는 1 픽셀(`buffer`). 가까이서 누르면 5만의 단위와
그 밑의 1:100만 단위가 한 덩이씩 뜬다. 1:100만은 영어 열을 쓴다 — 값은 옮기지 않는다는 규칙(CLAUDE.md "영어판")은 지키고, 상류가 준
두 말 가운데 읽을 수 있는 쪽을 고른 것이다. 5만은 스웨덴어 그대로다.

## 3. 탭 이름 — "노르웨이·스웨덴·핀란드"

스웨덴이 들어오니 "노르웨이·핀란드" 는 틀린 이름이다. 화면의 제목(`map.js`)·영어·CLAUDE.md 를 "노르웨이·스웨덴·핀란드" 로 바꿨다.
지역 열쇠(`fennoscandia`)는 그대로다. **`models.REGIONS` 의 표시 이름은 두었다** — 바꾸면 choices 가 바뀌어 마이그레이션이 생기고,
여러 가지가 마이그레이션 번호를 함께 세는 지금(0029 아프리카·0030 호주…) 번호가 또 부딪힌다. 그 이름은 관리 화면에만 보인다.
다음에 지역 마이그레이션이 생길 때 함께 바꾼다.

## 4. 3D·미리 데우기·정적 판

- **3D** — GeoServer 가 3857 도 그려 `MAP3D_WMS` 에 넣었다. 이 탭에서 3D 로 얹을 지질 레이어가 처음 생긴다(NGU·GTK 는 극지 투영뿐).
  3D 의 북극 묶음(`map3d.js` 의 `BUNDLES.arctic`)에 `fennoscandia` 가 빠져 있어 더했다 — 2D 의 `REGIONS.arctic.includes` 와 맞춘다
- **미리 데우기** — `prewarm.PROJECTED` 에 더했다(투영된 탭의 3413 타일)
- **정적 판** — CC0 이고 CORS `*` 라 브라우저가 곧장 부를 수 있다. `static-kinds.js` 의 `KINDS.sgu` 가 서버 판처럼 두 판을 함께 부르고,
  누르기(자세한 판부터, 판마다 하나)·범례(1:100만)를 같은 셈으로 한다. 손질은 문의 표(`sgu.FRIENDLY`)를 `static_tables` 로 떠 간다 —
  `test_static_kinds` 가 서버와 같은 값을 내는지 본다. 기본으로는 싣지 않고 `--with sweden` 으로 고른다(콜롬비아·미국과 같다).
  고르면 이 탭에 SGU 만 선다 — NGU·GTK 는 서버 판에만 있다

## 5. 확인

- `test_sgu` — 판 이름 바꾸기, 판마다 하나, 손질(`Null:…` 빼기), 3413 그림, 속성 차례·buffer, 범례, 정적 판 고르기. 전체 시험 통과
- 개발 서버로 탭을 열었다 — 줌 4 에 스웨덴 전체(1:100만), 스톡홀름 줌 10 에 5만 판. 누르면 "Vacka · Svekokarelska orogenen · Ba 60"(5만)과
  "Granitoid and subordinate syenitoid (c. 1.91-1.87 Ga) · Svecokarelian orogen · Bergslagen lithotectonic unit"(1:100만)이 함께 뜬다
