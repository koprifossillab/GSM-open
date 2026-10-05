# devlog 색인

그때의 판단과 근거를 적는다 — 규약은 [CLAUDE.md](../CLAUDE.md) "devlog". **새 파일은 이 표에 한 줄씩 더한다.**

## 파일 이름

2026-09-30 부터 글쓴이마다 번호를 따로 센다(WegenersDream 과 같은 꼴):

- 한 작업: `devlog/YYYYMMDD_{author}_{nnn}_{title}.md`
- 계획: `devlog/YYYYMMDD_{author}_P{nn}_{title}.md`
- `author` 는 GitHub 계정 이름(소문자). 이 서버의 Linux 계정마다 GitHub 계정이 하나다(`whoami` 로 본다):

  | Linux 계정 | GitHub 계정(`author`) |
  |---|---|
  | paleoadmin | `koprifossillab` |
  | jikhanjung | `jikhanjung` |
  | sclee | `wetherilli` |
  | jschoi | `tupandactyl` |

- `title` 은 영어 snake_case
- 번호는 **그 글쓴이의 다음 번호**다(저장소의 다음 번호가 아니다). 옛 꼴 001~077·P01~P05 는 sclee 계정이 적었으므로
  `wetherilli` 는 **078**·**P06** 부터, 다른 사람은 001·P01 부터
- **옛 꼴(`YYYYMMDD_NNN_slug.md`)은 이름을 바꾸지 않는다.** 가리킬 때는 번호만("devlog 017", "(017)")
- 새 꼴은 링크나 "jikhanjung 001" 로 가리킨다. 커밋 메시지 끝도 `(jikhanjung 001)`
- 머리줄 아래에 `날짜 · \`브랜치\` · 글쓴이` 를 적는다

## 목록

