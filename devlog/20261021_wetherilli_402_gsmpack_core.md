# 오프라인 묶음의 굽는 고리를 패키지 `gsmpack` 으로 — 동작은 그대로 (P16 1 단계)

2026-10-21 · `feature/gsmpack-core` · wetherilli

P16 의 1 단계다. `viewer/offlinepack.py`(꼴)와 `build_offline_pack` 의 굽는 고리(어림·예산·받기·자르기·이어 굽기·빠르기)를
`tools/gsmpack/` 로 옮겼다. 명령에는 GSM 안의 소스 — KIGAM·VWorld 문과 서버 캐시 — 와 지층 면 모으기만 남았다.
**동작이 바뀌지 않는 옮기기다.** 사람이 덧붙였다 — 「이건 오프라인 묶음을 겸하니까 일단 브이월드도 같이 구워야 해」.
VWorld 는 빠지지 않았다. 명령의 `VWorldSource` 가 그대로 문으로 받고 parts 에 둔다.

## 왜 이렇게 했나

- **GSM 은 패키지를 깔지 않고 settings 가 `sys.path` 에 얹는다** — P16 은 "Docker 이미지와 CI 가 `pip install ./tools/gsmpack`" 이라 적었다.
  짜 보니 깔아야 할 자리가 넷이다 — 이미지, CI, 계정마다의 개발 venv(`~/venv/GSM`), 호스트의 전용 venv. 하나를 빠뜨리면
  `views.py` 의 import 에서 뷰어가 통째로 멈춘다. 다른 계정이 main 을 받는 날 그 venv 가 깨진다. 얹기만 하면 저장소를 받는 것으로 끝난다.
  노트북에서 혼자 쓸 때만 `pip install` 한다 — 빈 venv 에 패키지만 깔아 Django 없이 import·시험이 도는 것을 보았다
- **3857 격자 셈(`grid.tiles_for`)을 옮겨 두었다** — 패키지가 `viewer/tilegrid.py` 를 타면 혼자 돌지 못한다. 두 벌이 어긋나면 캐시 열쇠가
  어긋나므로 Django 시험(`test_offlinepack.Grid`)이 둘을 견준다. 셈은 칸 수(2^z)로만 해서 256·512 px 를 가리지 않는다
- **문의 오류는 소스가 `FetchError` 로 옮긴다** — 굽는 고리가 `PREWARM_ERRORS`·`VWorldError` 를 알면 viewer 를 타야 한다. 차단 조짐은
  문만 안다(`usage.paused()`) — 소스가 `blocked` 로 실어 넘긴다. 고리는 그것을 보고 곧장 멈춘다
- **지층 면은 함수로 넘긴다**(`bake(..., units=)`) — `unit_features` 가 `views._split_links`·`i18n.props_en` 을 써서 GSM 쪽이다. 고리는
  받은 바이트를 예산에서 먼저 떼는 일만 한다. 면 자르기·좌표 줄이기는 패키지(`clip`)에 있다
- **머리의 `gsm` 판은 `extra` 로** — 패키지는 GSM 판을 모른다. 머리의 칸 차례는 옛것 그대로다
- **parts 파일 이름과 자리는 그대로**(`.<박스>.parts.sqlite`) — 옛 명령으로 굽다 멈춘 것을 새 명령이 잇는다

## 확인한 것

- **옛 코드와 새 코드가 같은 묶음을 짓는다** — 고치기 전에 가짜 소스(시험의 `Build` 차림)로 작은 박스를 두 번(예산 넉넉·50 KB) 굽고 머리·
  타일 바이트·어림 글·마지막 줄을 떠 두었다가, 고친 뒤 같은 것을 떠 견주니 바이트까지 같았다(머리의 `built`·`gsm` 만 빼고). 견준 시험은 커밋하지 않았다
- P16 이 적은 확인은 **장성을 옛·새 명령으로 구워 머리를 견주기** 였다. 75 분 남짓 VWorld 를 수천 장 다시 부르는 일이라 하지 않았다.
  대신 **판을 붙일 때 운영에서 `build_offline_pack jangseong --dry-run` 을 배포 앞뒤로 한 번씩** 부르면 어림 글이 같아야 한다(판 세션)
- 패키지 시험 11 개(`python -m unittest discover -s tools/gsmpack/tests -t tools/gsmpack`) — 꼴·목록·자르기·예산·굽고 다시 읽기·
  차단이면 멈추고 다시 부르면 잇기·연달아 3 번 실패면 멈추기. CI 의 "뷰어 시험" 에 한 걸음 더했다
- `manage.py test viewer --parallel 8` — 2 294 개 가운데 `test_cache_headers.test_안내_타일에는_ETag_가_없다` 하나가 깨진다.
  이번 고침을 걷어 내도(stash) 이 트리에서 똑같이 깨지고, 깨끗한 main worktree 에서는 통과한다(wetherilli 401 때 본 것) — 이 트리의 환경 탓이다

## 버린 것

- **GSM 안 소스를 패키지에 두기** — 패키지가 문을 갖게 된다. 소스의 꼴만 패키지가 정하고 GSM 이 채운다(P16)
- **명령의 옛 이름(`clip_tile`·`fit_budget`·`is_blank`)을 명령에서 다시 내보내기** — 그 이름을 부르던 것은 시험뿐이라 시험을 패키지로 옮겼다
- **읽는 쪽(`offline.js`) 떼기** — 2 단계다
