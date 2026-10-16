# RustGIS 구조 및 장단점 분석 — GSM 과 견주고, 들일 것을 고른다

2026-10-13 · koprifossillab · 검토 (계획이 아니다)

[RustGIS](https://github.com/opengeos/RustGIS)(v0.2.0, Apache-2.0)의 구조를 읽고 GSM 과 견준다.
[GeoLibre 구조 및 장단점 분석](GeoLibre_구조_및_장단점_분석.md)과 같은 틀이다. 장단점을 따지고, GSM 의 원칙을
건드리지 않고 들일 수 있는 것을 고른다. 수치는 2026-10-13 의 `~/projects/RustGIS`(커밋 103 개)에서 쟀다.

> **같은 날 5.0 을 더하고 3·4·5.1·5.2 를 고쳤다** — GSM 쪽 시험을 다시 보니 `doors.REGISTRY` 와 `test_doors.py`,
> 상류의 이상한 응답을 넣는 `test_thin_doors.py`·`test_risky_paths.py` 가 이미 있었다. 처음 판은 "GSM 의 규약은
> 사람이 지킨다" 고 적었는데 반만 맞다. 무엇이 기계로 서 있고 무엇이 비었는지를 5.0 에 표로 둔다.

## 1. 한 줄

**RustGIS 는 "순수 Rust 로 짠 데스크톱 GIS(ArcGIS Pro 꼴)" 이고, GSM 은 "서버가 상류를 지키는 지질도 뷰어" 다.**
겹치는 것이 적다. GSM 이 들일 것은 Rust 도 egui 도 아니다. **"모든 동작은 이름 있는 명령이다"**,
**"적대적 입력에 깨지지 않는다"**, **"층의 경계를 기계가 검사한다"**, 이 세 규율이다.
GeoLibre 에서는 브라우저 쪽 능력을 들였다면, RustGIS 에서는 **규약을 시험으로 바꾸는 법**을 들인다.
GSM 은 규약을 이미 잘 만들었고 일부는 시험으로도 세웠다. 배울 것은 **그것을 끝까지 — 모든 문·모든 뷰로 — 넓혀
사람이 잊어도 CI 가 기억하게 하는 습관**이다.

## 2. RustGIS 는 어떻게 생겼나

### 2.1 개요

GeoLibre 와 같은 사람(opengeos, Qiusheng Wu)이 만든 다음 세대다. 한 Rust 프로그램이 GPU 로 그린다.
**네이티브(Windows·macOS·Linux)와 브라우저(WebAssembly, web.rustgis.app)에서 같은 앱이 돈다.** 런타임도
서버도 없다. GeoLibre 의 도구 묶음(geolibre-rust·Whitebox, 1,000 개 넘게)을 따로 받는 실행기로 부른다.

내세우는 것:

- **모든 버튼이 id 있는 명령이다** — 리본·단축키·명령 검색·CLI(`rustgis-cli`)·AI 도우미·MCP 서버가 같은 명령을 부른다
- **모든 변경을 되돌린다**(undo)
- ArcGIS Pro 를 닮은 리본(Home·Data·Style·Edit·Analyze·View·Publish), 속성표, 레이아웃·보고서·ModelBuilder
- 샌드박스 WebAssembly 플러그인(`wasmi`)과 레지스트리(plugins.rustgis.app)
- 15 개 언어

### 2.2 규모와 나이

- Rust 약 **7.5만 줄**, `#[test]` 약 300 개, 워크플로 9 개
- **2026-10-10 에 시작했다 — 사흘에 커밋 103 개(PR #119 까지).** 기능 목록은 넓지만 ROADMAP 이 스스로
  "많은 기능이 첫 판이다" 라고 적는다

### 2.3 저장소 구조 — 층을 쌓은 Cargo 워크스페이스

| 층 | 크레이트 | 하는 일 | 줄 |
|---|---|---|---|
| L0 | `geom` | 좌표·범위·Web Mercator·측지 거리와 면적 | 0.5천 |
| L1 | `data` | 피처·속성, GeoJSON·CSV·Shapefile·KML·GPX·GeoPackage·GeoParquet·FlatGeobuf, SQL where, 래스터(GeoTIFF·EPSG 재투영) | 1.2만 |
| L2 | `map`·`analysis`·`tiles` | 레이어·심볼·라벨·카메라·배경지도 / 지오프로세싱 / XYZ·TMS·WMS·MVT·PMTiles·MBTiles, 타일 캐시 | 0.6만·0.3만·0.7만 |
| L3 | `render`·`plugins`·`geolibre` | tiny-skia 렌더러·라벨 배치·PNG / WASM 플러그인 / GeoLibre 도구 | 0.5만·0.2만·0.1만 |
| L4 | `engine` | `Session`·undo·명령 레지스트리 (명령 id 약 350) | 1.7만 |
| L5 | `assistant` | AI 도우미 — 명령을 부르는 채팅 에이전트(Anthropic·OpenAI·Gemini·Ollama…) | 0.3만 |
| L6 | `ui-egui` | 리본·창·지도·속성표 (갈아 끼울 수 있다) | 1.8만 |
| apps | `rustgis`·`rustgis-cli`·`rustgis-web` | 데스크톱·명령줄·브라우저 | 0.1만 |

**각 층은 제 아래만 쓴다.** `cargo xtask layers` 가 이를 검사한다 — L6 아래 어디서도 egui·eframe·rfd 를
쓰지 않는다.

### 2.4 규약 (AGENTS.md)

- **절대 멈추지 않는다** — 테스트 밖에서 `unwrap`·`expect`·`panic!` 금지, `unsafe` 금지(`forbid`).
  파일과 명령 인자는 **적대적 입력**으로 본다. `hostile_params_never_panic` 시험이 **모든 명령·도구에 쓰레기
  인자를 넣어 돌린다.** 멈춘 것을 고치면 회귀 시험을 하나 더한다
- **wasm 을 깨지 않는다** — `apps/` 아래 전부가 `wasm32-unknown-unknown` 으로 빌드돼야 한다. CI 가 본다
- **명령은 대화상자를 열지 않는다** — 그래서 CLI·AI·시험이 UI 없이 같은 명령을 부른다
- **화면은 헤드리스 스크린숏으로 본다** — `ui_shot` 예제가 JSONL 스크립트로 앱을 돌려 PNG 를 낸다.
  README 의 그림이 전부 그렇게 나왔다
- **남의 자산을 넣지 않는다** — 아이콘은 코드로 그리고, 자산 파일은 하나하나 `ATTRIBUTION.md` 에 한 줄씩 적는다
- 품질 관문은 `cargo xtask ci` 하나 — fmt, clippy `-D warnings`, 시험, 층 검사

### 2.5 지도·타일 — GSM 과 가장 맞닿는 곳

- 화면은 Web Mercator 가 기본이고, Equal Earth·Robinson·극 평사도·EPSG 코드로 바꾼다. 레이어는 그때그때 투영한다
- **WMS 는 `{bbox-epsg-3857}` 주소 틀 하나로만 받는다.** 3857 타일을 받아 다른 투영으로 **다시 펴서** 그린다.
  `GetCapabilities`(레이어 목록)와 `GetFeatureInfo`(속성)는 없다
- 타일 캐시는 **메모리 안의 LRU** 다. 디스크에 남지 않고, 사람마다 따로다
- 상류의 키는 쓰는 사람이 제 것을 넣는다. 감춰 줄 서버가 없다

## 3. GSM·GeoLibre 와 견주기

| 항목 | RustGIS | GeoLibre | GSM |
|---|---|---|---|
| 꼴 | 네이티브 데스크톱 GIS (+ wasm 웹) | 웹 앱을 여러 꼴로 포장 | 서버 + 웹 뷰어 |
| 언어 | Rust 하나 | TypeScript + Python + Rust | Python + JS |
| UI | egui (캔버스에 직접 그림) | React (DOM) | 빌드 없는 JS + OpenLayers (DOM) |
| 무게중심 | 클라이언트 | 클라이언트 | 서버 |
| 상태 | `Session` + 명령 + undo | Zustand 스토어 | Django 모델 + IndexedDB |
| 늘리는 방식 | 샌드박스 WASM 플러그인 | JS 플러그인 | 상류마다 문 하나 |
| 경계 검사 | **기계가 한다** (`xtask layers`) | 패키지 경계 + 타입 | 문의 명세는 시험(`test_doors.py`), import 경계는 사람 |
| WMS | 3857 틀만, 속성 없음 | MapLibre 래스터 소스 | 지역 투영으로 곧장, 속성·범례·카탈로그 |
| 타일 캐시 | 메모리, 사람마다 | 브라우저, 사람마다 | 디스크, 모두가 함께 |
| 분석 | 넓다 (첫 판들) | 넓고 깊다 | 없다 |
| 나이 | 사흘·커밋 103 | 넉 달 반·커밋 1,973 | 석 주·커밋 1,446 |
| 라이선스 | Apache-2.0 | MIT | AGPL-3.0 |

### 3.1 가장 크게 다른 세 자리

**동작을 무엇으로 적나.** RustGIS 에서는 버튼을 누르는 것과 `rustgis-cli run --cmd 'layer.symbology=…'` 가 같은
일이다 — 둘 다 명령 레지스트리를 부른다. 그래서 AI 도우미·MCP·시험·스크린숏 스크립트가 공짜로 따라온다.
GSM 의 동작은 `map.js` 의 이벤트 처리기 안에 흩어져 있어 밖에서 부를 이름이 없다.

**규약을 누가 지키나.** RustGIS 의 규약(층, 깨지지 않기, wasm)은 **CI 가 모두 막는다.** GSM 은 반쯤이다 —
문의 명세(세 손·예외·딱지·씨앗의 상류)는 `test_doors.py` 가, 호스트의 `GSM.db` 는 dummy DB 엔진이 막는다.
그러나 **"문 밖에서 `requests` 를 쓰지 않는다"·"문은 서로를 타지 않는다" 는 CLAUDE.md 에만 있다**(5.0).

**극지를 어떻게 그리나.** RustGIS 는 3857 타일을 받아 극 평사도로 다시 편다. Web Mercator 는 위도 ±85° 밖을
담지 못하므로 **남극 내륙과 북극점 둘레는 3857 타일에서 나오지 않는다.** GSM 은 상류에 3413·3031 로 곧장
묻는다(CLAUDE.md "지역"). 극지 지질도에서는 GSM 의 길만 맞다.

## 4. 장단점

### 4.1 RustGIS

**좋은 점**

- **빠르고 작다** — 네이티브 하나, GPU 로 그린다. 런타임도 서버도 없다
- **하나의 코드가 데스크톱과 브라우저에서 같게 돈다** — Rust 하나라 GeoLibre 처럼 여러 언어를 잇지 않는다
- **모든 것이 명령이다** — CLI·AI·MCP·시험·스크린숏이 한 레지스트리를 쓴다. 스크립트로 지도를 만든다
- **깨지지 않음을 시험으로 지킨다** — 적대적 인자를 모든 명령에 넣는 시험, `unwrap`·`unsafe` 금지
- **층의 경계를 기계가 검사한다** — UI 를 갈아 끼울 수 있는 구조가 말로만 있지 않다
- **ArcGIS 를 쓰던 사람에게 낯익다** — 리본, 속성표, 편집, 레이아웃, ModelBuilder, undo
- **플러그인이 샌드박스에서 돈다** — 설치 전에 권한을 보이고 SHA-256 으로 확인한다
- **자산의 출처가 깨끗하다** — 남의 아이콘·글꼴 없이 코드로 그리고, `ATTRIBUTION.md` 에 다 적는다

**아쉬운 점**

- **아주 젊다** — 사흘·v0.2.0. 기능 목록이 넓은 만큼 각 기능은 첫 판이다(`analysis` 3천 줄에 버퍼·디졸브·
  가시권·IDW·최단경로가 다 든다). 오래 쓰며 다듬어진 것이 아직 없다
- **OGC 서비스가 얕다** — WMS 는 3857 주소 틀 하나, `GetCapabilities`·`GetFeatureInfo`·범례가 없다.
  지질도처럼 "눌러서 속성을 읽는" 일에는 맞지 않다
- **극지에 약하다** — 3857 타일을 다시 펴므로 ±85° 밖이 빈다
- **공용 캐시와 키 감추기가 없다** — 서버가 없는 구조의 값이다
- **egui 의 값** — 캔버스에 직접 그리므로 글자 고르기·복사, 브라우저 번역, 화면 낭독기, 검색 노출이
  DOM 앱보다 약하다. 웹판의 wasm 도 크다
- **Rust 의 문턱** — 지질학자·학생이 고치러 들어오기 어렵다. 빌드도 느리다
- **분야의 깊이가 없다** — 범용 GIS 라 지질도 큐레이션·시대 풀이·지역 투영 고르기가 없다

### 4.2 GSM 을 RustGIS 옆에 두면

GeoLibre 분석의 4.2 가 그대로 선다. RustGIS 와 견줄 때 더 또렷해지는 것만 적는다.

- **더 또렷해지는 좋은 점** — OGC 를 깊이 쓴다(지역 투영으로 곧장, 속성·범례·카탈로그). 극지가 제대로 그려진다.
  DOM 이라 속성 글자를 고르고 복사할 수 있다. 파이썬·JS 라 고치러 들어오기 쉽다
- **더 또렷해지는 아쉬운 점** — 동작에 이름이 없어 스크립트·시험·AI 로 부르지 못한다. import 경계를 기계가 막지
  않는다. 상류의 이상한 응답은 문 몇에서만 시험하고(`test_thin_doors.py` 의 넷 따위), 모든 문·모든 뷰에 한꺼번에
  넣어 보지 않는다. undo 가 없다

### 4.3 어느 자리에 무엇을 쓰나

| 자리 | 맞는 쪽 |
|---|---|
| 지질도를 겹쳐 보고 눌러 속성을 읽는다 | GSM |
| 남극·북극 지질도를 본다 | GSM |
| 내 자료를 편집·분석하고 인쇄용 지도를 만든다 | RustGIS (넓게) · GeoLibre (깊게) |
| 지도 작업을 스크립트·AI 에게 맡긴다 | RustGIS |
| 설치 없이 가벼운 데스크톱 GIS | RustGIS |
| 노트북·파이썬 작업에 끼운다 | GeoLibre |

## 5. GSM 에 RustGIS 의 좋은 점을 들이는 길

**지키는 것** — GeoLibre 분석의 5 와 같다. 서버가 키를 지킨다, 상류마다 문 하나, 서버 이미지에 GDAL 없음,
앱 하나, 빌드 없는 JS. 들이는 것은 **규율과 그것을 지키는 시험**이다. 대부분 코드를 옮기지 않고 생각만 빌린다.

### 5.0 지금 기계로 서 있는 것과 빈 것 (2026-10-13 확인)

| 규약 | RustGIS 에서 그 자리 | GSM 에서 지금 | 빈 것 |
|---|---|---|---|
| 문의 명세가 고르다 | 명령 레지스트리 | **선다** — `doors.REGISTRY`(명세 92), `test_doors.py` 가 세 손·예외·딱지·씨앗의 상류를 본다 | — |
| 키가 새지 않는다 | — | **선다** — `test_risky_paths.py` 가 오류 글·로그를 본다 | — |
| 호스트는 DB 를 열지 않는다 | — | **선다** — `GSM_RUN_PLACE=host` 면 DB 엔진이 dummy | — |
| 문 밖에서 `requests` 를 쓰지 않는다 | `xtask layers` | 글로만 — CLAUDE.md "구조" | **import 경계 시험** (5.1) |
| 문은 서로를 타지 않는다 | `xtask layers` | 글로만 | 같은 시험 (5.1) |
| 이상한 입력에 깨지지 않는다 | `hostile_params_never_panic` (모든 명령) | 몇 곳만 — `test_thin_doors.py`(문 넷), `test_risky_paths.py`(키·연결 레이어) | **모든 문·모든 뷰로 넓히기** (5.2) |
| 동작에 이름이 있다 | 명령 id 약 350 | 없다 — `map.js` 이벤트 처리기 | 명령 표 (5.3) |
| 자산마다 출처가 있다 | `ATTRIBUTION.md` | 코드·지도 자료만 | 정적 자산 (5.5) |

### 5.1 "문 밖에서 `requests` 금지" 를 시험으로 막는다 — 가장 싸고 바로 쓴다

RustGIS 의 `xtask layers` 에 해당한다. 파이썬 `ast` 로 `web/viewer/*.py` 를 읽어 `requests` 를 가져오는 모듈이
문 목록에 드는지 본다. 목록 밖이면 시험이 깨진다.

- **목록은 새로 만들지 않는다 — `doors.REGISTRY` 를 쓴다.** 2026-10-13 에 재 보니 `requests` 를 가져오는 모듈은 77,
  그 가운데 64 가 `REGISTRY` 에 있다. 남는 13 은 WMS 를 중계하지 않는 문이다 — 데이터소스를 받는 것(`pbdb`·`gvp`·`usgs`·
  `macrostrat`·`neotoma`·`kpds`·`trek`), 호스트에서만 부르는 것(`gfs`·`era5`·`gmgsi`·`ecco`), `basemaps`, `linked`.
  이 13 을 시험 쪽 작은 표(또는 `REGISTRY` 곁의 "자료 문" 표)로 두면 둘을 합친 것이 문 목록이 된다
- CLAUDE.md "구조" 의 일흔일곱 나열은 그 표를 가리키게 한다 — 목록을 두 곳에 적다 어긋나는 일이 없다
- 같은 틀로 "문은 서로를 타지 않는다"(문이 다른 문을 import 하지 않는다)도 막는다
- `test_doors.py` 에 시험 하나를 더하는 일이다. 의존성이 하나도 늘지 않는다

### 5.2 적대적 입력 시험 — 모든 뷰에 쓰레기를 넣는다

RustGIS 의 `hostile_params_never_panic` 에 해당한다. GSM 에는 그 씨앗이 이미 있다 — `test_thin_doors.py` 가 문 넷
(GSI·JMG·NSGS·SKGS)에 "상류가 그림·JSON 이 아닌 것을 줄 때" 를 넣어 본다(wetherilli 349). **그것을 손으로 고른 넷에서
모든 문으로, 문에서 모든 뷰로 넓힌다.**

- **우리 쪽 입력** — URL 레이어 이름, `BBOX`, 줌, 좌표, 점묶음 반입 파일. Django 의 URL 목록(경로 164)을 돌며 뷰마다
  빈 값·음수·NaN·아주 큰 수·이상한 글자·없는 레이어를 넣고, **500 이 나지 않는지**만 본다(400·404 는 괜찮다)
- **상류 쪽 입력** — `doors.relays()` 를 돌며 문마다 상류가 빈 몸·HTML 오류 페이지·깨진 XML·엉뚱한 content-type·
  타임아웃을 돌려주게 세운다(`test_thin_doors.py` 의 `answer()` 를 그대로 쓴다). 문이 `views.UPSTREAM_ERRORS` 밖의 예외를
  흘리지 않고 안내 타일이나 빈 속성으로 끝나는지 본다 — 새 문이 `REGISTRY` 에 들면 저절로 시험에 든다
- 멈춘 것을 고치면 그 입력을 회귀 시험으로 남긴다 — RustGIS 의 규약 그대로다
- 상류 여든 남짓 가운데 어디가 이상한 응답을 줄지 미리 모르는 GSM 에 특히 맞다

### 5.3 동작에 이름을 단다 — 명령 레지스트리 (가볍게)

GeoLibre 분석 5.3 의 "상태 객체 하나 + `syncLayers()`" 위에 얹는다.

- 브라우저 쪽 동작을 `{id, 인자} → 상태 변경` 의 작은 표로 모은다: `layer.toggle`·`layer.opacity`·`layer.order`·
  `view.goto`·`view.extent`·`personal.import`·`attr.at` 따위
- 패널·단축키·공유 주소(`share.js`)가 같은 id 를 부른다. **공유 주소가 곧 명령의 나열**이 되어 판이 바뀌어도
  뜻이 남는다
- Playwright 시험과 스크린숏이 화면을 클릭하는 대신 명령을 부른다 — 화면 배치가 바뀌어도 시험이 덜 깨진다
- undo 는 이 위에 나중에 얹을 수 있다. 지금은 하지 않는다

### 5.4 스크립트로 찍는 스크린숏

RustGIS 의 `ui_shot` 에 해당한다. 이미 있는 Playwright(`requirements-browser.txt`)로 5.3 의 명령을 차례로 부르는
작은 스크립트를 두고, 지역 탭마다 PNG 를 찍는다.

- 정적 판의 `deploy/static_smoke.py` 가 이미 비슷한 일을 한다 — 그것을 연구소 안 판에도 넓힌다
- PR 에 붙이거나, README·소개 화면 그림을 다시 찍는 데 쓴다

### 5.5 자산 출처표

RustGIS 의 `ATTRIBUTION.md` 에 해당한다. `static/viewer/` 의 splash·emblem 그림, `vendor/` 의 라이브러리,
`data/` 의 씨앗 파일을 한 줄씩 — 출처·라이선스·언제 받았나. GSM 은 코드는 `docs/licenses/`, 지도 자료는
`docs/상류_조건표.md` 로 이미 적는다. 그 사이의 **정적 자산**이 비어 있다.

### 5.6 (나중) 카탈로그를 부르는 CLI·MCP

RustGIS 의 `rustgis-cli`·`rustgis-cli mcp` 에 해당한다. 5.3 이 서고 나서 생각한다.

- `manage.py` 명령이나 작은 MCP 서버로 "이 범위의 지질도 레이어 목록", "이 좌표의 지층 속성" 을 부른다
- 서버가 키를 지키므로 **키를 내보내지 않고** AI 에이전트에 지질도를 열어 줄 수 있다. 이 점은 RustGIS 에는 없는 GSM 만의 자리다
- 상류의 이용제한("지나치게 잦은 호출")을 먼저 따진다 — 에이전트는 사람보다 자주 부른다

### 5.7 들이지 않는 것

| RustGIS 의 좋은 점 | 들이지 않는 까닭 |
|---|---|
| Rust·egui 로 다시 짜기 | 고치러 들어오는 문턱이 오르고, DOM 의 글자 고르기·번역·접근성을 잃는다 |
| 3857 을 받아 다시 펴는 투영 | 극지가 빈다. GSM 의 "지역 투영으로 곧장 묻기" 가 맞다 |
| 샌드박스 WASM 플러그인 | 앱 하나·상류마다 문 하나 규약과 맞지 않고, 기여자 규모에 비해 과하다 |
| 편집·레이아웃·보고서·ModelBuilder | 뷰어의 일이 아니다. 필요하면 GeoLibre·RustGIS 로 내보낸다 |
| 브라우저가 상류를 곧장 부름 | 키를 감추는 것이 GSM 에 서버가 있는 까닭이다 (정적 판만 예외) |

### 5.8 순서

GeoLibre 분석 5.8 과 함께 본다.

| 단계 | 할 것 | 품 | 얻는 것 |
|---|---|---|---|
| 1 | 5.1 문 경계 시험 | 소 | 중 — 규약이 기계로 선다 |
| 2 | 5.2 적대적 입력 시험 (뷰·문) | 소–중 | **대** — 상류 여든 남짓의 이상한 응답에 대비한다 |
| 3 | 5.5 자산 출처표 | 소 | 소 — AGPL 공개 사본(`GSM-open`)을 깨끗하게 |
| 4 | GeoLibre 5.3 + 5.3 명령 레지스트리 | 중 | 대 — 5.4·5.6 의 바탕 |
| 5 | 5.4 스크립트 스크린숏 | 소 | 중 |
| 6 | 5.6 CLI·MCP | 중 | 중 |

## 6. 챙길 것

- **라이선스** — RustGIS 는 Apache-2.0 이다. Apache-2.0 코드는 AGPL-3.0 으로 들어올 수 있다(거꾸로는 안 된다).
  다만 위의 길은 대부분 **생각을 빌리는 것**이라 옮길 코드가 거의 없다. 옮긴다면 CLAUDE.md "라이선스" 대로
  전문을 `docs/licenses/` 에 두고 README 에 한 줄 적으며, Apache-2.0 의 NOTICE 조건을 따른다
- **GeoLibre·RustGIS 와의 이음** — 둘 다 XYZ·WMS 주소 틀을 받는다. GSM 의 타일 중계 주소를 내보내면 두 앱이
  GSM 의 지질도를 배경으로 쓸 수 있다(RustGIS 는 3857 이므로 극지는 빠진다). 밖에 열 때는 `docs/상류_조건표.md`
  를 먼저 따진다
- **RustGIS 는 빨리 바뀐다** — 사흘 만에 v0.2.0 이다. 위의 수치와 "없다" 고 적은 것(WMS 속성·디스크 캐시 따위)은
  곧 낡을 수 있다. 다시 볼 때는 저장소를 새로 잰다
- **기록** — 단계마다 P 문서·devlog 를 쓰고 `feature/<기능 이름>` 브랜치에서 한다