| devlog | 날짜 | 제목 |
|---|---|---|
| 001 | 2026-09-23 | [상류 오픈API 를 훑는다](20260923_001_kigam-openapi-survey.md) |
| 002 | 2026-09-23 | [옆 저장소의 지질도 캐시를 가져올까](20260923_002_phyloserver-tile-cache.md) |
| 003 | 2026-09-23 | [배경지도를 무엇으로 깔까](20260923_003_basemap.md) |
| 004 | 2026-09-23 | [VWorld 로 더 할 수 있는 것](20260923_004_vworld-api.md) |
| 005 | 2026-09-23 | [손질이 안 뜬 까닭, 그리고 로고](20260923_005_cache-and-brand.md) |
| 006 | 2026-09-27 | [인증키가 왔다. 타일은 열려 있고 속성은 닫혀 있었다](20260927_006_openapi-key.md) |
| 007 | 2026-09-27 | [받은 것은 계속 보탠다](20260927_007_keep-everything.md) |
| 008 | 2026-09-27 | [영어판](20260927_008_english.md) |
| 009 | 2026-09-27 | [주소·장소로 찾기](20260927_009_address-search.md) |
| 010 | 2026-09-27 | [호출 제한은 재지 않는다, 미리 데우기는 천천히 크게](20260927_010_rate-and-prewarm.md) |
| 011 | 2026-09-27 | [주제도 비교](20260927_011_compare.md) |
| 012 | 2026-09-27 | [선·면도 받는다](20260927_012_shapes.md) |
| 013 | 2026-09-27 | [좌표계를 고른다](20260927_013_crs.md) |
| 014 | 2026-09-27 | [지운 점묶음을 적어 두고 되살린다](20260927_014_deletion-log.md) |
| 015 | 2026-09-27 | [3D 실험: VWorld 가 아니라 MapLibre 로](20260927_015_3d-experiment.md) |
| 016 | 2026-09-27 | [지역을 나눈다: 한국·그린란드·남극](20260927_016_regions.md) |
| 017 | 2026-09-27 | [극지는 극에서 본다: 3413·3031 화면과 극지 배경](20260927_017_polar-projections.md) |
| 018 | 2026-09-27 | [남극 지질도: GeoMAP 을 우리가 그린다](20260927_018_geomap.md) |
| 019 | 2026-09-27 | [그린란드 정부 포털의 점을 레이어로: 시료·연대·광물 산출지](20260927_019_greenland-portal.md) |
| 020 | 2026-09-27 | ["지질 참고": VWorld WMS 와 단층 벡터](20260927_020_vworld-reference.md) |
| 021 | 2026-09-27 | [스발바르와 북극: 노르웨이 극지연구소 지도 서버를 3413 으로 중계한다](20260927_021_svalbard.md) |
| 022 | 2026-09-27 | [얀마옌: NPI 지질도를 모양째 받아 우리가 그린다](20260927_022_jan-mayen.md) |
| P01 | 2026-09-27 | [스발바르 — 노르웨이 극지연구소(NPI) 자료로 지역 하나를 더한다 (계획)](20260927_P01_svalbard.md) |
| P02 | 2026-09-27 | [3D 에 점묶음을 얹는다 (계획)](20260927_P02_3d-pointsets.md) |
| P03 | 2026-09-27 | [시료 고도 붙이기 — 표고 타일에서 점마다 고도를 읽는다 (계획)](20260927_P03_sample-elevation.md) |
| 023 | 2026-09-28 | [v0.7.0 을 합치고 올리며 정한 것](20260928_023_v0.7-merge-and-deploy.md) |
| 024 | 2026-09-28 | [일본, 그리고 동아시아: GSJ 심리스 지질도를 타일째 중계한다](20260928_024_japan.md) |
| 025 | 2026-09-28 | [중국: USGS geo3al 을 모양째 얹는다 (연구실 내부용)](20260928_025_china-geo3al.md) |
| 026 | 2026-09-28 | [연구실의 암맥 기록과 한반도 지질도를 싣는다](20260928_026_phyloserver-dikes.md) |
| 027 | 2026-09-28 | [한반도 지질도 음영판: 좌표가 박힌 PDF, 그리고 그 좌표를 고쳐 쓴 까닭](20260928_027_peninsula-shaded.md) |
| 028 | 2026-09-28 | [한반도 지질도 민판: 월드파일이 붙어 왔는데 또 고쳐 쓴 까닭](20260928_028_peninsula-plain.md) |
| 029 | 2026-09-28 | [v0.10 묶음: 품 S 일곱, 미리 데우기 넓히기, 절 이름, 3D 점묶음, 그림 내려받기, 스발바르 도폭](20260928_029_v0.10-batch.md) |
| P04 | 2026-09-28 | [GLiM — 전 지구 암상도를 얹는다 (계획)](20260928_P04_glim.md) |
| 030 | 2026-09-29 | [3D 에 커스텀 지질도: 5179·5181 격자를 서버가 3857 로 다시 편다](20260929_030_3d-custom-layers.md) |
| 031 | 2026-09-29 | [시료 고도(P03)와 3D 의 일본 지형: 표고 상류 셋, 그리고 극지가 쉬워진 까닭](20260929_031_elevation.md) |
| 032 | 2026-09-29 | [북극의 3D: PGC ArcticDEM 을 3857 로 옮겨, 스발바르·그린란드를 3D 로 본다](20260929_032_polar-3d.md) |
| 033 | 2026-09-29 | [VWorld 배경지도를 곧장 받지 못하면 서버를 거친다: 사내 VPN 이 끊는다](20260929_033_vworld-relay.md) |
| 034 | 2026-09-29 | [스발바르 3D: 디코드 오류, 느린 로딩, 한국 테마](20260929_034_polar-3d-speed.md) |
| 035 | 2026-09-29 | [남극도 3D 를 연다, GLiM 벡터의 이용 조건](20260929_035_antarctic-3d-glim-terms.md) |
| 036 | 2026-09-29 | [달 — 둥근 달에 지질도를 얹는다](20260929_036_moon.md) |
| 037 | 2026-09-29 | [달 점묶음 — 몸을 가른다](20260929_037_moon-pointsets.md) |
| 038 | 2026-09-29 | [달 — 2D 의 틀로, 가까이 가면 평면으로](20260929_038_moon-flat.md) |
| 039 | 2026-09-29 | [달 지질도 원도 6 장을 얹는다](20260929_039_moon-originals.md) |
| 040 | 2026-09-29 | [남극 고해상 위성 배경, 남극 3D 에 GeoMAP](20260929_040_antarctic-imagery-geomap-3d.md) |
| 041 | 2026-09-29 | [달 — 도구와 자세, 누른 자리의 표, 자전축](20260929_041_moon-tools.md) |
| 042 | 2026-09-29 | [달 — 배경 영상 보정](20260929_042_moon-image-tune.md) |
| 043 | 2026-09-29 | [달 고해상 배경 — WAC 위에 Kaguya 지형 카메라](20260929_043_moon-kaguya-imagery.md) |
| 044 | 2026-09-29 | [달 — 범례를 지질시대별 상자로](20260929_044_moon-legend-ages.md) |
| 045 | 2026-09-29 | [달 — 기울여 보기: 가운데 점·거리·방위·기울기, 그리고 자전축을 한 막대로](20260929_045_moon-pose.md) |
| 046 | 2026-09-29 | [달 — 착륙지 레이어군](20260929_046_moon-landing-sites.md) |
| 047 | 2026-09-29 | [남극 배경에 IBCSO v2 — 해저·빙저 지형](20260929_047_ibcso.md) |
| 048 | 2026-09-29 | [달 — 그림으로 내려받기](20260929_048_moon-export.md) |
| 049 | 2026-09-29 | [남극 탭 — 장보고·세종 기지로 바로 가는 "자세" 묶음](20260929_049_antarctic-stations.md) |
| 050 | 2026-09-29 | [3D — 극지에서 넓게 열고, 레이어 목록은 지역을 따른다](20260929_050_3d-polar-range-and-regions.md) |
| 051 | 2026-09-29 | [3D 남극 — IBCSO 를 배경과 지형으로](20260929_051_3d-ibcso.md) |
| 052 | 2026-09-29 | [달 — 극 평사도법 평면](20260929_052_moon-polar-flat.md) |
| 053 | 2026-09-29 | [극지연구소 암석 시료 — 새 문 `kopri.py`](20260929_053_kopri-rock-samples.md) |
| 054 | 2026-09-29 | [남극 기지 — KPDC 지도 서버의 COMNAP 시설](20260929_054_antarctic-stations.md) |
| 055 | 2026-09-29 | [KPDC 자료의 위치 — 주제마다 한 레이어](20260929_055_kpdc-datasets.md) |
| 056 | 2026-09-29 | [운석 발견 지점 — KPDC 의 KoreaMet](20260929_056_meteorites.md) |
| 057 | 2026-09-29 | [KPDC 지도 서버의 WMS — 해안선 변화·호수·하천·빙퇴석](20260929_057_kpdc-wms.md) |
| 058 | 2026-09-29 | [화성 — 달 화면을 옮겨 짓고, 달·화성에 제 아이콘과 대기 화면](20260929_058_mars.md) |
| 059 | 2026-09-29 | [3D — 실험을 벗는다](20260929_059_3d-graduates.md) |
| P05 | 2026-09-29 | [달 — 둥근 달로 들어가 평면에서 일한다 (계획)](20260929_P05_moon.md) |
| 060 | 2026-09-30 | [NASA Trek 판 목록 — 달·화성이 함께 쓰는 틀](20260930_060_trek-catalog.md) |
| 065 | 2026-09-30 | [화성 — 극 평사도법 평면](20260930_065_mars-polar-flat.md) |
| 066 | 2026-09-30 | [화성 — 주룽(祝融) 착륙 지점과 주행 경로](20260930_066_zhurong.md) |
| 067 | 2026-09-30 | [화성 — 크레이터 38 만 개 (Robbins & Hynek 2012)](20260930_067_mars-craters.md) |
| 068 | 2026-09-30 | [화성 — 옛 지질도 (USGS I-1802-A·B·C, 1986–87)](20260930_068_mars-originals.md) |
| 070 | 2026-09-30 | [누른 자리의 수심·표고 — IBCSO 수치 격자에서 읽는다](20260930_070_ibcso-depth.md) |
| 071 | 2026-09-30 | [IBCSO 자료 출처(TID) 레이어 — 잰 곳과 메운 곳](20260930_071_ibcso-tid.md) |
| 072 | 2026-09-30 | [GeoMAP 암층 — 무늬 채우기를 옮겼다](20260930_072_geomap-lithostrat.md) |
| 073 | 2026-09-30 | [KPDC 지도 서버 속성의 이름](20260930_073_kpdc-wms-props.md) |
| 074 | 2026-09-30 | [시료 지점에 VWorld 둘레를 붙인다](20260930_074_pointset-vworld-places.md) |
| 075 | 2026-09-30 | [KPDC 자료의 북극 — 스발바르·그린란드 탭에](20260930_075_kpdc-arctic.md) |
| 076 | 2026-09-30 | [북극해 탭 — KPDC 북극 자료의 나머지](20260930_076_arctic-ocean-tab.md) |
| 077 | 2026-09-30 | [VWorld 벡터의 칸을 레이어마다 — 지하수 등수심선](20260930_077_vworld-vector-cells.md) |
| jikhanjung 001 | 2026-09-30 | [화면 투영의 EPSG 번호를 축척 막대 옆에](20260930_jikhanjung_001_epsg_badge.md) |
| jikhanjung 002 | 2026-09-30 | [제목 옆에 판 번호](20260930_jikhanjung_002_title_version.md) |
| jikhanjung P01 | 2026-09-30 | [KIGAM 5만 지질도의 층리·엽리·절리를 레이어로 (계획)](20260930_jikhanjung_P01_kigam_50k_structures.md) |
| jikhanjung 003 | 2026-09-30 | [층리·엽리 뺀 5만 지질도 — 그림만 낱레이어를 엮어 GeoServer 에서](20260930_jikhanjung_003_kigam_50k_no_attitude.md) |
| jikhanjung 004 | 2026-09-30 | [5만 지질도의 자세 기호에 커서를 — 올리면 손가락, 누르면 값](20260930_jikhanjung_004_attitude_hover.md) |
| jikhanjung 005 | 2026-09-30 | [자세 기호를 늘 그리는 스위치, 그리고 "(층리 등 제외)"](20260930_jikhanjung_005_attitude_symbols.md) |
| jikhanjung 006 | 2026-09-30 | [줌 표시, 그리고 자세 기호를 멀리서 작게](20260930_jikhanjung_006_zoom_badge.md) |
| jikhanjung 007 | 2026-09-30 | [패널 접는 손잡이, 자세 기호 체크를 색 글자로](20260930_jikhanjung_007_panel_handle.md) |
| jikhanjung 008 | 2026-09-30 | [달·화성 화면에도 패널 손잡이](20260930_jikhanjung_008_panel_handle_moon_mars.md) |
| jikhanjung 009 | 2026-09-30 | [온 지구 화면에도 패널 손잡이](20260930_jikhanjung_009_panel_handle_earth.md) |
| wetherilli 078 | 2026-09-30 | [3D 극지 지형을 미리 받는다](20260930_wetherilli_078_polar_dem_prewarm.md) |
| wetherilli 079 | 2026-09-30 | [화성 — USGS 지역 지질도를 옛 지질도에 얹는다](20260930_wetherilli_079_mars_regional_geology.md) |
| wetherilli 080 | 2026-09-30 | [화성 — NASA Trek 판 목록을 화성 화면에](20260930_wetherilli_080_mars_trek_catalog.md) |
| wetherilli 081 | 2026-09-30 | [달 — Trek 의 지질도 그림 둘에 속성과 범례를 붙인다](20260930_wetherilli_081_moon_geologic_rasters.md) |
| wetherilli 082 | 2026-09-30 | [운영 — 타일 캐시를 /data 하드로 옮긴다](20260930_wetherilli_082_tile_cache_to_data_disk.md) |
| wetherilli 083 | 2026-09-30 | [달 — 지형을 LOLA 256 ppd 로 올린다](20260930_wetherilli_083_moon_dem_256ppd.md) |
| wetherilli 084 | 2026-09-30 | [VWorld — 보호구역·토양·공역·유역 26 개를 더한다](20260930_wetherilli_084_vworld_more_layers.md) |
| wetherilli 085 | 2026-09-30 | [달 — 극 평면에서 Trek 판의 극지 짝을 받는다](20260930_wetherilli_085_moon_polar_trek_twins.md) |
| wetherilli P06 | 2026-09-30 | [온 지구 화면 — 달·화성처럼 둥근 지구를, 그리고 그때 그 자리 (계획)](20260930_wetherilli_P06_whole_earth.md) |
| wetherilli 086 | 2026-09-30 | [온 지구 — 달·화성처럼 둥근 지구에 Macrostrat 지질도를](20260930_wetherilli_086_whole_earth_globe.md) |
| wetherilli 087 | 2026-09-30 | [온 지구 — 그때의 자리, PALEOMAP 2016 판 회전으로](20260930_wetherilli_087_paleo_position.md) |
| wetherilli 088 | 2026-09-30 | [온 지구 — 그때의 자리를 EarthThruTime3D 에서 본다](20260930_wetherilli_088_ett_link.md) |
| wetherilli 089 | 2026-09-30 | [그린란드 포털 — 면과 갈래 색을 받는 틀, 그리고 레이어 넷](20260930_wetherilli_089_greenland_portal_areas.md) |
| wetherilli 090 | 2026-09-30 | [Trek 판 목록 — 타일 한 장을 받아 보고 적는다](20260930_wetherilli_090_trek_probe_tile.md) |
| wetherilli P07 | 2026-09-30 | [온 지구 — 시간 축, 그리고 그 위에 얹을 일곱 (계획)](20260930_wetherilli_P07_earth_time_axis.md) |
| wetherilli 091 | 2026-09-30 | [온 지구 — 시간 축, 그리고 판을 돌린 그때의 지구](20260930_wetherilli_091_earth_time_axis.md) |
| wetherilli 092 | 2026-09-30 | [극지 배경 — PGC 음영의 다른 그리는 법 둘](20260930_wetherilli_092_pgc_hillshade_variants.md) |
| wetherilli 093 | 2026-09-30 | [남극 — 세종·장보고 기지 위성영상 (VWorld 테마)](20260930_wetherilli_093_vworld_antarctic_stations.md) |
| wetherilli 094 | 2026-09-30 | [스발바르 — 빙하 전면 변화 1936–2025 (NPI)](20260930_wetherilli_094_svalbard_glacier_fronts.md) |
| wetherilli 095 | 2026-09-30 | [극지연구소 — KPDC 기본도 다섯 (노출암·등고선·역사 유적·북극 등심선·빙상 등고선)](20260930_wetherilli_095_kpdc_base_map_layers.md) |
| wetherilli 096 | 2026-09-30 | [지명 찾기 — 스발바르 하나에서 그린란드·드로닝모드랜드·북극 묶음으로](20260930_wetherilli_096_place_search_regions.md) |
| wetherilli 097 | 2026-09-30 | [온 지구 — 옛 해안선, 화석이 가리키는 가장 깊은 바다](20260930_wetherilli_097_paleocoastlines.md) |
| wetherilli 098 | 2026-09-30 | [온 지구 — 화석 산지, PBDB 27 만 곳을 연대마다 그 자리에](20260930_wetherilli_098_pbdb_fossil_collections.md) |
| wetherilli 099 | 2026-09-30 | [극지 — PGC 경사·등고선을 지질도 위에 겹치는 레이어로](20260930_wetherilli_099_pgc_slope_contour_layers.md) |
| wetherilli 100 | 2026-09-30 | [달 — 잰 선을 따라 높이 그래프](20260930_wetherilli_100_moon_elevation_profile.md) |
| wetherilli 101 | 2026-09-30 | [온 지구 — 지각 두께, CRUST 2.0](20260930_wetherilli_101_crust_thickness.md) |
| wetherilli 102 | 2026-09-30 | [온 지구 — 지명 찾기, 산맥·바다 이름, 강·호수, 빙하](20260930_wetherilli_102_natural_earth_places.md) |
| wetherilli 103 | 2026-09-30 | [달 — 누른 자리의 광물·원소·지각 두께 값](20260930_wetherilli_103_moon_point_values.md) |
| wetherilli 104 | 2026-09-30 | [온 지구 — 최근 빙기의 빙상 가장자리, 25–1 ka](20260930_wetherilli_104_ice_margins.md) |
| wetherilli 105 | 2026-09-30 | [온 지구 — 지질도가 가까이 갈수록 깨지던 것, 색마다 매끄럽게 늘린다](20260930_wetherilli_105_geology_upscale.md) |
| wetherilli 106 | 2026-09-30 | [온 지구 — 지구 속, OPT1 의 섭입한 판과 하부 더미](20260930_wetherilli_106_mantle_slabs.md) |
| wetherilli 107 | 2026-09-30 | [달 — 극지 5 m·NAC DTM 으로 가까이서 고운 지형](20260930_wetherilli_107_moon_fine_terrain.md) |
| wetherilli 108 | 2026-09-30 | [동·동남아시아 — CCOP 200만 지질도](20260930_wetherilli_108_ccop_geology.md) |
| wetherilli 109 | 2026-09-30 | [지구 — 잰 선을 따라 높이 그래프](20260930_wetherilli_109_earth_elevation_profile.md) |
| wetherilli 110 | 2026-09-30 | [온 지구 — 구의 그리기가 멈췄을 때](20260930_wetherilli_110_earth_render_failure.md) |
| wetherilli 111 | 2026-09-30 | [지역 탭 — "+ 추가 지역" 목록을 묶음 아래 들여 세운다](20260930_wetherilli_111_region_menu_nesting.md) |
| wetherilli 112 | 2026-10-01 | [온 지구 — PBDB 산지 링크를 displayCollectionDetails 로](20261001_wetherilli_112_pbdb_collection_link.md) |
| wetherilli 113 | 2026-10-01 | [첫 화면 — 스스로 넘어가는 소개, 지도는 `map/` 으로](20261001_wetherilli_113_intro_page.md) |
| wetherilli 114 | 2026-10-01 | [2D 지도 — 우클릭 끌기로 돌리고, 자세 묶음의 방위 단추로 되돌린다](20261001_wetherilli_114_map_right_drag_rotate.md) |
| wetherilli 115 | 2026-10-01 | [소개 다듬기 — 타이틀, 둥근 지구·달·화성, 쏟아지는 수십 장](20261001_wetherilli_115_intro_title.md) |
| wetherilli 116 | 2026-10-01 | [온 지구 — 맨틀을 켜면 땅이 물러나고, 슬랩은 파랑·더미는 빨강](20261001_wetherilli_116_earth_mantle_visibility.md) |
| wetherilli 117 | 2026-10-01 | [온 지구 — 맨틀을 깊이로 칠한다: 얕을수록 밝게](20261001_wetherilli_117_mantle_depth_shading.md) |
| wetherilli P08 | 2026-10-01 | [관리 화면과 개인 레이어 — 브라우저에만 두는 내 자료 (계획)](20261001_wetherilli_P08_personal_layers.md) |
| wetherilli 118 | 2026-10-01 | [관리 화면 — 개인 레이어 반입, 저장 자료 관리, 첫 자료 nkfcluster](20261001_wetherilli_118_personal_layers.md) |
| wetherilli 119 | 2026-10-01 | [소개 — 훑고 지나가게, 크게, 자연스러운 줄바꿈](20261001_wetherilli_119_intro_pace.md) |
| wetherilli 120 | 2026-10-01 | [개인 레이어 — 빈 블록은 감추고, 한 자리에 겹친 기록은 건수를 단다](20261001_wetherilli_120_personal_layer_stack.md) |
| wetherilli 121 | 2026-10-01 | [소개 — 공식 CI 원본, 굵게, 만든 이를 길게](20261001_wetherilli_121_intro_polish.md) |
| wetherilli P09 | 2026-10-01 | [연결 레이어 — 남의 API 를 개인 레이어로 잇는다 (계획)](20261001_wetherilli_P09_linked_layers.md) |
| wetherilli 122 | 2026-10-01 | [연결 레이어 — 곧장 받고, 막히면 서버를 거치고, 못 받으면 옛것](20261001_wetherilli_122_linked_layers.md) |
| wetherilli 123 | 2026-10-01 | [극지 아이콘과 대기 화면 — 지도와 소개에](20261001_wetherilli_123_polar_emblem.md) |
| wetherilli 124 | 2026-10-01 | [연결 레이어 — 전체 마감 20 초, https 에서 내려가면 키를 빼고](20261001_wetherilli_124_linked_deadline.md) |
| wetherilli 125 | 2026-10-01 | [소개 시작 장 — 지구와 극지를 한 줄에](20261001_wetherilli_125_intro_doors_row.md) |
| wetherilli 126 | 2026-10-01 | [연결 레이어 — FSIS 화석산지 API: 섞인 모양은 가르고, 선을 받고, 연구소 망의 인증서를 믿는다](20261001_wetherilli_126_linked_fsis.md) |
| wetherilli 127 | 2026-10-01 | [소개 — "…에서 만들었습니다", 위로 올린 "그래서"](20261001_wetherilli_127_intro_credit_wording.md) |
| wetherilli 128 | 2026-10-01 | [휴대폰 화면 — 접히는 패널, 아이콘 한 줄, 접힌 범례](20261001_wetherilli_128_mobile_layout.md) |
| wetherilli 129 | 2026-10-01 | [연결 레이어 — API 의 목차 주소를 넣어도 자료 주소를 찾아간다](20261001_wetherilli_129_linked_endpoints.md) |
| wetherilli 130 | 2026-10-01 | [관리 화면 — 반입 탭에 양식 예시를 펼쳐 보인다 (CSV·JSON·API)](20261001_wetherilli_130_format_examples.md) |
| wetherilli 131 | 2026-10-01 | [개인 레이어 — 아이콘을 눌러 색·모양, 면 투명도, 용량 재기, 켠 지질 레이어 모두 끄기](20261001_wetherilli_131_personal_style_capacity.md) |
| wetherilli 132 | 2026-10-01 | [휴대폰 화면을 시험으로](20261001_wetherilli_132_mobile_test.md) |
| wetherilli 133 | 2026-10-01 | [레이어 목록 — 체크박스 대신 상류 딱지, 줄을 눌러 켜고 끄기, 레이어군 모두 켜기](20261001_wetherilli_133_catalog_rows.md) |
| wetherilli 134 | 2026-10-02 | [온 지구 — 홀로세 화산, 스미스소니언 GVP 1 214 곳](20261002_wetherilli_134_gvp_volcanoes.md) |
| wetherilli 135 | 2026-10-02 | [해저 — GEBCO 해저 지형 배경, EMODnet 해저 지질을 북극해·스발바르에](20261002_wetherilli_135_seafloor_gebco_emodnet.md) |
| wetherilli 136 | 2026-10-02 | [대만 — 경제부 지질조사·광업관리중심 지질도, 대만 탭과 동아시아에](20261002_wetherilli_136_taiwan_gsmma.md) |
| wetherilli 137 | 2026-10-02 | [수성 — 화성 화면을 옮긴 1 단계 (영상·표고·지명·점묶음, 지질은 다음에)](20261002_wetherilli_137_mercury_view.md) |
| wetherilli 138 | 2026-10-02 | [온 지구 — 지진, USGS 의 M5 이상 10 만 7 천 곳을 규모 칸 셋으로](20261002_wetherilli_138_usgs_earthquakes.md) |
| wetherilli 139 | 2026-10-02 | [온 지구 — 제4기 고생태 산지, Neotoma 를 자료형 칸 다섯으로](20261002_wetherilli_139_neotoma_sites.md) |
| wetherilli 140 | 2026-10-02 | [노르웨이·핀란드 — NGU·GTK 기반암 지질도를 새 지역 탭과 북극 묶음에](20261002_wetherilli_140_fennoscandia_geology.md) |
| wetherilli 141 | 2026-10-02 | [대만 둘째 판 — 환경지질·민감구역·시추·온천, 국토측회중심 배경, 3D](20261002_wetherilli_141_taiwan_second.md) |
| wetherilli 142 | 2026-10-02 | [대만 범례 — 지층 면과 그림을 맞대어 견본을 뜬다](20261002_wetherilli_142_taiwan_legend.md) |
| wetherilli 143 | 2026-10-02 | [영국·프랑스·유럽 — BGS·BRGM 지질도와 EGDI 범유럽 1:100만, 탭 둘과 묶음 하나](20261002_wetherilli_143_europe_geology.md) |
| wetherilli 144 | 2026-10-02 | [수성 지질도 — USGS 1:500만 도폭 아홉의 합본을 우리가 굽는다](20261002_wetherilli_144_mercury_geology.md) |
| wetherilli 145 | 2026-10-02 | [휴대폰 화면 시험 — 구 화면을 하나씩 닫는다](20261002_wetherilli_145_mobile_test_close_pages.md) |
| wetherilli 147 | 2026-10-02 | [유럽 2단계 — 독일 BGR·스페인 IGME·아일랜드 GSI·북아일랜드 GSNI](20261002_wetherilli_147_europe_more.md) |
| wetherilli 146 | 2026-10-02 | [수성 더 — 소개 화면에 수성, 도폭 경계는 우리가 긋는다](20261002_wetherilli_146_mercury_more.md) |
| wetherilli 148 | 2026-10-02 | [화성·수성의 높이 그래프](20261002_wetherilli_148_planet_profiles.md) |
| wetherilli 150 | 2026-10-02 | [달 — 남은 값과 고운 지형 (다누리 KGRS·북극 판·NAC 셋)](20261002_wetherilli_150_moon_trek_more.md) |
| wetherilli 151 | 2026-10-02 | [브라우저 캐시 — 모든 응답에 ETag·304, 판이 든 주소만 길게](20261002_wetherilli_151_cache_headers.md) |
| wetherilli 153 | 2026-10-02 | [온 지구 아이콘과 대기 화면](20261002_wetherilli_153_earth_emblem.md) |
| wetherilli 154 | 2026-10-02 | [그때의 자리 — GPlates 와 견준 회귀 시험, 캡션 한 줄](20261002_wetherilli_154_paleo_gws_check.md) |
| wetherilli 152 | 2026-10-02 | [주소만 적힌 CSV 를 점묶음으로 — 화면이 50 줄씩 나눠 VWorld 에 묻는다](20261002_wetherilli_152_address_csv.md) |
| wetherilli 149 | 2026-10-02 | [공개용 저장소 GSM-open — 소스 링크를 개발 저장소에서 떼어 둔다](20261002_wetherilli_149_open_source_repo.md) |
| wetherilli 158 | 2026-10-02 | [캐시의 빈 곳 — 3D 편 것을 담고, 속성 JSON 에 헤더, prewarm 이 KOPRI·Trek 을](20261002_wetherilli_158_cache_more.md) |
| wetherilli 157 | 2026-10-02 | [그린란드 — 다이아몬드 탐사 자료의 시추공·지시광물·석류석·탐사 구역](20261002_wetherilli_157_greenland_diamonds.md) |
| wetherilli 156 | 2026-10-02 | [VWorld 측정망 점을 벡터로, AWS 음영·경사와 국토지리원 주제 타일을 배경으로](20261002_wetherilli_156_vworld_points_basemaps.md) |
| wetherilli 155 | 2026-10-02 | [일본의 찾기 칸 — 국토지리원 주소·지명 검색을 브라우저가 곧장](20261002_wetherilli_155_japan_search.md) |
| wetherilli 160 | 2026-10-02 | [정적 판 굽기 — `manage.py bake_static`](20261002_wetherilli_160_static_bake.md) |
| wetherilli 159 | 2026-10-02 | [연속값 색 — 그린란드 지화학 넷을 원소 하나로 칠한다](20261002_wetherilli_159_value_colors.md) |
| wetherilli 163 | 2026-10-02 | [그린란드 전암 화학 3 만 점 — 서버가 고른 원소만 잘라 준다](20261002_wetherilli_163_greenland_whole_rock.md) |
| wetherilli P10 | 2026-10-02 | [수성 — 화성 화면을 옮겨 짓는다 (계획)](20261002_wetherilli_P10_mercury.md) |
| wetherilli P11 | 2026-10-02 | [연구소 밖 정적 판 — GitHub Pages 의 GSM-open (계획)](20261002_wetherilli_P11_static_site.md) |
| wetherilli 162 | 2026-10-02 | [연구소 밖 정적 판의 뼈대 — 한국 지질도를 각자 키로](20261002_wetherilli_162_static_site_skeleton.md) |
| wetherilli 164 | 2026-10-02 | [정적 판의 VWorld — 공개 판용 키 하나로 배경·찾기·좌표→주소·레이어 그림](20261002_wetherilli_164_static_vworld.md) |
| wetherilli 165 | 2026-10-02 | [정적 판에 구운 것 잇기 — 남극·얀마옌·극지의 점이 서버 없이](20261002_wetherilli_165_static_wire.md) |
| wetherilli 166 | 2026-10-02 | [정적 판의 극지 지명 찾기 — 구운 지명에서 색인을, 화면이 뒤진다](20261002_wetherilli_166_static_placenames.md) |
| wetherilli 168 | 2026-10-02 | [정적 판의 시험 — 작은 판을 굽고 `/GSM-open/` 꼴로 띄운다](20261002_wetherilli_168_static_tests.md) |
| wetherilli 167 | 2026-10-02 | [정적 판의 영어판과 소개 — 말마다 따로 굽고, 뿌리는 소개로](20261002_wetherilli_167_static_lang_intro.md) |
| wetherilli 161 | 2026-10-02 | [정적 판의 극지 — 상류를 브라우저가 곧장 부르는 `static-kinds.js`](20261002_wetherilli_161_static_polar.md) |
| wetherilli 170 | 2026-10-02 | [시료 고도를 국가기준점과 견준다 — 24 점 모두 ±15 m 안](20261002_wetherilli_170_elevation_check.md) |
| wetherilli 172 | 2026-10-02 | [일본 — 국토지리원 활단층도·화산토지조건도를 겹치는 레이어로](20261002_wetherilli_172_japan_afm.md) |
| wetherilli 171 | 2026-10-02 | [지질도Navi 판 1 849 — 일본 탭의 판 목록](20261002_wetherilli_171_gsj_geonavi.md) |
| wetherilli 173 | 2026-10-02 | [시료 지점의 둘레에 보호구역·지목·소유구분](20261002_wetherilli_173_point_facts_land.md) |
| wetherilli 174 | 2026-10-02 | [정적 판 — KIGAM·VWorld 키를 둘 다 각자, 처음 열 때 묻는다](20261002_wetherilli_174_static_two_keys.md) |
| wetherilli 169 | 2026-10-04 | [KIGAM `/openapi/data` 모으기 — 문과 받기 명령, 지도는 아직](20261004_wetherilli_169_kigam_data_collect.md) |
| wetherilli 177 | 2026-10-04 | [유럽 — EGDI 1:100만의 속성을 암상 판으로 켠다](20261004_wetherilli_177_egdi_info.md) |
| wetherilli 176 | 2026-10-04 | [유럽 바다 — EMODnet 의 제4기 퇴적층·지질 사건을 유럽 탭들에](20261004_wetherilli_176_europe_seafloor.md) |
| wetherilli 181 | 2026-10-04 | [정적 판 — 판 이력을 떠 두고, 소개의 첫 장면에서 없는 화면을 뺀다](20261004_wetherilli_181_static_intro_history.md) |
| wetherilli 178 | 2026-10-04 | [그린란드 — 다이아몬드 탐사 자료의 나머지: 지시광물 화학 넷·거둔 다이아몬드·관입 연대·산출지의 선과 면](20261004_wetherilli_178_greenland_ded_more.md) |
| wetherilli 179 | 2026-10-04 | [정적 판 — 휴대폰에서 KIGAM 지질도가 안 뜬다는 제보, 후보를 지우고 키가 받히는지 묻는다](20261004_wetherilli_179_static_mobile_kigam.md) |
| wetherilli 180 | 2026-10-04 | [높이 그래프 밑에 지질 띠 — 우리 파일로 그리는 레이어만](20261004_wetherilli_180_profile_geology_band.md) |
| wetherilli 182 | 2026-10-04 | [prewarm 이 유럽·북극의 새 상류를 안다](20261004_wetherilli_182_prewarm_europe.md) |
| wetherilli 183 | 2026-10-04 | [화면이 주소를 짓는 타일에도 판을 — 길게(immutable) 캐시한다](20261004_wetherilli_183_immutable_js_tiles.md) |
| wetherilli 184 | 2026-10-04 | [조건이 열린 배경을 서버 캐시에 — NASA GIBS·GEBCO](20261004_wetherilli_184_cache_open_basemaps.md) |
| wetherilli 185 | 2026-10-04 | [지역 탭에 화석 산지·홀로세 화산·지진·고생태 산지 — 그리고 수성의 잠든 주소](20261004_wetherilli_185_regional_earth_points.md) |
| wetherilli 186 | 2026-10-04 | [온 지구에 높이 그래프, 달·화성·수성에 "그리기가 멈췄다" 안내](20261004_wetherilli_186_earth_profile_render_failed.md) |
| wetherilli 187 | 2026-10-04 | [3D 에 유럽·일본 지질도, 온 지구 찾기에 화석 산지·지층·화산](20261004_wetherilli_187_3d_europe_earth_search.md) |
| wetherilli 188 | 2026-10-04 | [남미 — 콜롬비아 지질조사소(SGC)의 남미 1:500만과 콜롬비아 1:50만으로 남미 탭을 연다](20261004_wetherilli_188_south_america_sgc.md) |
| wetherilli 189 | 2026-10-04 | [공유 링크 — 보던 자리·켠 레이어·배경을 주소의 해시에](20261004_wetherilli_189_share_links.md) |
| wetherilli 190 | 2026-10-04 | [점묶음을 CSV 로 — 우리 파일에서 읽는 값을 열로 붙여](20261004_wetherilli_190_pointset_csv.md) |
| wetherilli 192 | 2026-10-04 | [화성 — Trek 판의 극지 길과 누른 자리의 높이](20261004_wetherilli_192_mars_polar_values.md) |
| wetherilli 191 | 2026-10-04 | [브라질 — SGB 지질도, 그리고 남미를 나라 탭 둘과 묶음으로](20261004_wetherilli_191_brazil_sgb.md) |
| wetherilli 193 | 2026-10-04 | [휴대폰 시험을 모든 지역 탭과 팝업으로 — 그리고 VWorld `minZoom`, NPI 쉼표 소수](20261004_wetherilli_193_mobile_all_tabs.md) |
| wetherilli 194 | 2026-10-04 | [수성의 높이 값, 온 지구의 주소 CSV, 플라이스토세 화산](20261004_wetherilli_194_mercury_heights_earth_csv_pleistocene.md) |
| wetherilli 195 | 2026-10-04 | [페루 — INGEMMET 1:5만·1:10만 통합판을 타일 캐시로](20261004_wetherilli_195_peru_ingemmet.md) |
| wetherilli 196 | 2026-10-04 | [남미 — 아르헨티나 SEGEMAR(1:250만·1:25만)와 우루과이 DINAMIGE(1:50만)](20261004_wetherilli_196_argentina_uruguay.md) |
| wetherilli 197 | 2026-10-04 | [도폭 하나의 층리·엽리 장미도](20261004_wetherilli_197_structure_rose.md) |
| wetherilli 198 | 2026-10-04 | [남미의 남은 것 — 에콰도르를 싣고, 볼리비아는 또 막히고, 남미 묶음의 처음을 정한다](20261004_wetherilli_198_south_america_rest.md) |
| wetherilli 199 | 2026-10-04 | [5만 구조 요소 — `fetch_kigam50k` 명령과 화석산지·시료·광산·도폭 틀 레이어](20261004_wetherilli_199_kigam50k_layers.md) |
| wetherilli 200 | 2026-10-04 | [남은 배경의 조건을 읽었다 — NPI 타일만 서버 캐시로](20261004_wetherilli_200_cache_more_basemaps.md) |
| wetherilli 201 | 2026-10-04 | [정적 판에 콜롬비아 1:50만을 실을 수 있게 — 싣는 것은 사람이 고른다](20261004_wetherilli_201_static_colombia.md) |
| wetherilli 202 | 2026-10-04 | [5만 구조 요소 — 단층·습곡·광종·변질대·변성대](20261004_wetherilli_202_kigam50k_lines.md) |
| wetherilli 203 | 2026-10-04 | [작은 고침 묶음 — 미뤄 둔 것·시험·영어판·휴대폰의 빈틈](20261004_wetherilli_203_small_fixes.md) |
| wetherilli 208 | 2026-10-04 | [5만 구조 요소 받기를 주간 백업에서 뺀다 — 사람이 가끔 부른다](20261004_wetherilli_208_no_auto_kigam50k.md) |
| wetherilli 204 | 2026-10-04 | [캐나다 — NRCan 1:500만과 온타리오 OGS 1:25만, 화면은 캐나다 람베르트(3978)](20261004_wetherilli_204_canada.md) |
| wetherilli 205 | 2026-10-04 | [미국 — USGS SGMC(본토)와 알래스카 SIM 3340 으로 미국 탭](20261004_wetherilli_205_usa_usgs.md) |
| wetherilli 206 | 2026-10-04 | [멕시코 — SGM 1:25만·1:5만, WMS 가 막혀 문이 REST export 로 옮긴다](20261004_wetherilli_206_mexico_sgm.md) |
| wetherilli 207 | 2026-10-04 | [아프리카 — CGMW–BRGM 1:1000만과 BGS 아프리카 지하수 지도책으로 탭을 연다](20261004_wetherilli_207_africa.md) |
| wetherilli 209 | 2026-10-04 | [아프리카 나라 판 — 남아공 CGS·나미비아 GSN 1:100만 (탄자니아는 TLS 로 막혔다)](20261004_wetherilli_209_africa_countries.md) |
| wetherilli 212 | 2026-10-04 | [호주 — Geoscience Australia 지표 지질도 1:250만·1:100만](20261004_wetherilli_212_australia_ga.md) |
| wetherilli 210 | 2026-10-04 | [캐나다의 주 판 — 퀘벡 SIGÉOM·유콘 YGS, 그리고 북미 묶음](20261004_wetherilli_210_canada_provinces.md) |
| wetherilli 211 | 2026-10-04 | [유럽 — 이탈리아 ISPRA·포르투갈 LNEG·스위스 swisstopo](20261004_wetherilli_211_italy_portugal_switzerland.md) |
| wetherilli 213 | 2026-10-04 | [스웨덴 — SGU 기반암 1:100만·1:5만–25만을 노르웨이·핀란드 탭에](20261004_wetherilli_213_sweden_sgu.md) |
| wetherilli 214 | 2026-10-04 | [지역 탭 접기 — 한국·북극·남극만 서고 나머지는 "그 외"](20261004_wetherilli_214_region_fold.md) |
| wetherilli 215 | 2026-10-04 | [브라질 — SGB 의 노두·연대측정·화석 산지 점](20261004_wetherilli_215_brazil_points.md) |
| wetherilli 216 | 2026-10-04 | [아이슬란드 — 자연사연구소(NÍ) 1:60만·1:10만, 북극 묶음에](20261004_wetherilli_216_iceland.md) |
| wetherilli 218 | 2026-10-04 | [뉴질랜드 — GNS QMAP 1:25만·1:100만, 남극 남빅토리아랜드, 오세아니아 묶음](20261004_wetherilli_218_new_zealand.md) |
| wetherilli 219 | 2026-10-04 | [멕시코 — SGM 의 지질 연대·고생물·광상](20261004_wetherilli_219_mexico_more.md) |
| wetherilli 220 | 2026-10-04 | [아르헨티나 — SEGEMAR 의 지역 판·제4기 변형·화산 위험도](20261004_wetherilli_220_segemar_more.md) |
| wetherilli 221 | 2026-10-04 | [몽골 — MonGeoCat 국가지질도첩 지질도·단층, 동아시아 묶음에](20261004_wetherilli_221_mongolia.md) |
| wetherilli 222 | 2026-10-04 | [페루 — INGEMMET 의 단층·습곡을 따로 켜는 레이어](20261004_wetherilli_222_ingemmet_structures.md) |
| wetherilli 223 | 2026-10-04 | [한국 — KIGAM 5만의 선구조·신장광물·습곡축·유동구조를 방향 기호로](20261004_wetherilli_223_kigam50k_attitudes.md) |
| wetherilli 226 | 2026-10-04 | [인도 — GSI 1:200만, 그림은 BGS 의 OneGeology WMS·속성은 GSI 피처 서비스](20261004_wetherilli_226_india.md) |
| wetherilli 224 | 2026-10-04 | [퀘벡 시대 표와 알래스카의 물 띠](20261004_wetherilli_224_quebec_ages_alaska_water.md) |
| wetherilli 225 | 2026-10-04 | [호주 — 주 지질조사소 판 셋(퀸즐랜드·빅토리아·남호주)](20261004_wetherilli_225_australia_states.md) |
| wetherilli 227 | 2026-10-04 | [사우디아라비아 — SGS 1:25만 합본, 보는 범위의 범례](20261004_wetherilli_227_saudi.md) |
| wetherilli 229 | 2026-10-04 | [달·수성 — USGS Astrogeology WMS 의 옛 탐사선 배경 (루나 오비터·클레멘타인·마리너 10)](20261004_wetherilli_229_moon_astro_basemaps.md) |
| wetherilli 230 | 2026-10-04 | [일본의 좌표 → 주소 — 국토지리원 역지오코더를 브라우저가 곧장](20261004_wetherilli_230_japan_reverse_geocode.md) |
| wetherilli 232 | 2026-10-04 | [호주 주 판 — 퀸즐랜드·남호주의 범례와 구조선](20261004_wetherilli_232_australia_states_legends.md) |
| wetherilli 217 | 2026-10-04 | [유럽 1:500만 — BGR IGME5000](20261004_wetherilli_217_bgr_igme5000.md) |
| wetherilli 228 | 2026-10-04 | [동남아 — 인도네시아·말레이시아·필리핀·태국 탭과 묶음](20261004_wetherilli_228_southeast_asia.md) |
| wetherilli 231 | 2026-10-04 | [브리티시컬럼비아·캘리포니아 — 캐나다 탭과 미국 탭에 주 지질도 둘](20261004_wetherilli_231_bc_california.md) |
| wetherilli 233 | 2026-10-04 | [멕시코 — SGM 의 지화학·원소 이상·광상 나머지](20261004_wetherilli_233_mexico_geochem.md) |
| wetherilli 234 | 2026-10-04 | [페루 — INGEMMET 1:5만 지질 단위만(단층·습곡 없이)](20261004_wetherilli_234_ingemmet_units.md) |
| wetherilli 236 | 2026-10-04 | [달 — 누른 자리의 값, 남은 판](20261004_wetherilli_236_moon_values_rest.md) |
| wetherilli 237 | 2026-10-05 | [유럽 넷 더 — 오스트리아·폴란드·네덜란드·벨기에, 체코·덴마크는 사람에게](20261005_wetherilli_237_europe_more_3.md) |
| wetherilli 235 | 2026-10-05 | [캐나다 주 판 둘째 — 앨버타·사스카치원·노바스코샤](20261005_wetherilli_235_canada_provinces_2.md) |
| wetherilli 238 | 2026-10-05 | [미국 — 하와이·푸에르토리코](20261005_wetherilli_238_usa_islands.md) |
| wetherilli 239 | 2026-10-05 | [오스트리아·폴란드 1:5만 — 가까이서만 그리는 레이어](20261005_wetherilli_239_europe_50k.md) |
| wetherilli 240 | 2026-10-05 | [달 — 고운 지형, 남은 판](20261005_wetherilli_240_moon_terrain_rest.md) |
| wetherilli 241 | 2026-10-05 | [호주 — Geoscience Australia 의 다른 서비스](20261005_wetherilli_241_ga_more.md) |
| wetherilli 243 | 2026-10-05 | [동남아 — 인도네시아 범례를 보는 범위의 것으로](20261005_wetherilli_243_sea_legends.md) |
| wetherilli 244 | 2026-10-05 | [멕시코 — 지자기(SGM DatosAbiertos 7)는 싣지 않았다](20261005_wetherilli_244_mexico_magnetics.md) |
| wetherilli 245 | 2026-10-05 | [한반도 지질도 민판 — 색↔지층 표는 CorelDRAW 원본에 없다](20261005_wetherilli_245_peninsula_legend.md) |
| wetherilli 246 | 2026-10-05 | [아프리카 나라 판 둘째 — 부르키나파소 BUMIGEB·카메룬 IRGM 1:100만](20261005_wetherilli_246_africa_countries_2.md) |
| wetherilli 247 | 2026-10-05 | [미국 — USGS mrdata 의 광물·지구물리·연대](20261005_wetherilli_247_usa_more.md) |
| wetherilli 249 | 2026-10-05 | [중동·남아시아 나머지 — 열린 지질도 서비스가 없다](20261005_wetherilli_249_middle_east.md) |
| wetherilli 242 | 2026-10-05 | [중앙아메리카·카리브 — 니카라과·도미니카공화국, 따로 세운 묶음](20261005_wetherilli_242_central_america.md) |
| wetherilli 248 | 2026-10-05 | [카리브 — USGS 카리브 지질도를 면 한 덩이로, SIM 3534 는 실측만](20261005_wetherilli_248_caribbean_usgs.md) |
| wetherilli 250 | 2026-10-05 | [캐나다 — NRCan 의 편찬 지질도·핵심 광물·광상 유망도](20261005_wetherilli_250_canada_more.md) |
| wetherilli 251 | 2026-10-05 | [정리 — 영어 빈자리·CLAUDE.md 의 지역 목록·TODOs 의 끝난 일](20261005_wetherilli_251_housekeeping.md) |
| wetherilli 252 | 2026-10-05 | [새 상류 점검 — 미리 데우기가 화면이 멈춘 줌 너머를 받던 다섯](20261005_wetherilli_252_upstream_audit.md) |
| wetherilli 253 | 2026-10-05 | [파나마 — STRI 1:25만 면·단층을 한 덩이씩](20261005_wetherilli_253_panama.md) |
| wetherilli 254 | 2026-10-05 | [카리브 — USGS 대앤틸리스 지질도(SIM 3534)를 우리가 굽는다](20261005_wetherilli_254_caribbean_sim3534.md) |
| wetherilli 255 | 2026-10-05 | [일본 — GSJ 의 1:200만 지질도·부게 중력·지구화학도](20261005_wetherilli_255_japan_more.md) |
| wetherilli 256 | 2026-10-05 | [남미 나머지 — 파라과이 탭과 USGS 남미 지질도, 나머지는 실측만](20261005_wetherilli_256_south_america_more.md) |
| wetherilli 257 | 2026-10-05 | [정적 판 점검 — 오늘 붙은 상류 가운데 고를 수 있는 것](20261005_wetherilli_257_static_optional.md) |
| wetherilli 260 | 2026-10-05 | [프랑스 해외 영토와 태평양 섬 — 누벨칼레도니 Géorep, BRGM 해외 스캔](20261005_wetherilli_260_overseas.md) |
| wetherilli 261 | 2026-10-05 | [남극의 다른 자료 — Bedmap3 를 올리고 나머지는 실측만](20261005_wetherilli_261_antarctica_more.md) |
| wetherilli 262 | 2026-10-05 | [남극 자력 이상 ADMAP-2 — Geosoft 격자를 numpy 없이 굽는다](20261005_wetherilli_262_admap2.md) |
| wetherilli 263 | 2026-10-05 | [대만 셋째 판 — 5만 유역 지질도·광상·불연속면, 활성단층을 누른다](20261005_wetherilli_263_taiwan_more.md) |
| wetherilli 264 | 2026-10-05 | [온 지구 — 해양 지각 연대와 해저 퇴적층 두께](20261005_wetherilli_264_earth_ocean_crust.md) |
| wetherilli 266 | 2026-10-05 | [일본 셋째 판 — 지구화학도 53 원소, 공중 자력 편집도 셋](20261005_wetherilli_266_japan_more.md) |
| wetherilli 267 | 2026-10-05 | [온 지구 — 지열류(IHFC 2024)와 세계 암상(GLiM)](20261005_wetherilli_267_earth_heatflow.md) |
| wetherilli 268 | 2026-10-05 | ['그 외' 차림을 대륙 머리로 묶는다](20261005_wetherilli_268_region_menu_groups.md) |
| wetherilli 258 | 2026-10-05 | [유럽 — BGS GeoIndex 의 자력·중력·광산·광물 산지 (EGDI 광물은 못 붙였다)](20261005_wetherilli_258_europe_resources.md) |
| wetherilli 259 | 2026-10-05 | [그린란드 — GEUS ArcGIS 의 자력 편찬·DTU 부게 중력·지질구](20261005_wetherilli_259_greenland_more.md) |
| wetherilli 265 | 2026-10-05 | [남미 — 브라질 광물 산출·콜롬비아 금속광상도와 지구물리·아르헨티나 광상](20261005_wetherilli_265_south_america_resources.md) |
| wetherilli 269 | 2026-10-05 | [오세아니아 — 호주 세 주의 광물·지구물리, 뉴질랜드 중력](20261005_wetherilli_269_oceania_resources.md) |
| wetherilli 270 | 2026-10-05 | [북유럽 — 핀란드 지구물리, 북유럽 광상 FODD, 스웨덴 산지·자력](20261005_wetherilli_270_nordic_resources.md) |
| wetherilli 271 | 2026-10-05 | [레이어가 오백을 넘은 뒤의 성능 점검](20261005_wetherilli_271_catalog_perf.md) |
| wetherilli 272 | 2026-10-05 | [온 지구 — 판 경계와 세계 지질구 (Hasterok 2022)](20261005_wetherilli_272_earth_plates.md) |
| wetherilli 273 | 2026-10-05 | [온 지구 — 지각 응력(World Stress Map 2025)](20261005_wetherilli_273_earth_stress.md) |
| wetherilli 274 | 2026-10-05 | [화성·수성을 달과 맞추기 — 화성의 고운 지형](20261005_wetherilli_274_mars_parity.md) |
| wetherilli 275 | 2026-10-05 | [한국 탭 다시 보기 — 빠진 것은 지열류 하나](20261005_wetherilli_275_korea_more.md) |
| wetherilli 276 | 2026-10-05 | [온 지구 — 세계 광상 (USGS MRDS·세계 광상 표)](20261005_wetherilli_276_earth_minerals.md) |
| wetherilli 277 | 2026-10-05 | [페루 — INGEMMET 의 광물 산지·광상·광화대, 부게 이상·항공 자력](20261005_wetherilli_277_peru_resources.md) |
| wetherilli 278 | 2026-10-05 | [온 지구 화면의 레이어 패널 — 주제로 묶는다](20261005_wetherilli_278_earth_panel.md) |
| wetherilli 279 | 2026-10-05 | [온 지구 — 세계 활성단층 (GEM Global Active Faults)](20261005_wetherilli_279_earth_faults.md) |
| wetherilli 280 | 2026-10-05 | [아시아 — 인도네시아·필리핀·태국·사우디·몽골의 광물](20261005_wetherilli_280_asia_resources.md) |
| wetherilli 281 | 2026-10-05 | [상류 조건표](20261005_wetherilli_281_upstream_terms.md) |
| wetherilli 282 | 2026-10-05 | [메타타일 — 큰 장을 한 번 받아 칸으로 잘라 담는다, 멕시코 지자기에 먼저](20261005_wetherilli_282_metatile.md) |
| wetherilli 283 | 2026-10-05 | [온 지구 — 충돌구와 거대 화성암 지대](20261005_wetherilli_283_earth_impacts.md) |
| wetherilli 284 | 2026-10-05 | [메타타일 넓히기 — SGC 넓은 줌, EGDI(실패하면 칸 하나로), prewarm 의 메타타일 블록](20261005_wetherilli_284_metatile_more.md) |
| wetherilli 287 | 2026-10-05 | [느린 상류 찾기와 메타타일 적용](20261005_wetherilli_287_metatile_slow.md) |
| wetherilli 285 | 2026-10-05 | [아프리카 — 남아공의 광업·석탄·우라늄 지역](20261005_wetherilli_285_africa_resources.md) |
| wetherilli 286 | 2026-10-05 | [온 지구 — 화석 산지 밀도, 옛 연대는 그때의 자리로](20261005_wetherilli_286_earth_fossil_density.md) |
| wetherilli 288 | 2026-10-05 | [캐나다 — 주의 광물 산지 다섯](20261005_wetherilli_288_canada_minerals.md) |
| wetherilli 289 | 2026-10-05 | [온 지구 — 세계 빙하 (RGI 7.0)](20261005_wetherilli_289_earth_glaciers.md) |
| wetherilli 290 | 2026-10-05 | [상류 응답 시간을 날마다 센다](20261005_wetherilli_290_upstream_timing.md) |
| wetherilli 295 | 2026-10-05 | [관리 화면에 상류 응답 시간 표](20261005_wetherilli_295_upstream_dashboard.md) |
| wetherilli 291 | 2026-10-05 | [미국 — 네바다·워싱턴·오리건 주 지질도](20261005_wetherilli_291_us_states.md) |
| wetherilli 292 | 2026-10-05 | [최근 지진 — USGS 실시간 피드를 매시 받아 온 지구 화면과 지역 탭에](20261005_wetherilli_292_recent_quakes.md) |
| wetherilli 294 | 2026-10-05 | [시험 돌리기 다듬기 — 나란히 돌 때 깨진 것이 보이게, 느린 것 줄이기](20261005_wetherilli_294_test_speed.md) |
| wetherilli 296 | 2026-10-05 | [유럽 — 프랑스·스페인·독일·포르투갈의 광물](20261005_wetherilli_296_europe_minerals.md) |
| wetherilli 297 | 2026-10-05 | [타일 캐시 디스크 점검 — 상류별 몫, 5 GB 바닥, 메타타일 두 벌](20261005_wetherilli_297_cache_audit.md) |
| wetherilli 298 | 2026-10-05 | [모든 상류의 레이어 대조 — verify_layers 를 670 개로](20261005_wetherilli_298_verify_all_layers.md) |
| wetherilli 299 | 2026-10-05 | [메타타일 첫 운영 점검표 — 하루 뒤에 볼 것, 되돌리는 스위치](20261005_wetherilli_299_metatile_ops_checklist.md) |
| wetherilli 300 | 2026-10-05 | [시간 한계의 사슬 — 바깥이 안보다 길게, 넘으면 "느리다" 안내 타일](20261005_wetherilli_300_timeout_chain.md) |
| wetherilli 301 | 2026-10-05 | [그린란드 — 공중 자력 셋, 지질도 1:250만·1:10만 둘 (GEUS ArcGIS)](20261005_wetherilli_301_greenland_geophysics_maps.md) |
| wetherilli 303 | 2026-10-05 | [페루 — INGEMMET 지화학 지도첩·산업 광물](20261005_wetherilli_303_peru_more.md) |
| wetherilli 302 | 2026-10-05 | [빅토리아 — 중력 측점, 지구물리 선형 셋 (GSV GeoServer)](20261005_wetherilli_302_victoria_geophysics.md) |
| wetherilli 304 | 2026-10-05 | [팝업이 가운데 맞춤 없이 서던 것 — 휴대폰 시험이 가끔 깨진 까닭](20261005_wetherilli_304_mobile_popup.md) |
| wetherilli 305 | 2026-10-05 | [대만 — 지질운 열린자료를 받아 두고 그린다](20261005_wetherilli_305_taiwan_open_data.md) |
| wetherilli 306 | 2026-10-05 | [남호주 SARIG 지구물리 — 열린 길을 찾지 못했다](20261005_wetherilli_306_sa_geophysics_search.md) |
| wetherilli 307 | 2026-10-05 | [극지 격자의 메타타일 — 3413·3031·3575·3978·대만 4326](20261005_wetherilli_307_metatile_polar.md) |
| wetherilli 308 | 2026-10-05 | [대조에서 깨진 레이어 고치기](20261005_wetherilli_308_verify_broken.md) |
| wetherilli 309 | 2026-10-05 | [미리 데우기의 메타타일 계획을 극지 격자로](20261005_wetherilli_309_prewarm_polar_metatile.md) |
| wetherilli 310 | 2026-10-05 | [운영 대조의 빈 그림 — 대개 축척 끝이었다](20261005_wetherilli_310_verify_empty.md) |
| wetherilli 311 | 2026-10-05 | [대조가 건너뛰던 갈래 — 점·모양 덩이, 곧장 부르는 타일, 우리가 자른 타일](20261005_wetherilli_311_verify_more.md) |
| wetherilli 312 | 2026-10-05 | [구운 자료의 나이 — data_status](20261005_wetherilli_312_data_status.md) |
| wetherilli 313 | 2026-10-05 | [넓게 볼 때만 느린 레이어 — 10 초 넘는 줌은 묻지 않는다](20261005_wetherilli_313_slow_wide.md) |
| wetherilli 314 | 2026-10-05 | [레이어 대조의 기록 — 날마다 남기고 지난번과 견준다](20261005_wetherilli_314_verify_history.md) |
| wetherilli 315 | 2026-10-05 | [정적 판 연기 시험](20261005_wetherilli_315_static_smoke.md) |
| wetherilli 316 | 2026-10-05 | [일본 — GSJ 1:200만 지질도·중력을 누르면 이름이](20261005_wetherilli_316_gsj_names.md) |
| wetherilli 317 | 2026-10-05 | [브리티시컬럼비아 — 넓게 볼 때도 칠한다](20261005_wetherilli_317_bcgs_wide.md) |
| wetherilli 318 | 2026-10-05 | [호주의 남은 주 — 태즈메이니아 지질, 뉴사우스웨일스 광물](20261005_wetherilli_318_au_states_more.md) |
| wetherilli 319 | 2026-10-05 | [TODOs 를 다시 묶었다 — 끝난 줄을 걷고, 결정 없이 할 것과 (사람) 을 가르고](20261005_wetherilli_319_todos_cleanup.md) |
| wetherilli 320 | 2026-10-05 | [캐나다 — 편찬 지질도 CGMC 를 누르면 암상이](20261005_wetherilli_320_cgmc_names.md) |
| koprifossillab P01 | 2026-09-30 | [백업 — WegenersDream 의 틀로, 바뀌는 빠르기에 따라 넷으로 (계획)](20260930_koprifossillab_P01_backup_plan.md) |
| koprifossillab 001 | 2026-09-30 | [매주 월요일 새벽: 운영 자료 백업과 KPDC 목록 갱신](20260930_koprifossillab_001_weekly_backup.md) |
| koprifossillab 002 | 2026-09-30 | [`/healthz/` — 판·DB·백업 상태를 한 장으로](20260930_koprifossillab_002_healthz.md) |
| koprifossillab P02 | 2026-10-01 | [바람을 온 지구 화면에서 흐르게 (계획)](20261001_koprifossillab_P02_wind.md) |
| koprifossillab 003 | 2026-10-01 | [바람 1 단계 — 받고 굽고 내주기](20261001_koprifossillab_003_wind_data.md) |
| koprifossillab 004 | 2026-10-01 | [아라온호 위치를 매시간 쌓는다](20261001_koprifossillab_004_araon_track.md) |
| koprifossillab 005 | 2026-10-01 | [cron 은 /srv/GSM/scripts 의 사본을 전용 venv 로 돈다](20261001_koprifossillab_005_srv_scripts.md) |
| koprifossillab 006 | 2026-10-01 | [아라온호 항적을 지도에 — 온 지구와 극지 탭](20261001_koprifossillab_006_araon_layer.md) |
| koprifossillab 007 | 2026-10-01 | [바람 2 단계 — 온 지구 화면에 바람을 흘린다](20261001_koprifossillab_007_wind_layer.md) |
| koprifossillab 008 | 2026-10-01 | [지금의 바람 — 예보도 받아 지금 시각으로 섞는다](20261001_koprifossillab_008_wind_forecast.md) |
| koprifossillab 009 | 2026-10-01 | [아라온호 지난 1 년 항적 — 날짜는 하루 단위로](20261001_koprifossillab_009_araon_past.md) |
| koprifossillab P03 | 2026-10-01 | [구름 — 모델 구름량을 바람과 같은 시각으로, 다음에 위성 적외선 (계획)](20261001_koprifossillab_P03_cloud.md) |
| koprifossillab 010 | 2026-10-01 | [온 지구 — "움직이는 지구" 레이어군](20261001_koprifossillab_010_earth_in_flux.md) |
| koprifossillab 011 | 2026-10-01 | [구름 1 단계 — 모델 구름량을 바람과 같은 시각으로](20261001_koprifossillab_011_cloud.md) |
| koprifossillab 012 | 2026-10-01 | [구름 2 단계 — 위성이 찍은 지금의 구름 (NOAA GMGSI)](20261001_koprifossillab_012_sat_cloud.md) |
| koprifossillab 013 | 2026-10-01 | [매시 받기를 한 줄로 — 그리고 `/healthz/` 가 지켜본다](20261001_koprifossillab_013_hourly.md) |
| koprifossillab 014 | 2026-10-01 | [해류 1 단계 — ECCO2 표층 한 날을 온 지구에 흘린다](20261001_koprifossillab_014_ocean_current.md) |
| koprifossillab 015 | 2026-10-01 | [해류 2 단계 — 달마다 한 장, 1992–2019](20261001_koprifossillab_015_ocean_monthly.md) |
| koprifossillab 016 | 2026-10-01 | [바람과 해류를 같이 켜도 갈리게 — 색 계열과 선의 결](20261001_koprifossillab_016_flow_colors.md) |
| koprifossillab 017 | 2026-10-01 | [아라온호 항적 — 기간을 고르고, 오래된 것일수록 옅게](20261001_koprifossillab_017_araon_period.md) |
| koprifossillab 018 | 2026-10-01 | [바람·해류의 빠르기 범례](20261001_koprifossillab_018_flow_legend.md) |
