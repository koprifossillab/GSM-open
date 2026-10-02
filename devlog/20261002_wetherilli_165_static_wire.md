# 정적 판에 구운 것 잇기 — 남극·얀마옌·극지의 점이 서버 없이

2026-10-02 · `feature/static-wire` · wetherilli

정적 판 뼈대(wetherilli 162, #138) 위에 구운 것(`bake_static`, 160)을 잇는다. 이 몫만으로 **남극(GeoMAP·IBCSO 자료 출처·NPI 시료·
극지연구소)과 얀마옌, 그린란드·스발바르·북극해의 점 레이어**가 서버 없이 선다. 브라우저가 곧장 부르는 극지 상류(GEUS·NPI 지도
서버·PGC·EMODnet·KPDC WMS)는 gsm-85 의 `static-kinds.js` 몫이다.

## 화면에 알리는 법 — `static-config` 의 `baked`

- `static_site.py --baked <폴더>` 가 그 폴더의 `manifest.json` 을 읽어 `baked` 를 싣는다 — GeoMAP 레이어마다 마지막 줌, 점 레이어마다
  영어판이 따로 있나, IBCSO 가 있나. 9 만 줄의 파일 목록은 싣지 않는다(화면은 몰라도 된다)
- `--baked` 가 있으면 극지 다섯(남극·그린란드·스발바르·얀마옌·북극해)을 지역에 더하고, 상류 `geomap`·`ibcso` 를 켠다

## 점 레이어는 상류가 아니라 이름으로

- NPI 와 극지연구소는 한 상류에 **서버를 타는 지도 레이어와 구운 점 레이어가 섞여 있다**. 상류를 통째로 켜면 서버가 없어 깨지는
  레이어가 목록에 선다. 그래서 `views._static_catalog` 가 `baked.points` 의 이름도 받는다
- 주소 — `points/?layer=a:b&lang=` 을 `points/a/b.json`(영어이고 따로 구운 것은 `.en.json`)으로 (`map.js` 의 `pointsUrl`)

## GeoMAP·IBCSO

- 소스의 해상도 표를 구운 줌까지만 짓는다 — 그 너머는 OpenLayers 가 마지막 줌의 타일을 늘린다. 지도 줌 17 까지 들어가도 줌 9 타일만
  묻는 것을 보았다. 굽지 않은 타일(자료 밖)은 404 라 빈칸이다
- 속성은 묻지 않는다 — 서버가 gpkg·원본 격자에서 읽던 것이라. GeoMAP 의 클릭 속성은 정적 판에서 빠진다. 벡터 타일로 굽는 길(검토 §7)이
  열리면 돌아온다. 같은 까닭으로 IBCSO 수심 읽기(`ibcso/depth`)도 정적 판에서는 묻지 않는다
- 범례는 구운 그림 `legend/geomap/<레이어>.png`

## 확인

- `static_site.py` 로 구워(340 MB, 13 초) `python -m http.server` 로 `/GSM-open/` 꼴을 띄워 헤드리스 Chromium 으로 보았다 — 남극에
  GeoMAP·NPI 시료·극지연구소 암석 시료, 얀마옌 지질 단위·선과 범례, GeoMAP 범례, 깊은 줌
- 정적 판은 아직 한국어 한 장으로 굽는다 — 영어판의 `.en.json` 은 뼈대가 영어 쪽을 구울 때 쓰인다
- 극지의 지명 찾기(`placenames/`)는 서버의 것이라 정적 판에서 돌지 않는다. 구운 지명(`points/npolar/place_names.json` 등)을 화면이
  뒤지게 하는 것은 찾기 칸을 만지는 쪽(gsm-57)과 맞춰 다음에
