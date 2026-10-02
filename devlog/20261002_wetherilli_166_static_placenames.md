# 정적 판의 극지 지명 찾기 — 구운 지명에서 색인을, 화면이 뒤진다

2026-10-02 · `feature/static-placenames` · wetherilli

정적 판(P11)에서 스발바르·그린란드·남극(드로닝모드랜드)·북극의 찾기 칸은 서버의 `placenames/` 를 불러 돌지 않았다(165 에 남긴 것).
구운 지명 덩이(`bake_static` 의 `points/npolar/place_names.json` 따위)는 이미 정적 판에 있다.

## 색인은 굽고, 맞추기는 화면이

- `static_site.py` 가 구운 지명 덩이에서 **서버와 같은 `arcpoints.name_index`** 로 색인을 지어 `placenames/<상류>/<이름>.json` 에 둔다.
  한 줄은 `[이름들, 곁말, 위도, 경도, 앞세움]` — 그린란드 3 만 3 천 건이 2.3 MB(지명 덩이 6.2 MB 의 셋 중 하나 남짓), 스발바르 0.4 MB,
  드로닝모드랜드 0.2 MB. 지역 → 색인 주소는 `static-config.baked.placenames` 에
- 맞추기(`arcpoints.match_index`)는 map.js 의 `staticNames` 로 옮겼다 — 같은 이름·앞이 같은 것·들어 있는 것, 같으면 도시·마을, 짧은
  이름. 접기(`fold`)도 그대로(æ→ae, ø→o, å→a, ĸ→q, 덧붙임표 떼기). 정적 판과 서버 판이 같은 차례로 낸다
- 색인은 지역마다 **처음 찾을 때 한 번** 받는다. 지도를 열 때 받지 않는다 — 찾지 않는 사람이 대부분이다
- 버린 길 — 지명 덩이(GeoJSON)를 그대로 받아 화면이 색인을 짓기. 덩이가 세 배 크고, 색인 짓는 셈이 서버와 화면에 둘이 된다.
  색인을 짓는 셈은 파이썬 한 곳에 두고 맞추기만 옮겼다

## 나누기

- 같은 찾기 칸에 gsm-57 이 VWorld(한국)를 넣고 있다(#141). 미리 맞췄다 — 이쪽은 `searchNames` 안과 새 함수(`foldName`·`placeIndex`·
  `staticNames`)만, 그쪽은 `searchPlaces` 의 VWorld 줄과 `addressFor`

## 확인

- `static_site.py --baked` 로 굽고 `/GSM-open/` 꼴로 띄워 헤드리스 Chromium 으로 쳐 보았다 — 스발바르 `longyear`(Longyeardal·
  Longyearbyen …), 그린란드 `Nuuk`(도시가 맨 앞)·`Godthåb`(옛 이름으로 → "Nuuk (Godthåb)"), 남극 `Troll`, 북극 묶음 `Ny-Ålesund`
- 이 PR 은 #140(정적 판에 구운 것 잇기) 위에 쌓았다 — `staticBaked` 와 `--baked` 처리를 쓴다
