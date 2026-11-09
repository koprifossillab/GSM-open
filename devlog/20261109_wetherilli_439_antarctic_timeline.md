# 남극 탭에 Gernon 고지형의 연대 막대 — 가벼운 판

2026-11-09 · `feature/antarctic-timeline` · wetherilli

사람이 발표에서 Gernon 외 2026 의 고지형이 100 → 34 Ma 로 바뀌는 것을 **온 지구 화면처럼 시간 축으로 이어서** 보이려 한다.
대장이 품을 재어 보였고 사람이 가벼운 판을 골랐다 — 지질시대 띠·두 장 섞기·공유 링크는 넣지 않는다.

## 레이어를 한 줄씩으로, 연대는 주소에

열 연대 × 레이어 하나(436·435)는 켜고 끄며 넘기는 길이었다. 막대 하나로 넘기려면 "어느 레이어가 연대를 따르나" 가 있어야 한다.
카탈로그 행에 `ages`(옛것부터의 연대 목록)를 달고, 타일 주소는 `polargrid/gernontopo/{age}/{z}/{x}/{y}.webp` 꼴로 낸다.
화면은 `{age}` 를 지금 연대로 바꿔 끼우고, 덩이(`points/`)는 `&age=` 를 붙인다. 연대마다의 판(`gernontopo:<연대>`)은 타일·누른 자리를
내는 속 이름으로만 남겼다 — `polargrid_tile` 이 그대로 쓰고, 카탈로그에서만 빠진다.

- 버린 길 — 서버가 "지금 연대" 를 쥐는 것(쿠키·세션). 캐시 열쇠가 주소 밖으로 나가고, 나란히 보기의 두 지도가 같은 주소로 다른 그림을 받는다
- 버린 길 — 연대마다 레이어를 두고 화면이 켜고 끄기. 패널이 34 줄이고, 켠 차례·투명도를 연대마다 따로 기억해 버린다
- 판(`?v=`)은 34 폴더의 때를 묶은 것 하나(`views._gernon_version`) — 한 연대만 다시 구워도 바뀐다. 다 굽지 않았으면 판이 없어 하루짜리로 낸다

`gernontopo.AGES` 를 34 장(100–34, 2 Myr)으로 늘렸다. 굽기는 연대마다 0–1 초라 34 장이 30 초 남짓이다.

## 등고선은 저장소 밖으로

등고선도 34 연대를 뽑으니 2.4 MB(줄 4 468)다 — 1.5 MB 를 넘어 `data/antarctic_papers.json` 에서 빼고 래스터 옆
`<GSM_GERNON_PALEOTOPO_DIR>/contours.json` 으로 옮겼다. **같은 zip 에서 같은 명령(`build_gernon_paleotopo`)이 함께 굽는다** —
원본이 하나이니 굽는 자리도 하나가 맞다. `--contours-only` 로 등고선만 다시 굽는다(14 초).

- 버린 길 — 좌표를 정수 차분으로 줄여 저장소에 남기기. 반쯤 줄어도 1.5 MB 근처이고, 읽는 쪽에 풀기를 더해야 한다
- 읽기는 래스터와 같은 `gernontopo.read_tif` 로 바꿨다 — 원점·칸을 꼬리표에서 읽어 601×601 이 아닌 작은 시험 격자도 돈다.
  옛 열 연대와 **좌표가 한 글자도 다르지 않은지** 견줬다(100·90·60·34 Ma)

`build_antarctic_papers` 는 Gernon zip 을 더 받지 않는다 — Armadillo zip 과 `--fig2a`·`--fig4a` 만. 저장소 파일은 220 KB 가 됐다.

## Fig. 4A 빙상 범위

papers-fig4a(wetherilli 440)가 그림에서 딴 열두 장(6 Myr)을 `--fig4a` 로 받아 저장소 파일에 넣는다. 화면이 2 Myr 칸으로 넘기므로
**고른 연대에서 3 Myr 안의 가장 가까운 장**을 내고, 같은 거리면 옛것이다(97 Ma → 100). 2 Myr 칸이면 늘 하나가 걸려 빈 연대는 없다 —
그래도 막대가 다른 레이어의 연대를 줄 수 있어 밖이면 비우는 규칙은 남겼다. 면은 `area` 모양(옅게 칠하고 테두리)으로 그린다.

