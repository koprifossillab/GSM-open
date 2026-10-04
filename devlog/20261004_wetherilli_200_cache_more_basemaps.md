# 남은 배경의 조건을 읽었다 — NPI 타일만 서버 캐시로

2026-10-04 · `feature/cache-more-basemaps` · wetherilli

TODOs "캐시·미리 받기" 의 줄 — 브라우저가 곧장 받는 배경 가운데 조건이 허락하는 것을 서버에 담는다. GIBS·GEBCO 는 184 로 섰다.
남은 셋(PGC 음영·NPI 타일·Trek 영상)의 조건을 2026-10-04 에 읽었다. **서버에 담아 다시 내주는 것이 분명히 허락되는 것만** 옮긴다.

## 1. 읽은 것

| 배경 | 근거 | 판단 |
|---|---|---|
| **NPI 스발바르 지형도·위성 모자이크** (`geodata.npolar.no/…/Basisdata/NP_Basiskart_Svalbard_WMTS_25833`·`NP_Satellitt_Svalbard_WMTS_25833`) | 두 서비스의 `f=json`: `copyrightText` "Norsk Polarinstitutt"(위성은 "… Copernicus Sentinel data"), 설명 "Lisensiert/licensed under CC BY 4.0"·"Licensed under CC BY 4.0" | **옮긴다** — CC BY 4.0 은 다시 내주는 것을 허락한다. 출처는 화면이 이미 단다 |
| **PGC 음영** (`di-pgc.img.arcgis.com/…/arcticdem_latest`·`rema_latest/ImageServer`, `Hillshade Gray` 따위) | 서비스 `f=json` 의 `copyrightText`·설명·`licenseInfo` 가 모두 비었다. PGC 의 ArcticDEM 쪽과 감사 표기 정책은 "Acknowledgement Policy 를 따른다" 만 적고 라이선스 이름이 없다. AWS 공개 자료 목록(`registry.opendata.aws/pgc-arcticdem`)은 ArcticDEM 자료를 "CC BY 4.0" 이라 적는다 | **두다** — 자료(DEM)는 CC BY 4.0 이지만, 우리가 받는 것은 Esri 가 올려 둔 PGC 의 영상 서비스가 그때그때 그린 음영이다. 그 서비스의 이용 조건이 적혀 있지 않다 |
| **NASA Trek 영상** (달 LRO WAC·Kaguya TC·LOLA, 화성 Viking·THEMIS·MOLA·MOLA–HRSC, 수성 MESSENGER MDIS·USGS DEM 음영) | Trek 의 안내(`trek.nasa.gov/moon/jpl/config/textAbout.html`)에 조건이 없다. "Trek 자료는 등록 없이 누구나 쓴다" 는 소개 글뿐이다. LROC 의 저작권 안내(`lunaserv.im-ldi.com/copyright_info.html`)는 출처 "NASA/GSFC/Arizona State University" 만 요구하고 다시 내주는 것을 말하지 않는다. 배경에 **JAXA**(Kaguya TC)·**ESA/DLR/FU Berlin**(HRSC) 자료가 섞였다 | **두다** — NASA 단독 자료는 대개 미국에서 저작권이 없지만, Trek 이 적어 둔 것이 없고 JAXA·ESA 자료는 그쪽 조건을 따른다. 배경마다 갈라 고르는 일은 사람이 정한다 |

EOX(비상업)·Esri·VWorld 는 판 세션의 말대로 그대로 곧장 부른다.

애매한 둘은 TODOs 의 (사람) 줄과 이슈 #153 에 한 줄씩 남겼다. 길은 둘이다 — PGC 에 영상 서비스 결과를 담아도 되는지 묻거나, Trek 에서
NASA 단독 배경(LOLA·Viking·THEMIS·MOLA·MESSENGER)만 골라 옮긴다.

## 2. NPI 타일을 서버 길로

184 의 GIBS 와 같은 틀이다(`basemaps.npi_tile`, `views.npi_tile`, `npi/<서비스>/<z>/<y>/<x>`).

- 받는 것은 브라우저가 부르던 주소 그대로 — `…/MapServer/tile/z/y/x`. 열쇠는 `npi-tile/<서비스>/<z>/<y>/<x>`
- 문은 화면이 쓰는 서비스 둘(`NPI_SERVICES`)과 줌 0–17 만 받는다. `Basisdata_Intern/*` 은 "Svalbardkartet 안에서만" 이라 부르지 않는다(P01)
- 정적 판은 서버가 없어 곧장 부르는 길을 남겼다(`map.js` 의 `STATIC ?`)
- 극지 NPI **지질도**(npolar.py, 021)는 원래 서버 문을 거쳐 담겨 왔다. 이번 것은 **배경**이다

## 3. 확인

- 시험(`test_basemaps.Npi`) — 브라우저가 부르던 주소로 받고 두 번째는 캐시, 모르는 서비스·줌은 묻지 않는다, 화면은 서버를 거치고 정적 판만 곧장. 전체 시험 통과
- 개발 서버로 스발바르 탭(롱위에아르뷔엔, 줌 8)을 지형도·위성 배경으로 열었다 — 배경 타일 44 장이 모두 서버를 거쳐 200 이었고, 상류로 곧장 나간 요청은 없었다

## 운영

없음.
