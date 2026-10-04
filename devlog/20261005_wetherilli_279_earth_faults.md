# 온 지구 — 세계 활성단층 (GEM Global Active Faults)

2026-10-05 · `feature/earth-faults` · wetherilli

판 세션이 준 일 — GEM Global Active Faults 를 활성단층 선으로. 판 경계(272)·응력(273)과 같은 "구조" 주제.

## 자료와 조건

GitHub `GEMScienceTools/gem-global-active-faults` 의 `geojson/gem_active_faults_harmonized.geojson`(10 MB, 13 696 줄, Styron & Pagani 2020).
**CC BY-SA 4.0** — 저장소의 `LICENSE.txt`. NAS `sources/earth/gem_faults/` 에 GeoJSON·LICENSE·SHA256SUMS 를 두었다.

- **같은 조건으로 나눠야 한다(SA).** 구운 파일과 그 타일도 CC BY-SA 4.0 이다 — 굽는 파일의 머리와 화면의 출처에 그렇게 적었다.
  코드는 AGPL 이고 자료의 조건은 자료에만 걸린다(CLAUDE.md "라이선스")
- `harmonized` 판을 골랐다 — 목록마다 다른 속성 이름을 GEM 이 맞춰 둔 판이다. 다른 판(`gem_active_faults.geojson`)은 원 목록의 열이 그대로다

## 담는 꼴 — 저장소 밖

판 경계(1.3 MB)처럼 `data/` 에 두려 했는데 0.01° 로 줄여도 2.6 MB 였다 — 좌표보다 속성(목록 이름·세 값 글)이 무겁다. CLAUDE.md 대로 크면
`<EARTH_DIR>` 에 둔다(`earth_faults.json`, 2.9 MB). 저장소 밖에 두니 좌표를 0.001° 로 되돌려 줌 8 에서도 꺾임이 산다.

- 미끄럼 갈래(`slip_type`) 스물 남짓을 여섯으로 — 정단층 빨강·역단층과 섭입 파랑·주향이동과 변환 초록·사교 주황·확장 해령 회색·습곡과
  모름 점선. 해령은 PB2002 를 옮긴 줄(`catalog_name` "Bird 2003")이라 판 경계와 겹친다 — 옅게 먼저 긋는다
- 세 값 `(가장 그럴듯한, 최소, 최대)` 을 `8.29 (6.52–9.77)` 로 푼다. 원본이 float32 를 글로 적어 `11.1000003814697` 이 섞여 있어 넷째 자리에서 끊는다
- 누르면 그 줌의 8 화소 안의 가장 가까운 단층 하나(선분까지의 거리, 경도는 cos 위도로 줄여 잰다) — 이름·갈래·원문 미끄럼·경사·경사
  방향·레이크·미끄럼 속도·지진 발생 깊이·원 목록. 헤이워드 단층 → 우수향, 8.29 mm/yr
- 판·지질구 레이어군 안에 판 경계 다음으로 선다(그 레이어군이 없으면 따로)

## 운영 메모

- 배포 뒤 한 번: `manage.py build_faults /nfs/temp-share/GSM/sources/earth/gem_faults/gem_active_faults_harmonized.geojson` →
  `/srv/GSM/db/earth/earth_faults.json`
- 정적 판에는 싣지 않았다 — SA 조건이라 실을 때 출처 표기와 함께 조건을 다시 본다
