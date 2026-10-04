# 남극의 다른 자료 — Bedmap3 를 올리고 나머지는 실측만

2026-10-05 · `feature/antarctica-more` · wetherilli

판 세션이 준 일 — SCAR ADD·ADMAP·BedMachine/Bedmap·BAS 지질처럼 열린 남극 자료를 실측하고, 쓸 만한 것을 남극 탭(3031)에. 마이그레이션 없이.

## 실측 (2026-10-05, 주소마다 한두 번, 2 초 간격)

| 자료 | 길 | 조건 | 한 것 |
|---|---|---|---|
| **Bedmap3** 빙저 지형·두께·윗면 (BAS, 2025) | ArcGIS Online 타일(TilesOnly, 3031 Esri 극 격자), CORS 되비춤 | CC BY 4.0(항목의 이용 조건) | **올림** |
| SCAR ADD (해안선·노두·빙퇴석·등고선) | ADD 뷰어가 BAS 의 ArcGIS Online 앱. 같은 것이 벡터 타일·피처 서비스로 있다 | — | 이미 있다 — 극지연구소 KPDC 기본도(노출암·등고선·호수·빙퇴석, 057)가 ADD 판이다 |
| SCAR 지명 사전(CGA) | BAS 의 피처 서비스, CORS | 항목에 조건 글 없음 | TODOs (사람) |
| BAS 암석 표본·코어 | 피처 서비스(표본 14 만 3 천, 해양 코어 966, 빙하 코어 84) | 조건 글 없음 | TODOs (사람) |
| ADMAP-2 자력 이상 | PANGAEA 의 grd 파일뿐 | CC BY 3.0 | 굽는 꼴 — 따로 했다(wetherilli 262) |
| BedMachine Antarctica | NSIDC — Earthdata 로그인 | — | 버림 — 열쇠 없이 받을 수 없다. Bedmap3 가 같은 자리를 메운다 |
| BAS 지질도 | — | — | GeoMAP(SCAR, 018)이 그것이다 |
| NASA GIBS 3031 | WMTS, CORS `*` | 공공 도메인 | 지질에 쓸 것이 없다 — SCAR 육지·물 가림과 해안선뿐 |
| 호주 AADC GeoServer | `data.aad.gov.au/geoserver` 가 자료 포털 첫 화면(HTML)을 준다 | — | 닿지 않는다 |

## Bedmap3 — 문을 거치지 않는 타일

BAS 가 Bedmap3 셋을 ArcGIS Online 에 **타일만**(TilesOnly) 올려 두었다. `export`·`identify` 가 없어 문으로 그릴 길이 없고, 앨버타
(`ags.py`, wetherilli 235)처럼 카탈로그 행의 `tiles` 를 화면이 곧장 받는 것이 맞다. 다른 점은 격자다 — 3031 이지만 **Esri 극 격자**
(원점 ±30 635 955 m, 줌 0 해상도 239 343 m)라 우리 3031 격자(GeoMAP·IBCSO)와도, Esri 남극 위성 배경(원점 ±33 699 551 m)과도 다르다.
행에 `grid`(원점·범위·해상도·첫 줌)를 실어 `esriGridSource` 하나로 받게 했다. 서비스의 `tileInfo` 를 화면이 묻지 않게 서버가 적어 준다.

- **캐시는 줌 4 부터다**(`minScale` 5 654 만 = 줌 0 의 1/16) — 줌 3 을 물으니 "Page Not Found" HTML 이 왔다. 격자에 `minZoom: 4` 를
  두어 그 밑은 줌 4 를 줄여 그린다. 남극 탭은 줌 1 로 열리지만 대륙이 줌 4 타일 네 장에 든다
- 줌 4 의 네 장을 이어 보아 극이 가운데·남극반도가 왼쪽 위에 서는 것을 확인했다(격자가 맞다)
- 범례는 REST `legend` 의 견본 조각 — 칸 이름 `-4,999.999999 - -4,000` 을 `-5,000 – -4,000 m` 로 다듬어 `list/legend/` 로 낸다
  (태국·말레이시아·캘리포니아의 길)
- 누른 자리는 없다 — 타일뿐이다. 같은 자리의 값은 2D 의 표고·IBCSO(047)가 갈음한다. 3D 에는 얹지 않았다(극지 3D 는 3031 을 펴서
  얹는데, 남의 Esri 격자를 펴는 길은 따로다)
- 배경이 아니라 레이어로 두었다 — 얼음 두께·윗면은 배경으로 쓸 그림이 아니고, IBCSO 와 견주어 켜고 끌 것이라서

## 버린 것

- **IBCSO 처럼 우리가 굽기** — 원본(GeoTIFF 500 m)을 받아 칠하면 색을 우리가 고를 수 있지만, BAS 가 이미 같은 자료를 칠해 열어 두었다.
  받은 것을 다시 내주지 않는다는 원칙과도 맞는다
- **Bedmap2 타일**(같은 계정의 `bedmap2_*_Clip`) — Bedmap3 가 그것을 대신한다
