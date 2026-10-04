# 상류 조건표

2026-10-05 · `main` (문서) · wetherilli

판 세션이 맡긴 일이다 — 상류가 여든다섯이 되어, 밖에 열 때 무엇을 내릴지·정적 판에 무엇을 실을지를 사람이 한눈에 정하도록 `docs/상류_조건표.md` 를 썼다.
코드는 바꾸지 않았다.

## 어떻게 모았나

- 상류 목록은 씨앗(`data/*_layers.json` 의 `_상류`)과 `seed_catalog` 의 줄에서 — 여든다섯
- 조건·CORS 는 문의 머리글과 `ATTRIBUTION`·근거 devlog 가 적은 것을 옮겼다. **새로 묻지 않았다** — 그래서 CORS 를 잰 적 없는 곳은 "—" 다
- 캐시는 `views.NO_STORE`, 밖에 열 때는 `views.LAB_ONLY`, 정적 판은 `deploy/static_site.py` 의 `UPSTREAMS`·`BAKED_*`·`OPTIONAL` 에서

## 찾은 것

- 조건을 읽지 않은 곳이 **열여덟** — 한국(KIGAM 오픈API 약관, 5만 WFS 의 CC BY-NC 근거), 동남아 넷, 인도·사우디·몽골, 포르투갈, 캘리포니아,
  니카라과·파라과이·우루과이, CGMW, 부르키나파소·카메룬, 극지연구소
- **CLAUDE.md 와 코드가 다르다** — CLAUDE.md 는 극지연구소(`kopri`)를 "KPDC 공개 정책을 읽기 전까지 LAB_ONLY" 라 적는데, `views.LAB_ONLY` 에는 없고
  정적 판의 기본 상류(`UPSTREAMS`)에 들어 있다. 고치지 않고 표의 "먼저 볼 것" 에 올렸다 — 어느 쪽이 맞는지는 사람이 정한다
- 비상업·판매·내부·개인 조건이 걸린 곳을 표 머리에 모았다 — 밖에 열기 전에 내릴 후보다
