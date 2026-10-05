# README "라이선스와 자료의 출처" 맞추기

2026-10-05 · `main`(문서) · wetherilli

판 세션이 준 일 — 상류가 여든아홉으로 늘었는데 README 의 출처 절은 "다른 상류의 조건은 CLAUDE.md 에" 한 줄이었다. 상류마다 기관·조건을 `docs/상류_조건표.md`
와 맞추고, 옮겨 온 코드의 라이선스 전문이 빠지지 않았는지 본다. README 첫 줄·소개 문구는 사람 몫이라 건드리지 않았다.

## 상류 — 표에서 옮겼다

README 에 표를 새로 적지 않고 **`상류_조건표.md` 의 상류·기관·조건·비상업 네 칸을 스크립트로 옮겼다** — 손으로 옮기면 두 문서가 갈라진다. 조건표가 정본이고
README 는 그것을 가리킨다고 적었다. 칸이 많은 것(CORS·서버 캐시·밖에 열 때·정적 판·근거)은 조건표에만 둔다.

옮기다 보니 조건표에 **두 상류가 빠져 있었다** — 씨앗(`data/*_layers.json`)의 상류 91 과 견주어 찾았다(`gsv`·`gssa` 는 `gsq` 줄에 함께 있어 빠진 것이 아니었다).

- `gsnsw` 뉴사우스웨일스 — CC BY 4.0(GeoServer AccessConstraints, wetherilli 318)
- `mrt` 태즈메이니아 — theLIST 웹 서비스 약관인데 레이어의 저작권 칸이 비었다. **(사람) 읽을 것** 으로 적었다(318 도 정적 판에 싣지 않았다)

## 담아 둔 코드의 라이선스

| 코드 | 전문 |
|---|---|
| EarthThruTime3D(MIT) | `docs/licenses/` 에 있었다 |
| proj4js(MIT)·CesiumJS(Apache-2.0)·MapLibre(BSD-3, 글리프 SIL OFL 1.1) | `static/viewer/vendor/` 에 동봉돼 있었다 |
| **OpenLayers 9.2.4(BSD-2-Clause)** | **없었다** — 압축본 `ol.js` 머리에도 없다. 같은 판의 `LICENSE.md` 를 jsDelivr 에서 받아 `vendor/ol.LICENSE.md` 로 두었다 |

BSD 는 내려 보낼 때 저작권 표시와 조건 전문을 함께 두라고 한다 — 정적 판(GSM-open)과 이미지에 `ol.js` 가 실리므로 빠지면 안 됐다. README 에 담아 둔 코드
표를 두어 다음에 라이브러리를 더할 때 그 줄도 같이 적게 했다.
