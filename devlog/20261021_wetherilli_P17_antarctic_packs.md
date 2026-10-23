# 남극 오프라인 묶음 — 세종·장보고 기지 둘레 (계획)

2026-10-21 · `main`(계획) → 단계마다 `feature/gsmpack-polar-*` · wetherilli

P16(묶음 패키지)이 한국 묶음을 정리했다. 다음 묶음은 남극이다 — 극지연구소 현장 조사(세종·장보고 기지)에 망 없이 쓸 지질도.
국외 지질도는 뒤로 미뤘지만 극지는 예외다(사람, 2026-10-21). 앞의 일은 P13·381–385·P16(402–408)·409, 조건은 `docs/오프라인_묶음_조건.md`.

## 사람이 정한 것 (2026-10-21)

- **두 기지 다, 조사권역으로** — 세종(킹조지섬 바턴·위버 반도 둘레)과 장보고(테라노바만 둘레). 박스 표(`data/offline_boxes.json`)에 하나씩 둔다.
  아래 범위는 초안이고 사람이 고친다
- **배경은 고르게 한다** — REMA 지형 음영·기지 위성(VWorld 2013)을 굽는 쪽이 받을 수 있게 하고, 박스마다 무엇을 실을지는
  사람이 박스 표에서 고른다(사람: "선택하게 해줘"). Esri 남극 위성도 골랐지만 조건이 막는다 — 아래 "열어 둔 것". IBCSO 해저·빙저 지형은 줌 6 까지라 거칠어 고르지 않았다 — 값이 싸니 원하면 박스에 더한다
- **지질도는 GeoMAP** — 우리가 그리는 것(CC BY 4.0)이라 조건이 열려 있다. 누른 자리의 속성도 우리 파일에서 뽑는다 — 상류를 타지 않는다

## 지금 걸리는 것 (조사, 2026-10-21)

- **굽는 쪽이 3857 에 박혀 있다** — `gsmpack.grid`·`clip` 이 `lonlat_to_3857` 로 칸을 세고 자른다. 머리의 `grid` 는 늘 `EPSG:3857` 이라 적는다
- **화면의 남극 배경은 묶음을 읽지 않는다** — `offlineWrap` 을 거치는 것은 카탈로그 레이어(`layerSource`)와 VWorld(`vworldSource`)뿐이다.
  Esri(곧장, `services.arcgisonline.com` 의 극 타일)·REMA(PGC ImageServer 를 `TileArcGISRest` 로 곧장)는 감싸지 않는다
- **격자가 넷이다** — 열쇠는 화면 소스의 tileCoord 그대로라, 굽는 쪽이 레이어마다 화면과 같은 격자로 세야 한다

| 무엇 | 화면의 길 | 격자 |
|---|---|---|
| GeoMAP `geomap_*`(지질도 여섯) | `geomap/{레이어}/{z}/{x}/{y}.png` — 우리가 그리고 캐시에 담는다 | 3031 `GEOMAP_GRID`(±3333134.0276, 256 px) |
| REMA 음영 `rema*` | PGC ImageServer 를 곧장 — 캐시 없음 | 3031 `createXYZ` 512 px, 줌 16 까지 |
| Esri 남극 위성 | ArcGIS Online 극 타일을 곧장 — 캐시 없음 | Esri 극 격자(원점 −33699550.99, 256 px, 줌 13 까지) |
| 기지 위성 `AntarcticaSejong`·`Jangbogo` | VWorld 테마(문 `vworld.WMTS_THEMES`) — 이미 `offlineWrap` 을 거친다 | **3857** XYZ 256 px, 줌 10–18, 화면이 옮겨 그린다 |

- 화면의 묶음 읽기는 대부분 투영을 가리지 않는다 — `deeper`(늘려 그리기)는 쿼드트리 셈이고, 지층 면 찾기·"가 보기" 는 경위도다.
  다만 **머리의 `grid` 를 보지 않는다** — 256 px 격자가 셋(3031·Esri·3857)이라 `tile_size` 만으로는 못 가른다

## 짜임

### 패키지 — 격자를 꽂게 한다

- `gsmpack.grid` 에 **격자 꼴**을 둔다 — `tiles_for(bbox, z)`·`cell_extent(z, x, y)`·`project(lon, lat)`·`name`. 3857 은 지금 것 그대로,
  3031 은 `viewer/tilegrid.Grid` 의 셈(극 평사도법 `polar_forward`, 부채꼴 범위의 32 점 표본 `projected_bbox`)을 옮기고, Esri 극 격자는 원점·해상도를 받는다.
  소스가 제 격자를 들고(`src.grid`), 굽는 고리는 그것으로 세고 자른다
- **자르기는 투영 좌표에서** — 박스(경위도 네모)의 테두리를 격자의 투영으로 옮긴 다각형으로 칸 밖을 비운다. 3031 에서는 경위도 네모가 부채꼴이라 투영의 네모로 자르면 둘레가 샌다
- 머리의 `layers.<이름>.grid` 에 진짜 격자 이름을 적는다(`EPSG:3857`·`EPSG:3031`·`ESRI:antarctic`). **화면은 격자가 다르면 그 레이어를 건너뛴다**
  (지금은 `tile_size` 만 본다) — 옛 묶음은 다 `EPSG:3857` 이라 그대로 읽힌다. 꼴의 판(`GSMPACK1`)은 올리지 않는다 — 칸이 늘 뿐이다
- 한국 묶음의 동작은 바뀌지 않는다 — 1 단계의 확인이 그것이다(장성·진교를 다시 구워 머리·바이트가 같다)

### GSM 안의 소스 — 넷

