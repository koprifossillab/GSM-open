# 페루 — INGEMMET 1:5만·1:10만 통합판을 타일 캐시로

2026-10-04 · `feature/peru-ingemmet` · wetherilli

판 세션이 남미에 페루를 맡겼다. 후보와 첫 실측은 [docs/다른_대륙_지질도.md](../docs/다른_대륙_지질도.md) 의 "페루" 절이다.
지역은 브라질(191)이 세운 꼴 그대로다 — 나라 탭 `peru` 를 더하고, 묶음 "남미" 에 넣고, SGC 의 남미 1:500만을 `sgc:sa:` 앞머리로 빌린다.

## 1. 무엇을 실었나 — 통합판 둘

GEOCATMIN 에는 지질 서비스가 여럿이다. 실은 것은 **1:5만 통합판**(`SERV_GEOLOGIA_50K_INTEGRADA`, 2005–2011 갱신, 폴리곤 15 만 7 천 —
남미에서 가장 자세한 전국판)과 **1:10만 통합판**(`SERV_GEOLOGIA_100K_INTEGRADA`)이다. 1:10만은 1:5만이 비는 곳(아마존 쪽 저지대)을 더 덮고
속성이 짧다.

- 버린 것 — **세계판**(`SERV_GEOLOGIA_MUNDIAL`)은 CGMW 세계 지질도를 DVD 로 사서 올린 것이라 싣지 않는다(문서의 판단 그대로).
  해양 지질·지역 지도 모음(`SERV_GEOLOGIA_MARINA`·`SERV_MAPAS_GEOLOGICOS`)은 이번 범위가 아니다

## 2. 쟀다 (2026-10-04, 요청 사이 1–2 초)

- Capabilities 200, CRS 에 3857 이 있다. 1:5만 레이어는 WMS `0` 암상·`1` 지형·`2` 암맥·`4` 습곡·`5` 단층·`7` 관찰점,
  1:10만은 `0` 지질·`3` 단층 따위. **WMS 번호는 REST 번호를 뒤집었다**(WMS `0` = REST `7`)
- **WMS 로 넓게 물으면 못 쓴다** — 리마 둘레 줌 9 한 장은 2–3 초인데, 페루 전체 줌 5 한 장이 1:5만 **46 초**, 1:10만 **33 초**였다.
  폴리곤 15 만 개를 그 자리에서 그리기 때문이다
- **REST 타일 캐시는 빠르다** — 두 판 다 `singleFusedMapCache` 이고 3857 256 px(`tile/{z}/{y}/{x}`)다. 줌 5·8·12 모두 한 장에 1.3–1.8 초.
  캐시는 **1:5만이 줌 13**, **1:10만이 줌 16** 까지 있고 그 너머는 404 다. 리마 시내까지 실제 지질도(도시 면은 회색)
- 속성 — WMS `GetFeatureInfo` 는 geo+json 으로 기하 없이 5 KB 다. REST `query`(점 하나, `returnGeometry=false`)도 같은 열을 준다.
  빈 값이 `" "`·`"<Null>"` 로 온다
- 범례 — REST 범례 JSON 은 1.9 MB, 1:5만 암상의 칠하기 규칙(`drawingInfo.renderer`)은 `CODI` 값마다 색 하나로 3 261 칸(880 KB)이다.
  1:10만은 `NAME` 으로 1 340 칸(240 KB)

## 3. 고른 것

- **그림은 타일 캐시로**, 일본(GSJ)처럼 우리 서버가 z/x/y 를 중계해 담는다(`ingemmet/<판>/{z}/{x}/{y}.png`). 넓은 줌에서 46 초짜리 WMS 를
  기다리게 할 수 없다. 대가는 캐시가 **판의 모든 레이어를 한 장에 구운 것**이라는 점이다 — 단층·습곡·암맥을 따로 켜고 끌 수 없다(TODOs).
  캐시 밖(바다·나라 밖)의 404 는 빈 타일로 담는다 — 다시 물을 까닭이 없다
