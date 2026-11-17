# 남극 — InSAR 접지선 1992–2025·빙붕·빙하 유역 (MEaSUREs)

2026-11-17 · `feature/antarctic-boundaries` · wetherilli

Earthdata 토큰으로 풀린 자료를 추린 것(`docs/Earthdata_반입_후보.md`)의 가-1·2 다. 둘 다 NASA MEaSUREs 의 남극 자료이고 작아서 한 갈래로 묶었다.

## 무엇을 들였나

- **InSAR 접지선 v2.1**(NSIDC-0498) — 1992–2025 의 관측 1 820 줄. 남극 탭에는 RAISED(20–5 ka, wetherilli 420)와 Gernon 의 옛 빙상
  범위가 있는데 **지금 움직이는 접지선**이 비어 있었다. 같은 빙하에 해마다 겹친 줄로 파인아일랜드·스웨이츠가 물러나는 것이 보인다.
  색은 해(年)가 아니라 **관측 시기 다섯 칸** — 위성 세대(ERS·RADARSAT → Sentinel-1·COSMO)와 대략 맞고, 서른 해를 서른 색으로 칠하면
  범례가 읽히지 않는다
- **남극 경계 v2**(NSIDC-0709)에서 넷 — 빙붕(181, 이름), 빙하 유역(199, 이름·흘러드는 빙붕·IMBIE 유역), IMBIE 유역(19), 2007–09 접지선.
  3 차 극지 조사가 "ADD 로 갈음" 했지만 **유역과 빙붕 이름은 ADD 에 없다** — 질량 수지·빙하 이름을 읽는 칸이 생긴다

## 굽는 길

- `antpapers`(435)의 틀 그대로 — 서버가 레이어마다 갈래(`code`) 색을 단 GeoJSON 한 덩이를 낸다(`points/`). 3D·구의 격자로는 펴지 않는다
- **numpy 없이 컨테이너에서** 돈다 — 셰이프는 `geo3al.read_polygons`·`read_dbf`, gpkg 는 `geomap.parse_geometry`, 줄이기는
  `antpapers.simplify`. 새 읽개를 쓰지 않았다
- 구운 것은 저장소 밖(`<GLACIO_DIR>/antarctic_boundaries.json`, RAISED·빙저호와 같은 자리). 7 MB 라 저장소에 두지 않는다
- 처음엔 12 MB 였다 — InSAR 접지선의 조각 1 만 9 천을 줄마다 따로 적어 속성이 거듭 실렸다. **관측 하나 = 피처 하나(MultiLineString)** 로 묶고
  허용을 60 → 120 m, 좌표를 소수 넷째 자리로 줄여 4.6 MB(gzip 1.3 MB)

## 버린 것

- **해안선**(NSIDC-0709 의 `Coastline`) — ADD 해안선(KPDC 지도 서버)이 이미 남극 탭에 있다
- **마스크 래스터**(122 MB) — 빙붕·접지선 면이 같은 것을 말한다
- **`IceBoundaries`** — 유역과 빙붕을 합친 것이라 둘을 따로 둔 지금과 겹친다
- **접지대 NSIDC-0778** — 휘는 띠라 선과 다른 손이 든다. 1 820 줄로 먼저 쓰임을 본다
- 해(年)마다 레이어 — 시기 다섯 칸의 색으로 갈음했다. 연대 막대(439)에 얹는 것은 쓰임이 보이면
