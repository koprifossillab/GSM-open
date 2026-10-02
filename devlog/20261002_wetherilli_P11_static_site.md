# 연구소 밖 정적 판 — GitHub Pages 의 GSM-open (계획)

2026-10-02 · `main`(계획) · wetherilli

사용자: "그냥 github.io 까지 만들어." 검토는 [docs/정적_밖_경로.md](../docs/정적_밖_경로.md), 알림은 이슈 #129.
주소는 **https://koprifossillab.github.io/GSM-open/** — 공개용 저장소 GSM-open(wetherilli 149)의 `gh-pages` 가지.

## 1. 정한 것 (사용자, 2026-10-02)

- **서버 없이** — 연구소 서버를 밖에 열지 않는다(터널 없음). 정적 파일만 Pages 에
- **한국은 각자 KIGAM 키** — 화면에 넣어 그 브라우저 `localStorage` 에만, 30 일 기억, "키 지우기"·"이 PC 에 기억하지 않기"
- **극지는 상류를 브라우저가 곧장** — GEUS·NPI·PGC·EMODnet·그린란드 포털은 CORS 가 열려 있다(검토 §2). GEUS `whoami` 도 각자
- **KPDC 공개 자료는 싣는다** — `kopri` 를 `LAB_ONLY` 에서 뺀다(053 의 사람 몫이 이것으로 정해졌다)
- "비공개로 받아 넣은 자료는 없다" — 다만 phyloserver(연구실 내부망)는 정적 판의 브라우저가 닿지 못해 빠진다. 음영판·민판은 구워 싣는다.
  중국 geo3al(USGS "내부 용도만")은 이번 범위(한국·극지) 밖이라 손대지 않는다
- VWorld 는 지금처럼 화면에 키가 실린다 — 공개 판용 키를 따로 받는 것이 낫다(검토 §10). 받을 때까지 지금 키

## 2. 나눔

| 몫 | 누가 | 브랜치 · devlog |
|---|---|---|
| 뼈대 — `deploy/static_site.py`(Django 로 map.html 을 정적 판으로 한 번 그리기, 정적 파일·카탈로그), map.js 의 **정적 모드 고리**(`GSM_STATIC`), KIGAM 각자 키, 서버만 하는 것 끄기(올리기·관리 등), GSM-open `gh-pages` 로 밀기, README | gsm-31 | `feature/static-site` · 162 |
| 우리 파일 굽기 — GeoMAP·IBCSO·얀마옌·점 묶음·음영판을 화면이 부르는 주소 꼴 그대로 (`manage.py bake_static`) | gsm-91 | `feature/static-bake` · 160 |
| 극지 상류를 곧장 — `static-kinds.js`(GEUS·NPI·PGC·EMODnet·KPDC·포털 점, 속성 손질의 JS 판) | gsm-85 | `feature/static-polar` · 161 |

고리의 약속: 정적 모드면 map.js 가 상류마다 `window.GSM_STATIC_KINDS[upstream]` 을 먼저 찾는다 —
`{source(name,row), info(source, coordinate, view) → Promise<{features:[{props}]}>, legend?}`. 없으면 그 레이어는 정적 판에서 숨긴다.
구운 파일은 지금 서버 주소 꼴(`geomap/…`, `points/<이름>.json` …) 그대로라 map.js 는 BASE 만 보면 된다.

## 3. 단계

1. 뼈대 + KIGAM 각자 키 → 한국 탭이 github.io 에서 뜬다 (첫 링크)
2. 극지 곧장(gsm-85) + 굽기(gsm-91) → 극지 탭
3. 판마다 — 판 세션이 `publish_open.sh`(소스)에 이어 정적 판도 굽고 민다

## 4. 걸리는 것

- Pages 는 사이트 1 GB·파일 100 MB. GeoMAP 을 줌 몇까지 구울지는 gsm-91 이 재고 고른다
- KIGAM 속성은 CORS 가 없어 첫 판은 **그림만**(누르면 "정적 판에서는 속성이 없다"). JSONP 길은 쓰지 않는다(검토 §3)
- 저장소 주인이 GSM-open 의 Settings → Pages → Source 를 `gh-pages` 가지로 한 번 켠다