- **누른 자리는 REST `query`** 로 묻는다(`ingemmet/info/`). 그림이 WMS 가 아니라서 화면이 WMS 속성 주소를 지을 수 없다. 일본처럼 위경도로
  묻고 서버가 그 점을 품은 면을 받는다. WMS 와 REST 의 번호·열 이름(`TIP_UNIDAD`·`TIPO_UNIDAD`)이 엇갈려 REST 하나로 맞췄다
- **범례는 보는 범위의 것**(`ingemmet/legend/`) — ArcGIS 에는 GeoServer 의 `hideEmptyRules`(191) 같은 것이 없다. 범위 안의 단위는
  **통계 질의**(`groupByFieldsForStatistics` + 개수)로 받는다 — 리마 둘레 55–57 줄·9 KB·2 초. 처음엔 `returnDistinctValues` 를 썼는데
  같은 단위를 1 342 번 돌려줬다(271 KB). 색은 칠하기 규칙에서 찾고, 규칙은 한 번 받아 30 일 담는다. 범례를 뜨는 가장 넓은 범위는
  1:5만 4°, 1:10만 6° 다 — 넓으면 통계 질의도 무거워진다
- **지질시대** — 에스파냐어(`Cretácico`·`Jurásico`)를 ICS 영문으로 옮기는 작은 표(`ingemmet.AGES_ES`)를 거쳐 한국어판이면 `i18n.age_ko`.
  콜롬비아 판(188)은 그 나라 말 그대로 두었지만, 여기는 1:5만이 기(sistema)를 따로 적어 옮기기 쉽다. 이름·암석·설명은 에스파냐어 그대로
- **빛깔** — 티티카카 호수의 쪽빛. 남미 묶음의 구리빛(안데스)과 콜롬비아의 진홍과 갈린다

## 4. 조건 — 비상업

Capabilities 의 AccessConstraints 는 `referencial`. GEOCATMIN 의 이용 허락(`geocatminapp.ingemmet.gob.pe/complementos/Descargas/Licencia.html`)은
INGEMMET 를 출처로 밝히면 쓰기·옮기기·2 차 저작을 허락한다. 메타데이터에는 **CC BY-NC-SA 4.0** 이 붙어 있다. 연구실 뷰어는 비상업이라
서버 판에는 싣고, **정적 판에는 싣지 않는다**(브라질·EOX 와 같은 자리). 출처 표기(`ingemmet.ATTRIBUTION`)에 조건을 적었다.

## 5. 3D·prewarm

3D 는 카탈로그 행의 `tiles` 를 256 px 원천으로 받는 길(187)에 `ingemmet` 를 더했다. 3D 의 남미 묶음에도 페루를 넣었다. prewarm 은 WMS 가
아니라 일본처럼 z/x/y 를 한 장씩 받는 `IngemmetPlan` 이다 — 캐시가 있는 줌까지만, 열쇠는 뷰와 같은 함수(`views.ingemmet_tile_key`).

## 6. 확인

- DB 사본에 마이그레이션(0024)·씨앗을 넣고 개발 서버로 열었다. 페루 탭이 서고, 나라 전체(줌 6)의 1:5만 타일 25 장이 모두 200 이었다.
  남미 묶음도 연다. 페이지 오류는 없었다
- 리마 남쪽을 누르면 1:5만은 "Kis-qui3 Grupo Casma - Formación Quilmaná · 백악기 · 93.9–113 Ma", 1:10만은 기호·이름·설명·도폭이 뜬다.
  리마 둘레 범례는 1:5만 55 칸, 1:10만 44 칸이 색과 함께 뜬다
- 시험 `test_ingemmet` — 속성 손질·시대 옮기기, 타일이 REST 의 `{z}/{y}/{x}` 로 가고 담기는지, 캐시 밖은 빈 타일, 캐시 줌 너머는 묻지 않음,
  누른 자리의 질의, 범례의 통계 질의·색·차례·캐시, 넓은 범위 거절, prewarm 의 줌과 열쇠
