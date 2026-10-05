# 노르웨이 — NGU 광물·지구물리

2026-10-05 · `feature/ngu-resources` · wetherilli

판 세션이 준 일(gsm-91 의 정리 목록 4번) — NGU 지도 화면이 부르는 주소를 읽어 광물 산지·자력·중력 같은 열린 서비스를 찾고 노르웨이·스웨덴·핀란드 탭에.
조건을 상류 조건표에도. 270 이 "NGU 의 광물·지구물리 서비스 주소를 못 찾았다(`geo.ngu.no/mapserver/*` 이름 짐작은 404)" 고 남긴 줄이다.

## 찾기 — 짐작하지 않고 읽었다

- **Geonorge**(노르웨이 국가 목록) 검색 — NGU 의 광물 셋(`MetallerWMS2`·`IndustrimineralerWMS3`·`NatursteinWMS3`)은 나오지만 지구물리는 없다
- **NGU 지도 화면**(`geo.ngu.no/kart/geofysikk_mobil/`)의 묶음 스크립트(500 KB)에 서비스 이름 표가 통째로 든다 — `GeofysikkWMS4`·`KritiskeMineralerWMS`
  를 비롯해 쉰 남짓. 270 의 짐작이 빗나간 것은 판 번호(`…WMS4`)를 몰라서였다

## 고른 것 (노르웨이 광물·노르웨이 지구물리, 레이어 여덟)

| 서비스 | 레이어 | 투영 | 누르기 |
|---|---|---|---|
| `MetallerWMS2` | 금속 광물 산지(`Punkt_Metaller`)·금속 광물 지대(`Provins`) | 3857 | 이름·광종(영문)·갈래·자원 중요도·등록 갈래 / 지대 이름·광종 |
| `IndustrimineralerWMS3` | 산업 광물 산지·지대 | 3857 | 금속과 같은 열 |
| `KritiskeMineralerWMS` | 핵심 금속(금속 갈래) | 3857 | 하지 않는다 — `text/plain` 이 비어 온다(HTML 틀에만 값) |
| `GeofysikkWMS4` | 자력·중력 이상 편찬, 평균 밀도(Olesen 외 2010) | 3575 | 하지 않는다 — 격자 칸에 값이 없다 |

- **광물 서비스는 3575 를 받지 않는다**(Capabilities 에 없다, 기반암·지구물리는 받는다) — 3857 로 받고 화면이 3413 에 옮겨 그린다. 북위 70° 의 부풂은 점·지대라
  축척 따라 켜고 끄는 판이 없어 문제되지 않는다
- 이름은 기반암처럼 `ngu:` + 상류 이름이 아니라 짧은 이름(`ngu:metals`)으로 두고 문의 `OTHER` 가 서비스·상류 레이어·투영을 안다 — 상류 이름이 서비스마다
  겹친다(`Provins` 가 금속·산업 둘에)
- 값(노르웨이어 `internasjonalBetydning`·`forekomst`)은 옮기지 않는다. 광종은 상류가 영문을 함께 주어 그것을 쓴다

## 조건

NGU 자료 정책 — NLOD 2.0(wetherilli 140). 광물·지구물리 Capabilities 도 Fees "none"·"no conditions apply", AccessConstraints 는 저작권 표시뿐이다.
상류 조건표의 `ngu` 줄에 서비스와 근거를 더했다.

## 두지 않은 것

- 자연석(`NatursteinWMS3`)·골재(`GrusPukkWMS5`)·광물 시추 코어 — 지질보다 건설 자재·보관 목록에 가깝다
- 공중·지상 지구물리 조사 범위(`Airborne_geophysics_*`·`Ground_*`) — 조사한 곳의 테두리일 뿐이다
