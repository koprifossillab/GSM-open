# 덧붙이의 점 레이어 — 문이 `POINTS` 와 `points()` 를 두면

2026-11-12 · `feature/addon-box-seam` · wetherilli

446 이 낸 서버 이음매는 격자(`SETS`)까지였다. 덧붙이가 **점**을 지도에 세울 길이 없었다 — GSM 의 점 레이어는 `views.point_layer` 가
상류마다 손으로 가르고(`if gtnp.knows(name): …`), 카탈로그 행도 상류 이름으로 지어진다. 남극 덧붙이의 다음 자료가 점(제 DB 의 행)이다.

## 꼴 — 격자 때와 같은 법

덧붙이의 문 파일이 정해 둔 이름 둘을 두면 GSM 이 싣는다.

- `POINTS = {레이어 이름: {카탈로그 행에 얹을 것}}` — 출처·저작 표시 따위. 행은 `kind: points`·`style: class`·`hand: "points"` 로 선다
- `points(name, lang, request) -> dict | None` — 덩이. 꼴은 GSM 의 점 레이어와 같다(`features`·`labels`·`links`·`legend`).
  `None` 이면 404

화면은 고칠 것이 한 줄이었다 — 446 이 행의 `hand` 로 손을 고르게 해 두었고, 손 표에 `points` 를 더했다. 그리기·범례·팝업은 GSM 의 점 레이어 그대로다.

## 덩이는 담지 않는다

GSM 의 점 덩이는 `public, max-age` 로 낸다 — 누구에게나 같은 것이라. 덧붙이의 것은 **보는 사람마다 다를 수 있다**(덧붙이가 `request` 를 받는 까닭) —
로그인 뒤의 자료, 사람마다 보이는 범위. 그래서 `no-store` 로 낸다. 덧붙이가 고를 수 있게 열지 않았다 — 틀리면 새는 쪽이라 닫힌 쪽을 기본으로 둔다.

## 버린 것

- **덧붙이가 제 주소로 덩이를 내고 행에 그 주소를 적는 길** — 화면의 점 받기(`pointUrl`)가 `points/?layer=` 하나로 짜여 있어 주소를 받게 하면
  정적 판·연대 막대·판 번호의 갈림을 다 건드린다. 서버에서 한 번 넘기는 쪽이 고칠 것이 적다
- **연속값(`style: value`)·잘라 주기(`slice`)** — 쓰는 것이 없다

## 시험

가짜 덧붙이의 문에 점 레이어 하나(`fakeaddon:cores`) — 카탈로그 행의 꼴, `points/` 의 덩이와 `no-store`, 덧붙이가 없으면 404.
