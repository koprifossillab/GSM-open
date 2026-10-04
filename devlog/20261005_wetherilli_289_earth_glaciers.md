# 온 지구 — 세계 빙하 (RGI 7.0)

2026-10-05 · `feature/earth-glaciers` · wetherilli

판 세션이 준 일 — Randolph Glacier Inventory 7.0(CC BY 4.0) 빙하 윤곽을 오늘 레이어로. 크면 줄여 `<EARTH_DIR>` 에. Natural Earth 빙하(102)와
겹치지 않게 줌으로 가른다.

## 윤곽은 받지 못했다 — 속성 표로 점을

RGI 7.0 의 정본은 NSIDC-0770 이다. 그런데 NSIDC 의 내려받기(`daacdata.apps.nsidc.org/pub/DATASETS/nsidc0770_rgi_v7/`)는 **NASA Earthdata 로그인**으로
돌려보낸다 — 계정은 사람이 만들 일이다. 찾아본 다른 길:

| 길 | 있는 것 | 판단 |
|---|---|---|
| NSIDC | 윤곽(셰이프)·속성 | Earthdata 로그인 — TODOs (사람) |
| OGGM 거울(브레멘대 `~oggm/rgi/`) | **RGI 7.0 빙하 속성 표**(`RGI2000-v7.0-G-global-attributes.csv`, 27 만 줄)·지역 경계 | **씀** — 같은 판의 정본 파일을 그대로 올린 것 |
| 같은 거울의 `rgi60_files/` | RGI 6.0 윤곽 414 MB | 쓰지 않음 — 일은 7.0 이고, 6.0 을 7.0 처럼 보이게 하면 헷갈린다 |

RGI 누리집(glims.org/RGI)이 CC BY 4.0 을 적는다. 속성 표에는 빙하마다 가운데(`cenlon`·`cenlat`)·넓이·높이·경사·끝의 갈래·서지가 들어 있어,
**넓이만 한 원**을 찍으면 가까이서 큰 빙하는 제 크기로, 작은 빙하는 한 점으로 선다. 윤곽이 들어오면 같은 레이어를 면으로 바꾸면 된다.

## 굽고 그리기

`glaciers.py` 가 `<EARTH_DIR>/glaciers.sqlite`(51 MB, 5 초) — 지열류(267)·지진과 같은 꼴이다.

- **줌 3 부터 그린다** — 서버가 그 밑은 빈 타일을 낸다(화면에 레이어마다 가장 낮은 줌을 둘 칸이 없다). 그 밑은 Natural Earth 의 빙하·빙붕이 맡는다고
  범례에 적었다. 27 만 점을 온 지구 한 장에 찍으면 산맥이 파랗게 덮일 뿐이다
- 원은 경위도 격자의 늘림을 따른 타원(경도 반지름 = 위도 반지름 / cos 위도) — 화면이 다시 펴면 둥글다
- **끝의 갈래는 바다만** — RGI 7.0 은 `term_type` 을 바다로 끝나는 빙하(1, 1 561 개)에만 적고 나머지는 9(가리지 않음)다. 땅·호수·빙붕 갈래는 6.0
  에만 있다. 그래서 범례는 둘뿐이다(조수 빙하를 진하게)
- **누르면 큰 빙하가 먼저** — 처음엔 가운데가 가까운 것부터 골라, 허버드 빙하 위를 눌러도 둘레의 작은 빙하가 떴다. 넓이의 원이 누른 자리를 품는
  빙하를 큰 것부터 앞에 둔다
- 이름이 있는 것은 5 만 8 천 — 끝에 쉼표가 붙은 이름(`Thurston I 001,`)이 있어 뗀다

## 운영 메모

- 배포 뒤 한 번: `manage.py build_glaciers /nfs/temp-share/GSM/sources/earth/rgi7/RGI2000-v7.0-G-global-attributes.csv` →
  `/srv/GSM/db/earth/glaciers.sqlite`
- #276(화석 밀도) 위에 쌓았다
