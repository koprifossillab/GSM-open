# 미국 — 네바다·워싱턴·오리건 주 지질도

2026-10-05 · `feature/us-states` · wetherilli

캘리포니아(wetherilli 231)와 같은 꼴로 주 지질도를 미국 탭(3978)에 더했다. 문은 하나(`usstates.py`)에 셋 — 호주 주 판(225)과 같다.

| 상류 | 판 | 한 장(주 전체 400²) |
|---|---|---|
| `nbmg` | 네바다 1:50만 (Stewart & Carlson, USGIN) | 1.2 초 |
| `wadnr` | 워싱턴 1:50만 (2022) · 1:10만 GeMS (2026) | 1.8 초 · 8.2 초 → 줌 8 부터 |
| `dogami` | 오리건 OGDC-6 | 10.8 초 → 줌 7 부터 |

## 왜 이렇게

- **문 하나에 셋** — 셋 다 ArcGIS REST `export`·`identify` 를 같은 꼴로 부른다. 화면의 WMS 변수 옮기기는 `arcwms.rest_*`(wetherilli 280)를
  그대로 쓴다. 상류 이름은 셋(`nbmg`·`wadnr`·`dogami`)이라 쓰임 기록·조건이 주마다 갈린다
- **주 밖 칸은 묻지 않는다** — 카탈로그 행의 `clip`(하와이·푸에르토리코, 238)이 레이어 범위 밖을 거른다. 미국 탭을 넓게 볼 때 상류 셋에 빈 칸을
  묻지 않는다
- 네바다는 WMS 도 있지만 셋을 한 길로 두려고 REST 로 부른다
- **범례는 REST 목록**(54–101 칸)인데 칸 이름이 기호뿐인 곳이 있다 — 워싱턴 1:50만은 GeMS 의 단위 설명 표(표 5)를, 네바다는 면의 값을 모아
  (`returnDistinctValues`) 기호 → 이름·시대를 붙인다. 30 일 담는다
- identify 는 열 **별칭**(`Unit Symbol`·`Geologic History`)으로 준다 — 열 이름이 아니다
- 시대는 영어(오리건 `Eocene/Oligocene`)라 `i18n.age_tidy` → `age_ko`

## 버린 것

- **유타 UGS·애리조나 AZGS** — 주소는 찾았지만(`webmaps.geology.utah.gov`·`services.azgs.az.gov`) 이 서버에서 TCP 연결이 30 초 시간 초과다.
  나라 밖을 막는 것으로 본다. TODOs
- **알래스카 DGGS** — 주 지질도는 USGS SIM 3340(`mrdata:sim3340`)이 이미 덮는다. DGGS 의 `geologic_maps` 는 스캔 모자이크(ImageServer)다
- 워싱턴 1:2.5만·1:2.5–9.9만(`site3/Geology`)은 덮는 곳이 조각이라 뒤로 미뤘다

## 확인

- 사본 DB: 네바다 Qa(제4기), 워싱턴 Tc(Tertiary continental sedimentary rocks · 제3기 · 설명), 1:10만 Ec(1s), 오리건 Tc(Clarno Formation · 에오세~올리고세).
  타일 0.7–2.1 초, 범례 54·101 칸
