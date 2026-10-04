# 오스트리아·폴란드 1:5만 — 가까이서만 그리는 레이어

2026-10-05 · `feature/europe-50k` · wetherilli

wetherilli 237 이 TODOs 에 남긴 "다음 판". 지역이 새로 생기지 않아 마이그레이션은 없다. 레이어는 기존 문(`geosphere.py`·`pig.py`)에 더했다 —
상류(기관)가 같다.

## 1. 오스트리아 — `einheiten_50`

- **WMS 가 꺼져 있다**(서비스에 WFSServer 뿐). 말레이시아(wetherilli 228)·캘리포니아(231)처럼 WMS 변수를 REST `export`·`identify` 로 옮긴다
- 바트 이슐 둘레 줌 13 한 장 1.4–1.8 초, 줌 9 는 3.3 초(153 KB)였다. 1:5만 판을 나라 줌에서 볼 까닭이 없어 **줌 11 부터**
- 속성은 GeoSciML-Lite 다 — 열 이름은 영어, 값은 독일어(`geologicUnitName` "Dachsteinkalk", `representativeAge` "Obertrias", `tectonicUnitName`
  "Oberostalpin", `collectionName` 도폭). 값이 없으면 "Unknown" 이 온다 — 뺀다
- **시대가 붙여 쓴 독일어다**(`Obertrias`·`Unterkreide`). `i18n.age_local` 이 앞머리 꾸밈말(ober·unter·mittel·früh·spät)을 떼어 읽게 했다.
  그래서 wetherilli 237 이 "모르면 원문" 의 보기로 든 `Mitteleozän` 도 이제 옮겨진다(에오세 중기)
- 범례는 두지 않는다 — 도폭마다 수백 칸이다. 누르면 단위가 뜬다

## 2. 폴란드 — `smgp50k`

- 같은 서버의 다른 서비스다. **WMS 번호가 여기서도 REST 와 거꾸로**다 — WMS `0` 이 단위(REST 5), `2`·`3` 이 경계·선 기호
- 1:9만 4 494 보다 넓으면 그리지 않는다 — **줌 13 부터**
- **디지털로 올린 도폭만 덮는다** — 자코파네(1060 도폭)는 있고, 바르샤바·크라쿠프는 줌 13·14 에서 비었다(2 233 B). 나라 전체를 덮는 판이 아니다
- 속성은 geo+json — `Wydzielenia`·`Geneza`·`Stratygrafia`("Holocen")·`Nr arkusza`(도폭)
- 범례는 WMS 그림(1:50만과 같은 길)

## 3. 버린 것

- 오스트리아 INSPIRE 메타데이터가 적은 GeoServer(`gis.geologie.ac.at/geoserver/ge_einheiten/wms`) — 열어 보지 않았다. REST 가 같은 자료를 준다
