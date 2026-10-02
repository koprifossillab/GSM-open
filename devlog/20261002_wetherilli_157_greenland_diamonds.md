# 그린란드 — 다이아몬드 탐사 자료의 시추공·지시광물·석류석·탐사 구역

2026-10-02 · `feature/greenland-diamonds` · wetherilli

그린란드 정부 광물자원 포털의 다이아몬드 탐사 자료(DED)에서 산출지(089) 말고 레이어 여섯을 더 올렸다. 틀은 그대로
`grportal.py` 의 `LAYERS` 와 `arcpoints` 다 — 통째로 받아 브라우저가 그린다.

## 이용 조건 — CC BY 4.0 이 적혀 있었다

- 019 때 포털 레이어에는 이용 조건이 없었다(`licenseInfo` 가 비어 있다). **DED 의 항목들은 다르다** — 같은 글이 붙어 있다:
  "Copyright © Government of Greenland (Ministry of Mineral Resources) 2020 … provided under a Creative Commons Attribution 4.0
  International Licence", 출처는 Hutchison, M.T. (2020) *Greenland diamond exploration data package*. 시추공·탐사된 곳 두 항목만
  비어 있는데, 같은 꾸러미의 일부라 같은 조건으로 본다
- 그래서 레이어에 `license` 를 달았다(`grportal.license_of`). 화면은 출처 줄과 범례 칸의 링크에 "CC BY 4.0, Hutchison (2020)" 을
  적는다. **이미 있던 산출지(089)도 같은 조건이었다** — 함께 고쳤다

## 사용자가 고른 넷 (레이어 여섯)

| 레이어 | 서비스 | 수 | 갈래 |
|---|---|---|---|
| 시추공 | `DED_GL_DRILLHOLES` | 202 | 킴벌라이트를 만났다(138)·못 만났다(63)·보고 없음(1) |
| 지시광물 농도 | `DED_GL_thm_BA_ind_inds_per_kg` | 1 048 | 낟알/kg — 100 넘게·10–100·1–10·1 밑 |
| 다이아몬드 농도 | `DED_GL_thm_BA_ind_dia_per_kg` | 178 | 개/kg — 1 넘게·0.25–1·0.05–0.25·0.05 밑 |
| 석류석 분류 | `DED_GL_thm_BA_ind_chemGT` | 2 468 | G10D 있음(558)·G10 있음(699)·G9 만(723)·그 밖(488) |
| 탐사된 곳 | `DED_GL_Explored_Polygons` | 면 1 (조각 7 874) | — |
| 탐사되지 않은 곳 | `DED_GL_Unexplored_Polygons` | 면 1 (조각 2 376) | — |

- **농도는 값의 구간으로 가른다.** `class_of` 는 받은 글의 머리말로만 갈랐다. `numeric` 갈래를 더해 `(이상, 미만)` 구간을 받게
  했다. 구간은 값의 분포(지시광물 가운데값 3, 위 10% 120, 최댓값 13 만)를 보고 10 배씩 끊었다
- **석류석은 열 여럿을 보고 가른다.** G10D(다이아몬드 안정역의 하즈버자이트질)가 하나라도 있으면 맨 위, 다음 G10, 다음 G9 만.
  탐사에서 보는 차례가 그렇다. 갈래 머리에 함수를 둘 수 있게 했다 — 캐시 열쇠(`signature`)에는 들지 않아 색을 바꿔도 다시
  받지 않는다
- **함정 — `Not_Reported` 도 `No` 로 시작한다.** 머리말로 가르면 "보고 없음" 이 "만나지 못했다" 에 섞인다. 보고 없음을 먼저 둔다
- **탐사 구역 면은 속성을 받지 않는다.** 면 하나에 붙은 값이 첫 시료의 것과 원본 셰이프 경로라 뜻이 없다. 0.02° 로 줄여
  714 KB·244 KB — 0.005° 면 1.1 MB 였다
- 단사휘석·티탄철석·첨정석·사방휘석 분류와 거둔 다이아몬드(macro·micro), 연대는 사용자가 고르지 않았다 — TODOs 에 남긴다

## 확인

- 상류에서 여섯을 다 받아 갈래별 수를 보았다(위 표). 임시 서버와 헤드리스 Chromium 으로 그린란드 탭에 켜 보았다
- `test_grportal` 에 구간·함수 갈래·보고 없음·이용 조건 시험을 더했다
