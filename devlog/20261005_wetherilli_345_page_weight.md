# 첫 화면의 무게

2026-10-05 · `fix/page-weight` · wetherilli

판 세션이 준 일 — 지도·온 지구·3D 를 처음 열 때 받는 JS·CSS·JSON 의 크기와 수를 재고, 정적 파일의 캐시 머리와 운영 nginx 의 gzip 을 본다. 화면 동작을
바꾸지 않고 줄일 수 있는 것만 고친다.

## 잰 것 (운영 nginx 를 이 기계에서 `Host: paleolab` 으로, 2026-10-05)

| 것 | 받는 크기 | 줄임 | 캐시 머리 |
|---|---:|---|---|
| 지도 HTML | 83 KB (원래 456 KB — 카탈로그를 품는다) | gzip | ETag |
| 온 지구·3D HTML | 11·33 KB | gzip | ETag |
| `map.js` | 128 KB | gzip | 판 붙음 · immutable |
| `ol.js`·`proj4.js` | 227·42 KB | gzip | **판 없음** · immutable |
| `Cesium.js`·`maplibre-gl.js` | 1.75 MB·211 KB | gzip | **판 없음** · immutable |
| `splash.gif`(지도) | **864 KB** | — | **판 없음** · immutable |
| `/GSM/catalog/` JSON | **486 KB** | **없음** | — |

세 가지가 걸렸다.

1. **판 없는 주소가 `immutable`** — nginx 는 `/GSM/static/` 을 판이 있든 없든 7 일 `immutable` 로 두었다. 같은 이름으로 대기 화면·벤더 파일을 바꾸면 사람의 브라우저가
   한 주 동안 옛것을 낸다. 판이 붙은 것은 `map.js`·`map.css` 따위 몇뿐이었다(템플릿에서 52 곳이 빠졌다). 그리고 앱(Django 정적 서빙)도 `max-age=60` 을 붙여
   **Cache-Control 머리가 둘**이었다 — 브라우저마다 어느 것을 따를지 갈린다
2. **앱이 내는 JSON 은 줄이지 않는다** — 호스트 nginx 의 기본 `gzip on` 은 `text/html` 만 줄인다. JS·CSS 는 앱이 미리 줄인 것을 내서 괜찮고, 카탈로그·범례·
   속성·점 레이어 JSON 만 날것이었다
3. **대기 화면이 무겁다** — GIF 여섯이 0.5–1.1 MB. 지도 화면은 극지로 열면 기본 GIF 를 받기 시작한 뒤 스크립트가 극지 GIF 로 바꿔 **둘을 받았다**

## 고친 것

- **템플릿의 정적 파일 주소마다 `?v=<내용 표>`**(52 곳). 끝이 `/` 인 뿌리 주소(Cesium·MapLibre 가 제 안에서 이어 붙인다)만 빼고 — 시험(`test_정적_주소에는_판이_붙는다`)이 지킨다
- **nginx — 판이 붙은 것만 1 년 `immutable`**, 판이 없는 것(벤더가 제 안에서 부르는 그림·작업자)은 한 시간 뒤 ETag 로 되묻는다. 앱의 Cache-Control 은
  `proxy_hide_header` 로 지워 머리가 하나다. 이 파일은 server 블록 안의 조각이라 `map` 대신 `set`·`if` 로 갈랐다
- **nginx — `/GSM/` 의 JSON·GeoJSON·SVG 도 gzip**(`gzip_types`·`gzip_proxied any`·`gzip_vary`). 카탈로그 486 → 81 KB
- **대기 화면을 같은 화소의 WebP 로**(무손실, `<picture>` 에 GIF 를 받침으로) — 30–65% 작다(지도 864 → 306 KB). 첫·가운데·끝 장의 화소가 GIF 와 같은지 견주었다.
  지도 화면은 그림 주소를 스크립트가 극지를 가린 **뒤에** 적어 하나만 받는다

nginx 둘은 임시 nginx(같은 설정 조각, 운영 앱에 읽기만 붙여)로 띄워 머리를 확인했다 — `map.js?v=` 는 `public, max-age=31536000, immutable` 하나,
`vendor/ol.js` 는 `public, max-age=3600` 하나, 카탈로그는 `Content-Encoding: gzip` 81 KB.

## 두지 않은 것

- 지도 HTML 이 품은 카탈로그(456 KB 날것) — 첫 칠에 레이어 목록을 바로 그리려고 품는 것이다. gzip 으로 83 KB 라 그대로 둔다
- `ol.js` 를 쓰는 것만 담은 판으로 — 빌드를 새로 꾸려야 한다. 쉬운 일이 아니다
- Cesium 1.75 MB — 구 화면의 몸통이다

## 운영 메모

**nginx 조각은 사람이 깐다**(sudo): `sudo cp deploy/nginx/GSM-subpath.conf /etc/nginx/snippets/GSM-subpath.conf && sudo nginx -t && sudo systemctl reload nginx`.
템플릿·WebP 는 판과 함께 나간다 — nginx 를 늦게 깔아도 화면은 그대로 돈다(판 붙은 주소가 늘 뿐).