## 화면 — map.js 에 작게

온 지구의 시간 축(`earth.js`)은 Cesium·판 회전·ICS 띠에 엮여 옮기지 않고, 말과 꼴(‹ › 단추, "더 옛날로 — 한 칸")만 빌렸다.

- **켠 레이어나 나란히 보기의 오른쪽에 `ages` 가 있을 때만** 뜬다. 여러 레이어가 있으면 연대의 합집합을 칸으로 쓰고, 레이어마다 가장
  가까운 제 연대를 낸다(지금은 셋이 같은 34 장이다)
- 막대의 값은 연대가 아니라 칸 번호다 — 끌면 2 Myr 씩 딱딱 넘는다. 왼쪽이 옛날(온 지구처럼)
- ▶ 는 0.9 초에 한 칸, 100 → 34 를 1 분 남짓에. 끝에서 누르면 처음부터. 다시 누르거나 다른 단추를 누르면 멈춘다
- 넘길 때 비지 않게 — 타일은 `setUrl` 하면 OpenLayers 가 새 타일이 올 때까지 옛 타일을 둔다. 덩이는 `source.refresh()` 가 먼저
  비워서, 옛 모양을 둔 채 새 연대를 받아 다 오면 갈아 끼운다(`gsmReload`). 재생 중에 늦게 온 옛 연대의 덩이는 버린다
- 레이어마다 지은 연대(`gsmAge`)를 적어 두어 바뀐 것만 다시 받는다 — 처음 열 때 두 번 받지 않게
- 누른 자리는 `polargrid/info/?layer=gernontopo:paleotopo&age=` — 그 연대의 고도
- 연대는 화면 기억(`stored`·`store`, `gsm.paleoage`)에 둔다. 공유 링크에는 싣지 않았다(가벼운 판)
- 3D 는 따르지 않는다 — 카탈로그 이름을 34 Ma 판에 걸어 두었다(`gernontopo.AGE_3D`). Paxman 바탕이라 오늘에 가장 가까운 판이다
- 자리는 축척 막대 위 가운데(아래 120 px) — 위는 확대 단추·손잡이 묶음, 바로 밑은 축척 막대·남쪽 끝 표·출처가 쓴다.
  휴대폰에서는 좌우를 다 쓰고 "연대" 글자를 뺀다. `test_mobile.RegionAgebar` 가 넘침·겹침·주소의 연대·재생을 본다 — 처음엔 104 px 라
  휴대폰의 축척 막대와 5 px 겹쳤다

## 옛 행 지우기

`seed_catalog` 는 씨앗에 없는 행을 지우지 않는다(넣고 손볼 뿐). 그래서 migration `0052_gernon_timeline` 이 옛 스무 행
(`gernontopo:<연대>`·`antpapers:gernon_<연대>ma`)과 빈 레이어군 "동남극 고지형 등고선 (Gernon 2026)" 을 지운다. 등고선·빙상 범위는
래스터와 같은 레이어군으로 옮겼다 — 발표하는 사람이 한 자리에서 켠다. 화면에 기억된 옛 이름은 카탈로그에 없어 조용히 빠진다.

## 운영에서

```
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_catalog
docker compose exec web python manage.py build_gernon_paleotopo /srv/GSM/db/<zip 자리>/gernon2026_zenodo_19205651_GIS_files.zip
```
(컨테이너가 뜰 때 migrate·seed_catalog 를 부르면 앞의 둘은 저절로다.) 굽기는 34 장 + 등고선이라 1 분 남짓, `/srv/GSM/db/gernon_paleotopo/`
에 0.1 MB × 34 와 `contours.json` 2.4 MB. 저장소 파일(`data/antarctic_papers.json`)은 판과 함께 간다.
