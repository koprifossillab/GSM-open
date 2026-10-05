# 3D 에 남극 IBCSO 자료 출처·ADMAP, 북유럽 NGU·GTK

2026-10-05 · `feature/3d-more` · wetherilli

새 일거리 둘째 판(wetherilli 330)의 5번. 3D(MapLibre)는 3857 타일만 얹는다.

## 남극 — 서버가 3031 을 3857 로 편다

GeoMAP 은 이미 `warp/geomap/` 으로 3D 에 선다(040). **IBCSO 자료 출처(TID, 071)와 ADMAP-2 자력 이상(wetherilli 262)도 우리가 GeoMAP 격자(3031, 256 px)로 잘라 둔 판**이라
같은 길에 얹었다 — `warp.polar_grid` 하나(격자는 GeoMAP 의 것, 읽기는 각자의 파일). IBCSO 의 해저·빙저 지형(bed·ice)은 원본 9354 격자라 따로다(051).

- 주소 `warp/admap/anomaly/…`·`warp/ibcso/tid/…`, 줌 2–17, 남위 60°(ADMAP)·50°(TID) 북쪽은 빈 타일
- **편 것은 캐시에 담고 열쇠에 원본의 판을 넣는다** — 잘라 둔 폴더의 때(`_dir_version`). 펴는 법(`warp.py`)은 고치지 않아 `WARP_RENDERER` 는 그대로다
- 3D 의 목록(`map3d_view`)과 `map3d.js` 의 소스에 한 갈래씩
- 운영 파일로(읽기만) 펴 보니 줌 3 의 512 px 한 장이 ADMAP 0.7 초·TID 0.4 초, 남극반도의 자력 이상이 제자리에 선다

## 북유럽 — 3857 도 그린다

노르웨이 NGU(2D 는 3575)·핀란드 GTK(2D 는 3413)는 3D 목록에서 "극지 투영으로만 받는다" 로 빠져 있었다. 두 문이 WMS 1.1.1 의 `srs` 를 그대로 넘기므로 3857 로 한 장씩 물었다 —
NGU 국가·지역 기반암·자력 이상, GTK 기반암·공중 자력 모두 그림(1.5–2.8 초), FODD 광상은 점이라 성기다. `MAP3D_WMS` 에 둘을 더했다.

## 버린 것

- PGC(ArcticDEM·REMA 경사·등고선)·극지연구소 KPDC 지도 서버 — 3031·3413 로만 받는 것이라 이번에는 재지 않았다. 다음에 같은 꼴로 재 본다
