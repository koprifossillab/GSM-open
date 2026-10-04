# 멕시코 — SGM 1:25만·1:5만, WMS 가 막혀 문이 REST export 로 옮긴다

2026-10-04 · `feature/mexico` · wetherilli

미국(205)에 이은 북미의 둘째 몫이다. 후보와 첫 실측은 [docs/다른_대륙_지질도.md](../docs/다른_대륙_지질도.md) 의 "멕시코" 절이다.

## 1. 쟀다 (2026-10-04)

- 서비스 `portal.sgm.gob.mx/arcgis/rest/services/SGM/SUNGeologiaContinuoMineDatosEs/MapServer` — 레이어 아홉 가운데 지질은 `8` 암상 1:25만
  (전국)·`7` 암상 1:5만(광업 지구, minScale 75만)·`6` 구조 1:25만·`5` 구조 1:5만(minScale 200만). 타일 캐시가 없는 동적 서비스다
- export 3857 512² 가 나라 전체(줌 5) 5.9 초, 사카테카스 둘레(줌 9) 1.3 초
- identify 는 1.1 초, 열을 **별칭**(Clave·Litología·Roca·Formación·Era·Periodo·Edad inicial·Edad final·Tipo de unidad)으로 준다.
  빈 값이 "Indeterminado"·"No aplicable" 로 온다
- 칠하기 규칙은 `CLAVE_SGM` 값마다 색 하나(887 칸), 통계 질의가 된다 — 사카테카스 둘레 1:25만이 14 칸
- **WMSServer 는 400** — WMS 를 열어 두지 않았다

## 2. 문 — `sgm.py`, 화면에는 WMS 와 같게

WMS 가 없다고 화면에 새 소스를 짓지 않았다. 화면은 다른 상류처럼 `wms/` 에 3857 WMS 변수를 보내고, **문이 그 변수를 REST `export` 로
옮긴다**(PGC 경사가 이미 그렇게 한다, 099). 속성도 `/featureinfo/` 로 오는 WMS 변수(범위·크기·I·J)를 3857 의 한 점으로 셈해 `identify` 로
묻는다. 그래서 map.js 는 `sgm: { source: npolarSource, info: wmsInfoUrl }` 한 줄이고, 캐시·prewarm·3D 가 WMS 상류와 같은 길을 탄다.

범례는 페루(195)·에콰도르(198)와 같은 보는 범위의 범례다(`sgm/legend/`) — 범위 안의 단위는 통계 질의, 색은 칠하기 규칙(30 일 담음).
REST 범례는 1.3 MB(1:5만 2 571 칸·1:25만 888 칸)라 쓰지 않는다. 구조선 레이어는 범례·누르기가 없다.

## 3. 에스파냐어 시대 — 표를 `i18n` 으로 옮겼다

페루의 문(`ingemmet.AGES_ES`)에 있던 에스파냐어 → ICS 영문 표를 `i18n.age_es` 로 옮겨 둘이 함께 쓴다. 멕시코는 절(Age) 이름도 준다
(`Valanginiano`·`Hauteriviano`) — 거의 다 `-iano` → `-ian` 이라 표 없이 규칙으로 옮긴다. `Terciario` 를 표에 더했다(`age_ko` 가 제3기로 옮긴다).
팝업의 지질시대는 "기 · 절~절" 로 잇는다(예: 제3기 · 팔레오세~에오세).

## 4. 지역·조건

나라 탭 `mexico`(마이그레이션 0028 — 미국의 0027 뒤라 이 가지는 `feature/usa-mexico` 위에 섰다). 3857. 빛깔은 로사 메히카노를 오악사카
흑도기 바탕에. 3D 허용 목록·prewarm(`PROJECTED`)에도 더했다. 북미 묶음은 캐나다가 들어오면 미국과 함께 세운다.

조건 — datos.gob.mx 의 1:25만 지질도가 **CC BY 4.0**, 서비스 저작권 "© SGM". 열린 조건이지만 이번 범위는 서버 판이고, 정적 판에 실으려면
브라우저가 export·identify 를 곧장 부르는 소스가 따로 있어야 해서 하지 않았다.

## 5. 확인

- DB 사본으로 멕시코 탭을 열었다 — 타일 200, 페이지 오류 없음. 사카테카스를 누르면 "Qhoal · Aluvial · Sedimentaria · 제4기 · 홀로세",
  범례는 14 칸이 색·지층·시대와 함께 뜬다
- 시험 `test_sgm` — 별칭 열 손질, 절 이름 규칙, export·identify 로 옮기기(누른 자리의 셈), 범례의 차례·색
