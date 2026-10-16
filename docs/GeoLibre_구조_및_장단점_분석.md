# GeoLibre 구조 및 장단점 분석 — GSM 과 견주고, 들일 것을 고른다

2026-10-13 · koprifossillab · 검토 (계획이 아니다)

[GeoLibre](https://github.com/opengeos/GeoLibre)(v3.4.0, MIT)의 구조를 읽고 GSM 과 견준다. 장단점을 따지고,
GSM 의 원칙을 건드리지 않고 들일 수 있는 것을 고른다. 정해지면 그때 단계마다 P 문서와 devlog 를 쓴다.
수치는 2026-10-13 의 두 저장소(`~/projects/GeoLibre` `70bbe208`, `~/projects/GSM` `main`)에서 쟀다.

## 1. 한 줄

**GeoLibre 는 클라이언트가 두껍고, GSM 은 서버가 두껍다.** GeoLibre 는 아무 자료나 브라우저 안에서 열고
연산하는 범용 GIS 작업대이고, GSM 은 상류 여든 남짓 앞에 서서 키를 감추고 타일을 중계·캐시하는 지질도
뷰어다. 둘은 겨루지 않고 서로를 메운다. **GSM 이 들일 것은 React 가 아니라 브라우저 쪽 능력(반입·분석)과
"상태 하나 → 화면 동기화" 의 규율이다.**

## 2. GeoLibre 는 어떻게 생겼나

### 2.1 개요

오픈소스 클라우드 네이티브 GIS. 핵심 원칙은 **"자료는 사용자 기기에 머문다"** 이다 — 지오프로세싱 도구
1,000 개 넘게가 WebAssembly 로 브라우저 안에서 돌고, 서버를 묻지 않는다.

한 React 앱이 여러 꼴로 나간다.

| 꼴 | 기술·배포처 |
|---|---|
| 데스크톱 | Tauri v2 (Windows·macOS·Linux, MS Store, Mac App Store, AUR, Flatpak) |
| 모바일 | Tauri Android·iOS (Google Play, App Store) |
| 웹 | nginx Docker (web.geolibre.app) |
| Jupyter | `geolibre` 파이썬 패키지 (anywidget, PyPI·conda-forge) |
| 그 밖 | R 패키지, Chrome 확장, MCP 서버 |

### 2.2 규모

- TypeScript·TSX 약 **78만 줄**, 파이썬 약 6.8만 줄, Rust 약 1.4만 줄
- 프런트엔드 시험 파일 약 850 개, 번역 로케일 21 개, GitHub Actions 워크플로 26 개
- 커밋 1,973 개 — 2026-05-27 에 시작했고, 최근 30 일에 548 개

### 2.3 저장소 구조 (npm workspaces 모노레포)

```
apps/
  geolibre-desktop   (1,151 파일) 셸 UI·Tauri 입출력·조합. src-tauri/ 에 Rust 크레이트
  geolibre-mcp-app   MCP 앱 빌드
packages/
  core        Zustand 스토어·도메인 타입·.geolibre.json 프로젝트 스키마  ← 단일 진실 원천
  map         (146) MapLibre 수명주기와 레이어 동기화
  plugins     (304) 플러그인 인터페이스와 내장 플러그인 약 200 개
  processing  클라이언트 쪽 알고리즘 레지스트리
  ui          shadcn 꼴 UI 부품
  embed       iframe 임베드 클라이언트
  collab-core 실시간 협업 공통 로직
workers/      Cloudflare Workers — viewer(공유)·collab·tiles·ai-proxy·collab-node
backend/
  geolibre_server      FastAPI 사이드카 (127.0.0.1:8765, 없어도 된다)
  geolibre_server_api  다중 사용자 서버 API 참조 구현 (SQLite·Postgres, S3)
python/       Jupyter 위젯과 MCP 서버
extensions/   Chrome 확장
```

### 2.4 자료의 흐름 — 스토어 하나, 한 방향

1. 자료가 들어온다 — 메뉴, Tauri 대화상자, 파일 고르기, 끌어다 놓기, 플러그인
2. MapLibre 가 바로 못 그리는 벡터는 브라우저 안의 **DuckDB-WASM Spatial**(`ST_Read`)이 GeoJSON 으로
   옮긴다. Shapefile 은 `shpjs` 로 읽고, 안 되면 DuckDB 로 넘긴다
3. 타일·래스터·ArcGIS·MBTiles 따위는 `GeoLibreLayer` 레코드가 되어 스토어에 든다
4. `MapController.syncLayers` 가 스토어를 MapLibre 의 소스·레이어에 맞춘다. **UI 는 MapLibre 를 직접
   건드리지 않는다** — 스토어를 바꾸면 동기화가 따라온다

지도 엔진은 넷이다 — MapLibre(기본)·Mapbox GL·CesiumJS·ArcGIS Maps SDK. 갈아 끼우거나 나란히 동기화해
띄운다. 래스터·포인트 클라우드·3D 는 deck.gl 이 얹는다.

파이썬 사이드카는 **없어도 돈다.** Whitebox 도구, 포맷 변환, rasterio 래스터 도구만 맡는다. 벡터 도구는
Turf.js 로 브라우저에서 돌고, 사이드카에 `vector` 묶음이 깔려 있을 때만 GeoPandas·Shapely 로 간다.

### 2.5 품질 장치

- `npm run ci` 하나가 lint·빌드·프런트/워커/백엔드 시험·`cargo check` 를 다 돈다
- **래칫** — 커버리지 하한(백엔드 55%), 시험 타입 오류 0, ESLint 경고 상한 242. 수치를 내리지 못하게 막는다
- 생성 파일(i18n 도구 카탈로그·갤러리·플러그인 문서)이 원본과 맞는지 CI 가 본다
- Playwright E2E(core·features·SSO·preview)
- CSP 의 `script-src` 를 jsDelivr 판 경로로 박아 두고 시험이 그것을 다시 따진다

## 3. GSM 과 견주기

| 항목 | GeoLibre | GSM |
|---|---|---|
| 목적 | 아무 자료나 열고 분석하는 범용 GIS | 나라마다의 지질도를 겹쳐 보고 속성을 읽는다 |
| 무게중심 | 클라이언트 (WASM·DuckDB·Turf) | 서버 (Django 의 "문") |
| 서버가 하는 일 | 없어도 되는 사이드카 — 무거운 처리만 | 반드시 있다 — 키 감추기·중계·타일 캐시·데이터소스 받기 |
| 프런트엔드 | React + TypeScript, Zustand, Vite 빌드 | 빌드 없는 JS 파일 (`map.js` 8,233 줄) |
| 지도 엔진 | MapLibre(기본)·Mapbox·Cesium·ArcGIS 갈아 끼우기 | OpenLayers 가 중심, MapLibre·Cesium 을 vendor 로 |
| 상태의 원천 | Zustand 스토어 + `.geolibre.json` | Django 모델(DB) + 브라우저 IndexedDB(개인 레이어) |
| 저장소 | 모노레포 (앱 2·패키지 7·워커 5) | 앱 하나 (`viewer/`) — "앱을 더 가르지 않는다" |
| 늘리는 방식 | 플러그인 API — 내장 약 200·외부 zip | 상류마다 파이썬 모듈 하나 (문 77 개) |
| 배포 | 데스크톱·모바일·웹·Jupyter·R·Chrome 확장 | Docker(연구소 안) + GitHub Pages 정적 판(밖) |
| 규모 | TS 약 78만·Py 약 6.8만·Rust 약 1.4만 줄 | Py 약 8.8만·JS 약 4.8만 줄 |
| 이력 | 2026-05-27 부터 커밋 1,973 | 2026-09-23 부터 커밋 1,446 (석 주) |
| 라이선스 | MIT | AGPL-3.0 (공개 사본 `GSM-open`) |
| 문서 | 영어 `docs/` 40 편 넘게, 래칫 CI | 한국어 `CLAUDE.md`(93 KB)·devlog 447 편·말을 고르는 규칙 |

### 3.1 가장 크게 다른 세 자리

**바깥을 부르는 방식.** GeoLibre 는 브라우저가 타일·서비스를 곧장 부른다(CSP `connect-src` 가 `https:`
전부를 연다). GSM 은 **상류마다 문이 하나** — 그 일흔일곱 밖에서는 `requests` 를 쓰지 않고, 키는 서버에서만
붙이고, 로그에서는 `redact()` 가 지운다. 상류가 바뀌어도 고칠 자리가 하나다.

**자료의 층.** GeoLibre 의 `GeoLibreLayer` 는 무엇이든 담는 한 틀이다(GeoJSON·래스터·3D Tiles·포인트
클라우드). GSM 은 **출처에 따라 갈라 섞지 않는다** — 상류가 주는 `LayerGroup`·`Layer`(사람은 한글 제목만
손질), 내가 올린 `PointSet`·`Point`·`Shape`, 받아 두는 `DataSource`·`FetchRun`.

**무거운 일을 누가 하나.** GeoLibre 는 공간 연산을 브라우저에서 하고 GDAL 계열만 사이드카로 넘긴다.
GSM 은 **공간 연산 라이브러리를 일부러 두지 않는다** — GDAL·shapely·geopandas 가 없어 web 이미지가 200 MB
대다. 남극 GeoMAP 은 sqlite3·struct·Pillow 로 그리고, 바람·해류는 호스트 전용 venv 가 PNG 로 구워 둔다.

## 4. 장단점

### 4.1 GeoLibre

**좋은 점**

- **서버 없이 돈다.** 자료가 기기를 떠나지 않는다 — 오프라인·보안망·민감 자료에 맞고 운영비가 거의 없다
- **코드 하나로 예닐곱 꼴을 낸다** — 웹·데스크톱·모바일·Jupyter·R·Chrome 확장
- **범용성과 분석력** — 도구 1,000 개 넘게, 포맷 대부분, 엔진 넷
- **아키텍처의 규율** — 스토어가 단일 진실 원천, 동기화가 한 방향, 패키지 경계가 분명하고 타입이 지킨다
- **품질 장치** — 래칫 커버리지·타입 기준선, E2E, CSP 시험
- **플러그인 생태계** — 바깥 사람이 코어를 건드리지 않고 기능을 더한다

**아쉬운 점**

- **크고 무겁다** — TS 약 78만 줄, 의존성 수백. 빌드가 느리고 WASM 자산이 커서 첫 로딩이 무겁다(자산 크기
  제한이 있는 호스트를 위해 `lite:build` 를 따로 둘 정도다)
- **바꾼 것이 어디까지 번지는지 보기 어렵다** — 하나를 고쳐도 일곱 배포처를 봐야 하고, Tauri·Android·iOS·
  MAS 가 저마다 함정을 갖는다
- **상류가 내보내지 않는 것을 손으로 베껴 두었다** — maplibre 따위를 올릴 때 소리 없이 깨질 수 있다
- **키를 감출 자리가 없다** — 키가 필요한 서비스는 쓰는 사람이 제 키를 넣어야 한다
- **공용 캐시가 없다** — 같은 타일을 사람마다 상류에서 따로 받는다
- **분야의 깊이는 얕다** — 지질도 같은 분야의 레이어 큐레이션·속성 풀이가 기본으로 없다

### 4.2 GSM

**좋은 점**

- **분야에 깊다** — 상류 여든 남짓을 골라 카탈로그로 두었다. 상류 문서의 오류를 `GetCapabilities` 와
  대조해 잡았고, 지질시대를 ICS 이름으로 옮기고, 지역마다 맞는 투영(북극 3413·남극 3031·북미 3978)을 쓴다
- **인증키를 지킨다** — 서버가 키를 붙이고 로그에서 지운다. 키가 없어도 뷰어는 돈다
- **공유 타일 캐시** — 한 번 받은 타일을 모두가 다시 쓴다. 빠르고, 상류의 이용제한을 지키기 좋다
- **단순하고 가볍다** — Django 앱 하나, 빌드 없는 JS, 200 MB 대 이미지. GDAL 을 뺀 덕에 의존성·보안 부담이 적다
- **상류마다 문 하나** — 주소가 바뀌거나 닫혀도 고칠 자리가 하나다
- **"왜" 가 남는다** — devlog 447 편과 말을 고르는 규칙이 결정의 까닭을 쫓게 해 준다

**아쉬운 점**

- **서버에 기댄다** — 밖의 정적 판에는 점묶음 올리기·3D·달·화성·KIGAM 속성이 빠진다
- **프런트엔드가 늘기 어렵다** — `map.js` 한 파일이 8,233 줄이고 모듈·타입이 없다(`import`·`export` 가 한 줄).
  `earth`·`moon`·`mars`·`mercury` 가 2,700–4,700 줄씩 서로 겹친다. 기능이 늘수록 회귀 위험이 커진다
- **분석이 없다** — 공간 연산을 뺀 것은 좋은 점이지만, 그래서 "보기" 에서 멈춘다. 버퍼·교차·통계에 답하지 못한다
- **상류가 끊기면 같이 끊긴다** — 문서에 없는 주소(GeoServer 직접)는 예고 없이 닫힐 수 있고, 문 77 개를
  돌보는 비용이 쌓인다
- **바깥 기여의 문턱이 높다** — 플러그인 구조가 없고 규약이 한국어 중심이다. AGPL 이라 남이 가져다 쓰기에도 조건이 붙는다
- **배포 꼴이 좁다** — 웹(안·정적)뿐이다. 데스크톱·모바일 네이티브·노트북 연동이 없다
- **속도와 문서의 부피가 다툰다** — 석 주에 커밋 1,446, `CLAUDE.md` 93 KB. 규약을 읽고 지키는 값이 커지고 있다

### 4.3 어느 자리에 무엇을 쓰나

| 자리 | 맞는 쪽 |
|---|---|
| 내 자료를 열어 분석한다 | GeoLibre |
| 나라마다의 지질도를 겹쳐 보고 속성을 읽는다 | GSM |
| 키가 필요한 상류를 여러 사람이 함께 쓴다 | GSM |
| 오프라인·보안망에서 서버 없이 쓴다 | GeoLibre |
| 노트북·파이썬 작업에 끼운다 | GeoLibre |
| 작은 팀이 빨리 고치고 낸다 | GSM |
| 오래 늘리고 바깥 기여를 받는다 | GeoLibre |

## 5. GSM 에 GeoLibre 의 좋은 점을 들이는 길

**지키는 것** — 서버가 키를 지킨다, 상류마다 문 하나, 서버 이미지에 GDAL 없음, 앱 하나. 들이는 것은
**브라우저 쪽 능력과 개발 규율**뿐이다.

### 5.1 개인 레이어 반입을 브라우저 변환으로 넓힌다 — 효과가 가장 크다

지금 `gsm-personal-layer` v1(`docs/개인레이어_양식.md`)은 WGS84 십진도의 JSON·CSV 만 받고, 평면 좌표계는
"옮겨서 넣는다" 로 끝난다. GeoLibre 처럼 **브라우저 안에서 변환해 v1 으로 바꾼 뒤** 지금의 반입 길에 넘긴다.
양식도 서버도 바뀌지 않는다.

| 입력 | 도구 (모두 MIT) | 크기 |
|---|---|---|
| Shapefile (.zip) | `shpjs` | 작다 |
| KML·KMZ·GPX | `@tmcw/togeojson` (+ JSZip) | 작다 |
| 평면 좌표계 (.prj·EPSG) | `proj4js` | 작다 |
| GeoPackage·GeoParquet·FlatGeobuf 따위 | DuckDB-WASM Spatial | 크다 (수십 MB) |

- DuckDB 는 **그 포맷을 열 때만 늦게 부른다.** 처음에는 작은 셋만 넣는다
- **밖의 정적 판(GSM-open)이 가장 크게 얻는다** — 서버 없이도 개인 레이어를 반입한다
- 서버 이미지 200 MB 대와 "GDAL 없음" 은 그대로다
- 정할 것: 양식을 넓힐지(평면 좌표계를 받는 v2), 브라우저에서 옮겨 v1 을 지킬지. 뒤쪽이 지금의 규약과 맞는다

### 5.2 브라우저 분석 (Turf.js)

"보기에서 멈춘다" 를 서버 없이 메운다.

- 버퍼, 점-면 포함("이 점묶음의 점이 어느 지층 위에 있나"), 거리·면적, 볼록 껍질, 간단한 집계
- 지층 판정은 WMS 타일로는 안 된다 — 지층 면을 받아 둔 지역(오프라인 묶음, GeoServer 속성)부터 한다
- 결과는 개인 레이어로 내보낸다. 5.1 의 반입 길을 다시 쓴다

### 5.3 프런트엔드 구조 — 가장 배울 것

GeoLibre 의 진짜 강점은 React 가 아니라 **"상태는 하나, 화면은 그것에 맞춘다"** 이다. GSM 은 빌드 없이 들인다.

1. **네이티브 ES 모듈로 가른다** — `<script type="module">` 은 번들러가 필요 없다. `map.js` 와
   `earth`·`moon`·`mars`·`mercury` 가 겹치는 것(좌표 표시·레이어 패널·속성 팝업·점묶음 그리기)을 공통 모듈로 뺀다
2. **상태 객체 하나 + `syncLayers()`** — 레이어 순서·켜기·투명도·범위를 한 객체에 두고, OpenLayers 는 그것을
   맞추는 함수 하나만 만진다. GeoLibre `MapController.syncLayers` 의 꼴이다
3. **타입은 빌드 없이** — JSDoc + `// @ts-check`, `tsc --noEmit` 으로 검사만 한다. 내주는 파일은 그대로다

### 5.4 프로젝트 파일 — 지도 상태의 저장·공유

- 레이어 구성·투명도·범위·개인 레이어를 담는 판 번호 있는 JSON 양식(GeoLibre 의 `.geolibre.json` 에 해당).
  이미 있는 `share.js` 를 이 양식 위로 정리한다
- **덤** — GSM 상태를 `.geolibre.json` 으로 **내보내면** 쓰는 사람이 GeoLibre(데스크톱·Jupyter)에서 같은
  지도를 이어 분석한다. 일곱 꼴 배포를 하지 않고 그 효과를 빌리는 가장 싼 길이다

### 5.5 상류를 표로 적는다

- `arcwms.Door` 와 `static-kinds.js` 의 `arcKind` 가 이미 "표 한 줄로 상류 하나" 를 시작했다
- 평범한 WMS·ArcGIS·GeoServer 상류는 표 하나의 Door 로 모으고, 별난 것(KIGAM·GSJ 따위)만 모듈로 남긴다
- GeoLibre 의 플러그인 레지스트리에서 가져올 것은 이 "등록과 선언" 정도로 넉넉하다

### 5.6 품질 장치 (래칫)

- 5.3 으로 모듈이 갈리면 순수 함수(좌표 변환·양식 읽기·시대 옮기기)를 `node --test` 로 시험한다
- 이미 쓰는 `coverage` 와 Playwright(`test_mobile.py`)를 **기준선 래칫**으로 묶는다 — CI 가 수치를 내리지 못하게 막는다
- ESLint 를 경고 상한과 함께 들인다

### 5.7 들이지 않는 것

| GeoLibre 의 좋은 점 | 들이지 않는 까닭 |
|---|---|
| React·TS 로 다시 짜기 | 값에 비해 얻는 것이 적고, 빌드 없는 단순함을 잃는다 |
| 엔진 넷의 추상화 | GSM 은 투영(3413·3031·3978)이 핵심이고, 그것을 OpenLayers 가 가장 잘 한다 |
| Tauri·모바일·Jupyter 배포 | 서버 중심 구조와 맞지 않는다. 5.4 의 내보내기로 갈음한다 |
| 모노레포·패키지 가르기 | "앱 하나" 규약과 부딪치고, 팀 크기에 비해 과하다 |

### 5.8 순서

| 단계 | 할 것 | 품 | 얻는 것 |
|---|---|---|---|
| 1 | 5.3 ES 모듈 가르기·상태 객체 — 나머지의 바탕 | 중 | 중 |
| 2 | 5.1 개인 레이어 변환 (shpjs·togeojson·proj4) | 소 | **대** |
| 3 | 5.6 JS 시험·래칫 | 소 | 중 |
| 4 | 5.4 프로젝트 파일·GeoLibre 내보내기 | 중 | 대 |
| 5 | 5.2 Turf 분석, 5.1 의 DuckDB 확장 | 중 | 중 |
| 6 | 5.5 상류를 표로 모으기 | 중 | 돌보기 |

## 6. 챙길 것

- **라이선스** — 들일 라이브러리(DuckDB-WASM·shpjs·togeojson·proj4js·Turf)는 모두 MIT 라 AGPL 과 어울린다.
  CLAUDE.md "라이선스" 대로 전문을 `docs/licenses/` 에 두고 README "라이선스와 자료의 출처" 에 한 줄씩 적는다.
  GeoLibre 의 코드를 옮겨 올 때도 같다(MIT). 거꾸로 GSM 의 코드가 GeoLibre 로 가면 AGPL 이 따라간다
- **vendor** — CDN 이 아니라 `static/viewer/vendor/` 에 둔다. OpenLayers 와 같은 길이다
- **기록** — 단계마다 P 문서·devlog 를 쓰고 `feature/<기능 이름>` 브랜치에서 한다
- **GSM 을 GeoLibre 의 레이어 소스로 잇는 길** — GSM 의 WMS 중계를 GeoLibre 가 부르면 서로의 빈 곳(GSM 의
  분석, GeoLibre 의 키 감추기·큐레이션)을 메운다. 다만 GSM 을 밖에 열 때 상류마다의 이용 조건
  (`docs/상류_조건표.md`)을 먼저 따진다
