# 정적 판의 시험 — 작은 판을 굽고 `/GSM-open/` 꼴로 띄운다

2026-10-02 · `feature/static-tests` · wetherilli

정적 판(P11)은 지금까지 굽는 것도 화면도 사람이 손으로 띄워 보았다(160·165·166). `viewer/tests/test_static_site.py` 하나로 옮겼다.

## 무엇을 보나

- **굽기** — `deploy/static_site.py` 를 따로 도는 파이썬으로 부른다. 그 스크립트는 제 손으로 Django 를 세우고(빈 DB 에 씨앗,
  `GSM_DB_PATH`·캐시를 임시 폴더로) 운영 DB·캐시를 건드리지 않는다. 시험의 Django 안에서 부르면 그 세우기가 시험의 설정과 엉킨다
- **가짜 구운 것** — `bake_static` 의 출력을 흉내 낸 작은 폴더(GeoMAP 한 장·얀마옌 한 덩이·스발바르 지명 하나·manifest). 진짜
  `bake_static` 은 gpkg·상류가 있어야 해서 시험에서 부르지 않는다 — 그것은 `test_bake_static` 의 몫
- **키** — 굽는 환경에 운영 키(`GSM_KIGAM_KEY`·`GSM_VWORLD_KEY`)를 가짜 값으로 넣고, 구운 HTML 어디에도 그 값이 없는지
- 앞머리(`/GSM-open/`), 구운 것이 제자리에 얹히고 `static-config.baked` 에 실리는지, 구운 점만 목록에 서는지, 연구실 내부용이 없는지,
  지명 색인
- **브라우저**(Playwright, `test_mobile` 과 같은 틀) — 구운 폴더를 `http.server` 로 띄워 한국 탭(페이지 오류 없음·키 칸)·남극 탭·
  스발바르 지명 찾기. 이 판 밖으로 나가는 요청(배경·상류)은 끊는다. `static-kinds.js` 는 아직 없는데(gsm-85 몫) 404 여도 오류가
  없어야 한다 — 남극 탭의 시험이 그것을 함께 본다

## 아직 들어오지 않은 몫은 저절로 켜진다

- 운영 VWorld 키를 빼는 것은 #141(gsm-57, wetherilli 164), 지명 색인은 #142(166)다. 둘 다 병합 전이라, 스크립트에 그 몫이 있을 때만
  그 시험을 돈다(`GSM_STATIC_VWORLD_KEY`·`def place_index` 를 글로 찾는다). 지금 main 에서는 셋을 건너뛰고, 둘을 합친 임시
  worktree 에서는 아홉이 다 통과했다
- 합쳐 보니 **#141 과 #142 가 `static_site.py` 의 `override_settings` 한 줄에서 부딪힌다** — 뒤에 들어오는 쪽이 `VWORLD_KEY=` 와
  `placenames` 두 줄을 다 살려야 한다

## CI

- 굽기 시험은 "뷰어 시험" 에서도 돈다(10 초 남짓, 브라우저 없이). 브라우저 시험은 "휴대폰 화면" job 에 한 단계로 더했다
  (`GSM_BROWSER_TESTS=1`) — 브라우저를 이미 받는 job 이다
