# 남호주 지구물리 — SARIG 의 영상 WMS 가 있었다 (306 을 바로잡는다)

2026-10-05 · `feature/sa-grids` · wetherilli

판 세션이 맡긴 일은 "SARIG 의 자력·중력·방사능 원본 격자를 받아 ADMAP 꼴로 굽기" 였다(정리 목록 7번). 격자를 찾으러 SARIG 의 자료 목록(CKAN,
`catalog.sarig.sa.gov.au/api/3/action/package_search`)을 한 번 물었더니 첫 쪽에 **"Geophysical regional imagery web service"** — `services.sarig.sa.gov.au/raster/GeophysicalStateImages/wms`
(CC BY 4.0)가 있었다. **wetherilli 306 의 "열린 길을 찾지 못했다" 는 틀렸다** — 306 은 `sarigdata.pir.sa.gov.au` 와 ArcGIS 경로만 보고 `services.sarig.sa.gov.au` 를 보지 않았다.
`data.sa.gov.au` 의 CKAN 은 막혔지만 SARIG 자신의 CKAN 은 열려 있었다.

## 붙인 것

GeoServer WMS, 레이어 스물아홉(총자력의 여러 변환·중력·방사능 원소별·DTM). 3857 로 그리고 축척 끝이 없다. 지질학자가 많이 보는 여섯을 골랐다 —

| 레이어 | 상류 |
|---|---|
| 총자력 (극 환원) | `tmi_vrtp` |
| 총자력 1차 수직 미분 | `tmi_vrtp_1vd` |
| 총자력 기울기 | `tmi_vrtp_tilt` |
| 부게 중력 | `grav` |
| 중력 1차 수직 미분 | `grav_1vd` |
| 방사능 삼색 (K·Th·U) | `rad_rgb` |

- 문은 남호주 문(`austates.py` 의 GSSA) — 레이어 표에 여섯, 이 여섯만 다른 주소(`GSSA_IMAGERY_URL`)로 간다. 이름을 `gssa:` 로 두어 남호주의 메타타일 줄(`gssa:`, wetherilli 287)에
  그대로 든다 — 512 px 1.2–1.4 초, 1 024 px(칸 넷) 2.4–3.2 초라 칸마다 받는 것의 절반이다
- **누르지 않는다** — GetFeatureInfo 가 값이 아니라 칠한 RGB(`RED_BAND`…)를 준다. 범례도 없다(퀸즐랜드 지구물리 영상과 같다)

## 원본 격자 — 굽지 않았다

값을 누르려면 격자를 구워야 한다. 목록에서 본 크기 — 2025 주 방사능 합본 ZIP 43 MB, 2016 중력 격자·영상 ZIP **4.7 GB**, 2021 주 총자력 합본은 PDF·PNG 만 보였다.
영상 WMS 가 있어 화면에 보이는 것은 이제 GA 온 나라 격자보다 고르고 많다. 값 누르기만을 위해 수 GB 를 받아 굽는 것은 이번 일의 몫을 넘는다고 보고 실측만 적는다.
하게 되면 방사능 합본(43 MB)이 가장 싸다.

## 확인

`verify_layers` 의 길로 여섯 모두 그림(격자 줌 5, 남호주 전체).
