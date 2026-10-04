# 그린란드 — 공중 자력 셋, 지질도 1:250만·1:10만 둘 (GEUS ArcGIS)

2026-10-05 · `feature/greenland-more-2` · wetherilli

wetherilli 259 가 남긴 것 — 같은 GEUS ArcGIS(`data.geus.dk/arcgis/rest/services/Greenland`)에 있는 공중 자력과 지질도를 더했다. 문은 그대로
`geus.py` 의 ARC(상류 `geusarc`)이고, 표(`ARC_LAYERS`)에 줄을 더하는 것으로 끝났다. 조건도 같다 — GEUS 이용 조건(개인 용도, 다시 펴내려면 서면 동의)이라
**정적 판에 싣지 않는다**.

## 더한 것 (3413 export 한 장, 2026-10-05)

| 레이어 | 서비스·REST 레이어 | 한 장 | 덮는 곳 |
|---|---|---:|---|
| 공중 자력 AEROMAG 1992–2013 | `Geophysics_Aeromag_Magnetic` 0 | 1.6 초 | 서남부 조사 구역 |
| 공중 자력 기울기 도함수 | 같은 서비스 2 | 1.5 초 | 같은 곳 — 구조선이 잘 보인다 |
| 공중 자력 AWI 1993–96 | `Geophysics_Aeromag_AWI` 2 | 1.3 초 | 동부 해안 |
| 헬기 자력 조사 (국지) | `Geophysics_Aem_Magnetic` 1–10 | 2.3 초 | 열 곳의 작은 조각 |
| 지질도 1:250만 | `Geological_map_2500k` 4·2·1 | 3.9 초 | 섬 전체 |
| 서남부 지질도 1:10만 | `Geological_map_100k_SSW` 5·3·0 | 12.9 초 | 서남부 |
| 카라트 지질도 1:10만 | `Geological_map_100k_Karrat` 17·13·10 | 2.4 초 | 카라트 |

- TODOs 가 `Geophysics_Aeromag_Magnetic_AWI` 로 적었던 서비스의 이름은 `Geophysics_Aeromag_AWI` 다. 그 안의 0 은 측선이라 빼고, 색 척도 둘(400–500·300–600 nT)
  가운데 넓은 쪽을 골랐다. AEROMAG 의 Z 도함수(1)는 기울기 도함수와 겹쳐 두지 않았다
- 지질도는 면·경계·구조선을 함께 그리고 글자(`trends_TEXT`)·지명·등고선·하천은 뺐다. **누르면 면에만 묻는다**(`ARC_QUERY`) — 경계·구조선까지 물으면 면 대신 선이 먼저 온다
- 속성 열이 판마다 다르다(1:250만 `Description`, 서남부 `Legend_Heading`·`Description`, 카라트 `gm_unit_name`·`short_description`) — `arc_friendly` 가 기호·단위·설명
  세 줄로 모은다
- **지질도는 목록 범례**(`views.list_legend`, 78·195·79 칸) — REST `legend` 를 그 면 레이어의 것만 받아 30 일 담는다. 지구물리는 REST 범례가 래스터의 RGB 띠 이름
  (`Red: Band_1`)뿐이라 범례를 두지 않았다
- 서남부 1:10만은 넓게 보면 한 장이 13 초다. 메타타일 표(wetherilli 287)에 넣을지는 운영의 응답 시간(`upstream_stats`)을 보고 정한다 — 화면이 3413 이라
  지금의 메타타일(3857 격자만)로는 받을 수 없기도 하다

## 버린 것

- 1:50만 `Geological_map_500k` — 이미 GEUS WMS 의 50만 지질도(추린 판)가 있다. 같은 판의 다른 길이라 두지 않았다. 원본을 여는지는 사람이 GEUS 에 묻는 일(TODOs)
- 방사능 `Geophysics_Radiometry` — 국지 조사 몇 곳뿐이다(259)
- 카라트의 광물 산지(`Mineral_occurences`) — 그린란드 포털(grportal)의 광물 산지 레이어가 이미 있어 두지 않았다
