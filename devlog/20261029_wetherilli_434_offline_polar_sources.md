# 극지 묶음의 소스 둘 — 세종에 킹조지섬 KGIS 덩이, 다산에 NPI 스발바르 배경

2026-10-29 · `feature/offline-polar-sources` · wetherilli

P17(남극 묶음)·411(남극 소스) 다음 일이다. 424(킹조지섬 KGIS)와 425(스발바르 FKB)가 "묶음에는 아직" 으로 남긴 것을 묶음이 담게 했다.
**굽기는 하지 않았다** — 운영에서 할 일로 적는다(아래).

## 1. 점·모양 덩이 — 꼴에 `vectors` 칸을 더했다

KGIS 일곱 레이어(등고선·해안선·얼음 없는 땅·물길과 호수·기지와 시설·길·보호구역)는 타일이 아니라 `kind: points` — 화면이 `points/?layer=` 의
GeoJSON 한 덩이를 받아 그린다. 묶음의 타일 칸(`<레이어>/z/x/y`)에도, 누른 자리의 지층 면(`@units/`)에도 맞지 않는다.

- **머리에 `vectors.<레이어>` 칸, 바이트는 `@vectors/<레이어>`** — 지층 면과 같은 꼴이다. 덩이는 서버가 화면에 주는 것 **그대로**(`legend`·`labels`·
  `style` 칸까지)에서 박스에 닿는 모양만 남긴다(`bake.clip_vector`). 화면의 그리는 손(`pointLayerFor`)이 범례·갈래 색을 그 칸에서 읽으므로
  덩이를 다시 짓지 않았다
- **모양은 자르지 않는다** — 네모가 박스에 닿으면 통째로 둔다. 등고선 한 줄을 박스 테두리에서 끊으면 선 끝이 박스 둘레에 줄지어 선다.
  타일·지층 면은 자르지만(385) 그것은 "어디까지가 묶음인가" 를 보이려는 것이고, 덩이는 망이 있을 때와 같은 그림이 낫다
- 꼴의 판(`GSMPACK1`)은 올리지 않았다 — 칸이 늘 뿐이고 옛 묶음은 그대로 읽힌다. 명세(README)·쓰기(`bake.py`)·읽기(`gsmpack-reader.js` 의
  `hasVector`·`readVector`)를 같은 커밋에서 맞췄다
- 화면은 그 레이어를 **망보다 묶음에서 먼저** 읽는다(`GSMOffline.vector`) — 타일이 묶음 먼저인 것과 같다. 덮는 묶음이 없으면 저장소를 기다리지
  않고 곧장 망으로 간다. "덮는 레이어" 기억(`gsm.offline.layers`)에 덩이 이름도 넣었다 — 저장소가 열리기 전에도 기다릴지 안다
- 덩이는 예산에서 먼저 뗀다(지층 면과 같다). KGIS 는 우리 파일이라 상류를 타지 않는다
- 세종 박스에 `vectors` 로 일곱을 적었다. 지금은 KGIS 만 받는다 — 다른 점 레이어(GTN-P·PetroChron 따위)는 덩이를 짓는 손이 레이어마다 달라
  `gather_vectors` 에 한 갈래씩 더한다

## 2. NPI 스발바르 배경 — 25833 격자

NPI 지형도·위성은 **25833(UTM 33N)** 격자다(원점 (−5 120 900, 9 998 100), 256 px, 줌 0 이 21 674.71 m/px). 정주지 상세도 FKB 는 3857.

- 패키지 격자에 `NPI_SVALBARD`("EPSG:25833")를 더했다. 투영은 크뤼거 급수(여섯 차)를 옮겼다 — `viewer/crs.latlon_to_utm` 과 뉘올레순에서 mm 안이다.
  패키지는 viewer 를 타지 않으니 셈을 옮겨 둔다(3031 때와 같다)
- 격자 이름 — 화면의 25833 은 proj4 정의뿐이라 투영 범위가 없다. 그래서 `offline.js` 의 `gridName` 이 원점을 붙이지 않고 `EPSG:25833` 을 낸다.
  패키지도 그 이름으로 적는다
- 서버의 소스(`NpiSource`)는 **화면과 같은 캐시 열쇠**(`npi-tile`)로 꺼내고, 없으면 문(`basemaps.npi_tile`)으로 받아 담는다 — CC BY 라 서버가 담는
  배경이다(200·425). REMA 처럼 parts 에만 두지 않는다
- **FKB 는 정주지 네모만 묻는다**(`FKB_SETTLEMENTS` — 뉘올레순). 상류는 정주지 밖 칸을 404 로 준다. 다산 박스(콩스피오르, 한 변 30 km)를 통째로 세면
  줌 17 에서 빈 칸을 수만 번 묻는다 — 남극 기지 위성의 `THEME_BBOX` 와 같은 까닭이다
- 화면은 `npiTiles`·`npiFkbLayer` 의 소스를 `offlineWrap` 으로 감싼다(`NPI_PACK`). 묶음이 없으면 지금과 같다
- 어림(`GUESS_BYTES`)의 NPI 값은 **재지 않은 짐작**이다 — 425 에서 본 지형도 한 장 15 KB 가 근거의 전부다. 구우면 잰 값으로 바꾼다

## 다산 박스

`dasan` — [11.3, 78.8, 12.7, 79.05], 뉘올레순과 콩스피오르·콩스베그·크로네브린 빙하. NPI 지형도(25833 줌 5–13, 줌 13 이 2.6 m/px)·FKB(3857 줌 12–17)·
위성(줌 5–12). **배경만이다** — NPI 지질도(1:10만·25만)는 서버의 `npolar` 문이 3413 `export` 로 받는 길이라 아직 묶음 소스가 아니다.
다산 묶음이 쓸모 있으려면 그것이 다음 일이다(TODOs 에 적을 것).

## 확인

- gsmpack 시험(45, node 로 읽는 쪽까지) — 덩이 쓰기·읽기·박스로 고르기, 25833 격자
- viewer `test_offlinepack` — NPI 소스가 화면의 열쇠로 담는지, FKB 가 정주지 밖을 묻지 않는지, KGIS 덩이가 박스 밖 모양을 빼는지
- 휴대폰(브라우저) 시험은 더하지 않았다 — 덩이를 묶음에서 그리는 것은 `pointLayerFor` 의 받는 길 하나만 바뀌었다. 구운 묶음으로 폰에서 본다(스킬의 절차)

## 운영에서 할 일 (`.claude/skills/offline-pack` 절차)

```sh
# 세종 — KGIS 를 받아 두었는지 먼저(424 의 fetch_kgis). 그다음 다시 굽는다
docker compose exec web python manage.py build_offline_pack sejong --dry-run
docker compose exec web python manage.py build_offline_pack sejong
# 다산 — 처음 굽는다. 어림을 보고 예산(200 MB)에 맞는지 본 뒤
docker compose exec web python manage.py build_offline_pack dasan --dry-run
docker compose exec web python manage.py build_offline_pack dasan
```

구운 뒤 `gsmpack info` 로 레이어마다 장수·`vectors` 를 보고, 다산의 잰 크기로 `GUESS_BYTES` 의 NPI 값을 바꾼다. 범위는 사람이 보고 정한다(P17 3 단계).
