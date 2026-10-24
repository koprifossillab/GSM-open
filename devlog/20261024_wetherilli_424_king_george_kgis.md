# 남극 — SCAR KGIS 킹조지섬 지형 DB 를 받아 일곱 레이어로

2026-10-24 · `feature/king-george-kgis` · wetherilli

세종기지(바턴반도)를 현장 축척으로 볼 벡터가 없었다 — 남극 탭의 지형은 REMA·ADD 정도이고 길·건물·물길이 없다.
후보는 `docs/극지_자료_후보.md` "2 차 조사" 의 3 순위(SCAR KGIS).

## 상류와 조건

PANGAEA.837976 — "Integrated topographic database for King George Island … with links to shapefiles", **License: CC BY 3.0**
(데이터셋 머리, 2026-10-24 `?format=textfile` 로 다시 읽었다). 파일은 AWI 저장소 ePIC 의 핸들 열여섯(`hdl:10013/epic.44322.d001`…`d016`)이고
`https://hdl.handle.net/…` 가 `epic.awi.de/id/eprint/36527/<n>/<이름>.zip` 으로 넘긴다. 다 합쳐 6.5 MB, .prj 는 모두 **WGS84 경위도**.

**바턴반도가 든다** — 받아 세어 보니 바턴반도 네모(58.83–58.66°W, 62.27–62.19°S) 안에 건물 43(한국 23)·등고선 159·길 19·세종기지(`AGKSG`)·
연료 탱크 6·물길 133·호수 86·착륙장 2·피난처 1. 조사 문서의 "섬 전체라고 적혀 있다" 가 맞았다.

## 무엇을 골랐나

- **문 하나 = `kgis.py`.** 받기(`fetch_kgis`, 핸들을 1 초 간격으로)와 받아 둔 zip 을 읽어 한 덩이로 내는 것을 한 파일에 두었다 — 극지연구소(`kopri.py`)처럼.
  새 상류라 파일 끝의 `REGISTRY` 만 적었다(`local: True`). 노던테리토리(`ntgeo.py`)처럼 zip 을 그대로 두고 프로세스가 옮긴 것을 든다 — 굽는 단계를 두지 않았다.
  섬 하나라 가장 큰 등고선도 2 초 안에 옮긴다(한 번 옮기면 프로세스가 든다)
- **셰이프는 GDAL 없이** — 면은 `geo3al.read_polygons`, 선은 `moonmap._read_lines`, dBASE 는 `geo3al.read_dbf`. 점(갈래 1)을 읽는 것은 없어 `kgis._read_points` 를 더했다
- **dBASE 의 글자는 UTF-8 이다** — `read_dbf` 가 latin-1 로 읽어 `Estação` 가 `EstaÃ§Ã£o` 가 된다. 되돌려 읽는다(`_text`). 공용 `read_dbf` 를 고치지 않은 것은 다른 파일들이 정말 latin-1 이어서다
- **레이어 일곱**(남극 탭, 레이어군 "킹조지섬 지형 (SCAR KGIS)") — 셰이프 열여섯을 현장에서 함께 켜는 것끼리 묶었다.
  등고선(50 m 마다 주곡선)·해안선(암석/얼음 — 빙벽을 가른다)·얼음 없는 땅·물길과 호수·기지와 시설(기지·건물·탱크·관·피난처·착륙장)·길(길·오솔길)·보호구역과 역사 유적.
  꼴은 `kopri` 의 `style: class` — 갈래마다 `code`, 덩이에 `legend`. 모양(`stroke`·`area`·`star`·`diamond`)은 화면의 `classStyle` 이 이미 그린다 — map.js 는 상류 표 한 줄만 더했다
- **지명(Placename)은 싣지 않았다** — KGIS 의 `SCAR_GAZ_I` 가 SCAR 지명사전의 번호다. 같은 사전의 새 판이 이미 남극 탭의 이름표(`scar:place_names`, wetherilli 412)라 겹쳐 뜬다
- **줄이기 0.00002°**(남북 2 m·동서 1 m) — 등고선 꼭짓점 27 만 → 15 만, 덩이 3.9 MB(gzip 1.05 MB). 0.00005° 면 2 MB 지만 1:5천에서 등고선이 각진다.
  등고선만 `render: image`(줄 2 천 4 백)
- 속성의 `ATN`·`LO_CODE` 는 `number` 로 낸다 — `code` 는 갈래(범례)의 열쇠라 덮으면 색이 사라진다(처음에 그렇게 했다가 진짜 파일에서 보였다)
- **보호구역도 실었다** — 조건은 데이터셋의 CC BY 3.0 이 덮는다(ATS/ERA 의 ASMA 판과 다른 것이다). 다만 **2007 년의 경계**라 레이어 이름·범례·설명에 2007 을 적고,
  현장에서는 남극조약사무국의 지금 관리 계획을 보라고 적었다. 2 차 조사의 2 순위(ASPA 2024·ASMA)가 붙으면 이 레이어를 내릴지 다시 본다
- 낡았다(2007) — 해안선 설명에 빙하 끝이 물러났다고 적었다

## 하지 않은 것

- 오프라인 묶음 — 벡터 덩이라 묶음이 담는 타일·지층 면과 꼴이 다르다. 세종 묶음을 다시 구울 때 따로 본다
- 정적 판 — 구운 덩이(`points/*.json`)로 실을 수 있지만 `static_site.py` 를 건드리지 않았다. 조건(CC BY 3.0)은 막지 않는다

## 확인

- 로컬 파이썬 3.14 는 `hdl.handle.net`·`epic.awi.de` 를 받지 못했다 — 연구소 망이 "KOPRI SSL" 로 다시 서명하는데 3.14 의 엄격한 X.509 검사가
  그 뿌리를 거절한다(`Missing Authority Key Identifier`). 운영 이미지는 3.12 이고 같은 망 뒤의 `data.aad.gov.au`(SCAR 지명사전)를 받으니 될 것이다.
  그래서 받기는 시험에서 `requests.get` 을 갈아 끼워 보고, 읽기는 curl 로 받은 진짜 zip 열여섯으로 보았다(덩이 일곱, 세종기지 둘레 화면 — 기지·건물·길·탱크·등고선·호수가 선다)

## 운영에서 할 일

1. 컨테이너 안에서 `docker compose exec web python manage.py fetch_kgis` — `/srv/GSM/db/kgis/` 에 zip 열여섯(6.5 MB). 한 번이면 된다.
   혹시 컨테이너에서도 인증서로 막히면 zip 을 손으로 받아 그 자리에 두어도 된다(이름은 `Building.zip` 꼴 그대로)
2. NAS `N:\GSM\sources\kgis\` 에 같은 zip 을 둔다(원본 보관)
3. 판이 뜨면 `seed_catalog` 가 레이어 일곱을 넣는다 — 남극 탭 "킹조지섬 지형 (SCAR KGIS)"