- **GeoMAP** — 화면이 받는 `geomap_tile` 과 같은 그림(캐시 열쇠 `geomap_tile_key`)을 캐시에서 꺼내고, 없으면 우리가 그린다. 상류를 타지 않으니
  빠르기 규칙(1 초에 한 번)이 걸리지 않는다(`touched = False`, 407). 지층 면은 GeoMAP gpkg 의 R*Tree 에서 박스의 면을 뽑아 경위도로 옮긴다
  (`xy3031_to_lonlat`) — 레이어마다 스타일이 고르는 단위가 달라 레이어마다 한 덩이. 속성 손질은 `geomap.friendly` 그대로
- **기지 위성** — VWorld 테마는 이미 문이 안다(`get_wmts_tile`). `VWorldSource` 가 `WMTS_THEMES` 도 받게 하고, 격자는 3857, 열쇠는 화면의 z/x/y
- **REMA 음영** — PGC 로 나가는 문은 `elevation.py` 다. 화면이 부르는 ImageServer `exportImage`(`TileArcGISRest` 의 변수)를 그대로 받는 함수를 문에 더한다.
  서버가 PGC 를 부르는 것은 처음이 아니다(`pgc:antarctica_slope` 가 `/wms` 로 간다)
- ~~Esri 남극 위성~~ — 조건이 막는다(아래). 격자(`ESRI_ANTARCTIC`)만은 1 단계(410)에 들었다 — 화면이 Esri 칸을 엉뚱한 묶음에서 읽지 않게 가르는 데 쓴다
- 화면(`map.js`)은 REMA 배경 소스를 `offlineWrap` 으로 감싼다 — 묶음에 그 칸이 있으면 망을 타지 않는다

### 박스 — 초안

| 박스 | 범위(서, 남, 동, 북) | 레이어 |
|---|---|---|
| `sejong` | −59.05, −62.30, −58.55, −62.10 — 바턴·위버 반도와 필데스 반도 동쪽, 맥스웰만 | GeoMAP 지질도·REMA·기지 위성(줌 18 까지) |
| `jangbogo` | 163.6, −74.95, 165.2, −74.35 — 테라노바만, 멜버른 산 남쪽 기슭 | GeoMAP·REMA·기지 위성 |

- 남위 62° 에서 경도 0.5° 는 26 km, 남위 75° 에서 경도 1.6° 는 46 km 다. 예산 200 MB 를 넘으면 지금처럼 뒤의 레이어부터 줌이 덜린다 — 어림을 보고 범위를 줄인다
- GeoMAP 은 1:25만 남짓의 편찬이라 줌 13 까지면 넉넉하다 — 기지 위성만 줌 18 까지 둔다

## 단계

1. **패키지의 격자** (`feature/gsmpack-polar-grid`) — 격자 꼴·3031·Esri 극 격자·투영 자르기·머리의 `grid`·화면의 격자 검사. 한국 묶음을 다시 구워 머리·바이트가 같은지 본다 — **됐다(410)**
2. **GSM 안의 소스** (`feature/gsmpack-polar-sources`) — GeoMAP(그림·지층 면)·기지 위성·REMA 문, `map.js` 의 REMA 배경 감싸기. 휴대폰 시험에 남극 묶음 하나(망 없이 GeoMAP·누른 자리)
3. **박스와 시험 굽기** (`feature/offline-antarctic-boxes`) — 세종 먼저, 다음 장보고. 굽고 나서 크기·박스 밖 칸·지층 면을 보고 사람에게 범위를 묻는다
4. (뒤의 일) 화면에서 요청하기를 남극에도 — 408 의 요청 화면은 한국·0.3° 뿐이다. 남극 박스는 조사권역이 넓어 한 변 한계를 따로 정한다

## 열어 둔 것

- ~~Esri 남극 위성~~ — **조건을 읽었고 담을 수 없다(2026-10-21, 빼기로 했다).** 서비스 항목(`6553466517dd4d5e8b0c518b8d6b64cb`)의 조건은
  Esri Master License Agreement 이고, 요약(tou_summary.pdf, 2025-04-21)과 본문(E204, 2025-08-01)이 이렇게 적는다 —
  "The data may only be taken offline using Esri Content Packages … used exclusively with Esri software",
  "YOU MAY NOT … Systematically harvest basemap tiles through any method other than using Esri Content Packages",
  §3.2(c) "Customer may not otherwise scrape, download, or store Data". 서비스도 `exportTilesAllowed=false` 다.
  우리 묶음(`.gsmpack`)과 뷰어는 Esri 소프트웨어가 아니다. 그래서 Esri 소스·문은 짓지 않는다 — 배경은 REMA 음영과 기지 위성 둘이다.
  **화면이 지금 Esri 타일을 곧장 부르는 것도** 같은 조건(§3.2(a) "use Data with the Products for which Esri has provided the Data")에 걸릴 수 있다 —
  TODOs "비상업·이용 조건이 걸린 배경" 에 이미 있는 줄이다. 밖에 열기 전에 사람이 본다
- **기지 위성은 VWorld** — 약관 19 조 ⑥ 은 한국 묶음과 같은 처지다(TODOs "오프라인 지도")
- **극지연구소 KPDC 레이어**(기지·시료·운석 점) — 조건이 적혀 있지 않다(`LAB_ONLY`). 넣지 않았다. 사람이 KPDC 정책을 읽으면(TODOs) 점 레이어를 더한다
- **GNS 남빅토리아랜드 1:25만**(CC BY 3.0 NZ) — 장보고 남쪽(남위 76.4° 부터)이라 초안 박스 밖이다. 박스를 남쪽으로 넓히면 더한다
- **REMA 음영을 묶음에 담는 것** — 사람이 정했다(2026-10-22, "담아도 돼"). REMA 자료는 CC BY 4.0 이고, 그려 주는 PGC 서비스(img.arcgis.com 위)는 조건을 적지 않았다
