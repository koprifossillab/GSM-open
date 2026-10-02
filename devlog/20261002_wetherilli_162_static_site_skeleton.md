# 연구소 밖 정적 판의 뼈대 — 한국 지질도를 각자 키로

2026-10-02 · `feature/static-site` · wetherilli

P11 의 첫 단계다. https://koprifossillab.github.io/GSM-open/ 에 **한국 지질도**가 뜬다 — 서버 없이, 보는 사람이 넣은 KIGAM
키로. 극지 탭은 gsm-85(브라우저가 곧장, 161)·gsm-91(굽기, 160)의 몫이 붙으면 늘린다.

## 1. 굽는 길 — Django 로 한 번 그린다

`deploy/static_site.py` 가 빈 DB 에 씨앗만 넣고(`seed_catalog` — 운영 DB 를 읽지 않는다) `settings.STATIC_SITE` 를 켠 채 지도 화면을
**한 번** 그려 `map/index.html` 로 둔다. 정적 파일은 `collectstatic`. HTML 의 `/GSM/` 을 `/GSM-open/` 으로 바꾸면 끝이다 —
화면은 주소를 `location.pathname` 에서 세므로(`map.js` 의 BASE) 앞머리만 맞으면 된다. WegenersDream 의 같은 이름 스크립트
(tupandactyl 029)와 같은 길이다. 뿌리(`/GSM-open/`)는 지도로 넘긴다 — 소개 화면은 서버의 것을 많이 써서 정적 판에 두지 않는다.

`deploy/publish_pages.sh` 가 구운 것을 GSM-open 의 `gh-pages` 가지에 **한 커밋으로 덮어** 민다. 역사를 쌓지 않는 까닭 —
극지에서 구운 타일이 붙으면 판마다 저장소가 커진다. 소스는 같은 저장소의 `main`(`publish_open.sh`, 149).

- **버린 것:** GSM-open 에 Actions 워크플로를 두고 거기서 굽기 — 굽는 데 우리 디스크의 파일(GeoMAP·음영판 원본, gsm-91 의 몫)이
  있어야 하는데 GitHub 의 러너에는 없다. 그래서 이 서버에서 굽고 민다. 공개 사본에는 `.github/` 를 두지 않는다(149)

## 2. 정적 모드 — 화면의 고리

`settings.STATIC_SITE` 가 켜지면 서버가 화면에 `static-config`(실을 지역·상류)를 싣고 `<html class="static-site">` 로 그린다.

- **카탈로그를 줄인다**(`views._static_catalog`) — 실을 지역·상류만. KIGAM 의 엮은 레이어("5만 지질도(층리 등 제외)",
  `kigam.COMPOSED`)는 문서에 없는 GeoServer 를 타므로 뺀다. 점묶음은 비운다
- **지역 탭을 줄인다** — 실리지 않은 지역은 `REGIONS` 에서 지우고, 묶음은 품은 것 가운데 실린 것만. 남극처럼 이름으로 부르던
  자리가 하나 깨져(지운 지역의 `.pending`) 지역이 있을 때만 돌게 했다
- **서버가 있어야 하는 것은 숨긴다**(`.server-only`) — 점묶음 올리기, 관리 화면, 3D, 온 지구·달·화성·수성으로 가는 차림
- **좌표 칸** — 도분초·평면 좌표 풀이는 서버(`coords.py`)에 있어 정적 판은 "위도, 경도" 십진도만 읽는다
- **상류 고르기**(`layerKind`) — 정적 모드면 KIGAM 은 `STATIC_KIGAM`, 다른 상류는 `window.GSM_STATIC_KINDS[상류]`(gsm-85 의
  `static-kinds.js`)를 먼저 찾는다. 속성은 주소 대신 Promise 를 받아도 되게 했다 — 브라우저가 곧장 받아 손질한 것을 그대로 쓴다

## 3. KIGAM — 각자 키로 곧장

`STATIC_KIGAM` 이 문서화된 `/openapi/wms` 를 키를 실어 곧장 부른다. KIGAM 은 CORS 를 열지 않았지만(검토 §2) 타일은 `<img>` 라
받힌다 — 그래서 `crossOrigin` 을 두지 않는다. 키가 없으면 타일을 묻지 않는다(빈 타일). 범례도 그림이라 곧장 건다.
**속성은 없다** — `/openapi/wms` 는 GetFeatureInfo 를 막았고(006) GeoServer 길은 CORS 가 없다. JSONP 길(검토 §3)은 쓰지 않는다.

키 칸은 한국 탭 위 알림 줄(`#static-key`)이다. 넣으면 `localStorage`(`gsm.key.kigam`)에 30 일 — 쓸 때마다 다시 센다 —,
"이 PC 에 기억하지 않기" 면 `sessionStorage`. 저장소가 막힌 브라우저에서는 탭 동안만. 넣거나 지우면 켠 레이어의 `key` 를 바꿔
다시 그린다. 우리 키는 정적 판에 없다 — 굽는 동안 `GSM_KIGAM_KEY` 를 지우고 시험이 HTML 에 키가 없는지 지킨다.

## 4. 확인한 것

이 기계에서 `/GSM-open/` 꼴로 띄워 키를 넣으니 KIGAM `/openapi/wms` 타일이 200 으로 왔고 한국 5만 지질도가 그려졌다. 단, 이 서버가
있는 연구소 망은 HTTPS 를 가로채 다시 서명해서(메모리 "KOPRI SSL") 헤드리스 브라우저의 인증서 검사를 끄고 쟀다 — 바깥에서는
일어나지 않는 일이다. github.io 라는 출처에서 키가 받히는지는 Pages 가 켜진 뒤 사람이 본다(KIGAM 키가 도메인에 묶이는지는 아직 모른다).

## 5. 결정 하나 — KPDC 를 내부용에서 뺐다

사용자가 "KPDC 에서 공개한 자료는 실어도 된다" 고 정했다. `views.LAB_ONLY` 에서 `kopri` 를 뺐다 — 053 이 사람 몫으로 남겼던
일이다. 이제 `GSM_PUBLIC=1` 로 열어도 극지연구소 레이어가 남는다. 시험 둘을 그 뜻으로 고쳤다.
