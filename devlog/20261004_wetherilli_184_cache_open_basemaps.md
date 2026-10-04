# 조건이 열린 배경을 서버 캐시에 — NASA GIBS·GEBCO

2026-10-04 · `feature/cache-open-basemaps` · wetherilli

브라우저가 곧장 부르던 배경 가운데 둘을 서버가 받아 담게 했다. 지역 탭의 GEBCO 해저 지형(`gebcoLayer`)과 극지 Blue Marble
(`gibsLayer`), 온 지구의 Blue Marble 셋(평면 WMTS·구 WMS)과 GEBCO 다. 화면은 `gibs/<투영>/<레이어>/<z>/<y>/<x>.jpeg`·`gibs/wms/`·
`gebco/wms/` 를 부르고, 서버가 같은 것을 상류에서 받아 `tilecache` 에 담는다.

## 왜 이 둘만인가 — 조건

- **GEBCO** — GEBCO Grid 는 공공 도메인이다. 출처(GEBCO Compilation Group, 판)만 밝히면 된다. 화면은 이미 출처를 단다(135)
- **NASA GIBS** — NASA 지구과학 자료는 쓰임에 제한을 두지 않고 출처 표기만 바란다. Blue Marble 도 NASA 의 것이다

판 세션이 이번에 맡긴 범위도 이 둘이었다. PGC 음영·NPI 타일·Trek 영상·EOX(비상업)·Esri 는 조건을 읽지 않았으므로 손대지 않고
TODOs 에 남겼다. 담는다는 것은 받은 것을 다시 내준다는 뜻이라, 조건을 모르는 채 옮기면 안 된다. VWorld 는 열쇠에 도메인 제한이 걸려
그대로 곧장 부른다(003·033).

## 곧장이 더 빠르지 않은가

2026-10-04 에 이 서버에서 한 장씩 쟀다 — GIBS 극지 WMTS 0.95 초, GEBCO 512 px 2.8 초. 서버를 거쳐도 처음 한 장은 그만큼 걸리지만,
두 번째부터는 캐시에서 1–11 ms 다. 곧장 닿는 길이 서버를 거치는 길보다 나은 것은 서버가 없는 정적 판뿐이다. 그래서 `map.js` 는
`STATIC` 일 때만 상류 주소를 그대로 둔다. 온 지구 화면은 정적 판에 없어 늘 서버로 간다.

## 문 하나에 둘 — `basemaps.py`

상류가 둘이니 문도 둘(`gibs.py`·`gebco.py`)로 갈 수 있었다. 하나로 묶은 것은 하는 일이 같아서다. 열쇠 없이 타일 한 장을 받아
그림인지만 보고, 받은 것을 그대로 담는다. 표고 상류 셋(AWS·국토지리원·PGC)을 `elevation.py` 하나에 묶은 것과 같은 까닭이다.
나중에 조건을 확인한 배경(PGC 음영·NPI 타일 따위)이 오면 여기에 더한다. 이름도 그래서 "조건이 열린 배경" 이다.

문은 **화면이 부르는 꼴만** 받는다. GIBS 는 화면이 쓰는 레이어 셋·투영 셋·줌 범위 안의 칸만, WMS 는 GetMap 이고 레이어가 표에 있고
변이 1024 px 이하인 것만 받는다. 그 밖은 404 다. 서버가 남의 WMS 를 아무 변수로나 부르는 길이 되지 않게 하려는 것이다.

## 브라우저가 부르던 주소와 같게

- WMTS 는 경로를 그대로 옮긴다 — `…/wmts/epsg<투영>/best/<레이어>/default/500m/<z>/<y>/<x>.jpeg`. 열쇠도 그 경로다(`views.gibs_tile_key`)
- WMS 는 브라우저가 보낸 변수를 `kigam.clean_params` 로 거른 그대로 넘긴다. 이름만 소문자가 되는데, WMS 는 변수 이름의 대소문자를
  가리지 않는다. 열쇠는 KIGAM 타일과 같은 `tilecache.key_for` 이고, 갈래를 `gibs`·`gebco` 로 갈랐다

화면의 격자·변수는 바꾸지 않았다. 주소의 앞만 바꿨으므로 OpenLayers·Cesium 이 짓는 BBOX 는 앞 판과 같다.

## 확인

- 이 서버에서 runserver 로 세 길을 한 번씩 받았다 — 처음은 상류에서(0.9–2.8 초), 두 번째는 캐시에서(`X-GSM-Cache: hit`)
- 머리 없는 브라우저로 한국 탭(GEBCO)·그린란드 탭(GIBS 3413)·온 지구(GIBS 4326 WMTS, GEBCO 4326 WMS)를 열었다. 배경 타일 50 장이
  모두 서버를 거쳐 200 이었고, 상류로 곧장 나간 요청은 없었으며, 페이지 오류도 없었다. 남극 탭은 이 기계에 GeoMAP 이 없어 지도가 서지
  않아 보지 못했다 — 같은 `gibsLayer` 를 그린란드가 탄다
- 시험(`test_basemaps`)은 상류를 갈아 끼워 주소·변수·담기·거절을 본다

## 하지 않은 것

- `prewarm` 에 GIBS·GEBCO 를 더하지 않았다. 배경은 줌이 낮아(GIBS 극지 4·4326 8, GEBCO 9) 사람이 한 번 훑으면 거의 다 담긴다
- 3D(`map3d.js`)의 배경은 이번 길과 상관이 없다 — GIBS·GEBCO 를 부르지 않는다
