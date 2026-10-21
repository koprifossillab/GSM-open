# 판 PR 의 검사 — 건너뛴 job 은 막지 않는다

2026-10-20 · `fix/release-checks-skipped` · wetherilli

판 세션이 #434 리뷰에서 짚었다 — 397 뒤로 PR 의 휴대폰 화면·이미지 굽기는 그쪽 파일이 바뀔 때만 돈다. 문서만 고친 판 PR 이면 둘이
`SKIPPED` 로 오는데 `release.sh` 의 `checks()` 는 "모두 SUCCESS" 만 ok 로 봐서 판이 멈춘다.

- **하나라도 SUCCESS 이고 나머지가 SUCCESS·SKIPPED 면 ok.** 뷰어 시험은 PR 마다 늘 돌므로 SUCCESS 하나는 늘 있다. 전부 SKIPPED 이거나
  비었으면 여전히 막는다 — 아무것도 보지 않은 PR 을 통과시키지 않으려고
- 태그의 CI 는 경로를 가리지 않고 다 돈다. `ship` 이 태그 실행의 결론을 따로 보므로 판마다 휴대폰 화면은 한 번 지나간다
