# 그린란드 — GEUS ArcGIS 의 자력 편찬·DTU 부게 중력·지질구

2026-10-05 · `feature/greenland-more` · wetherilli

미국·호주·캐나다·일본·영국과 같은 꼴로 그린란드에도 지구물리를 더했다. 그린란드 정부 포털(grportal)의 광물 산지·화학 점은 이미 다
실려 있어(019·160) 새로 붙일 것이 없었고, 새 것은 GEUS 쪽에서 나왔다.

## 찾기

- 지도 서비스(`greenland_portal` WMS)의 Capabilities 에 든 열 레이어는 이미 다 실려 있다
- GEUS 지도 화면(`data.geus.dk/geusmap/?mapname=greenland_portal`)의 코드에 레이어 61 개가 있다 — 지구물리(`grl_geophysic_aeromag_magnetic`·
  `grl_geophysical_magnetic_compilation`·`grl_geophysic_radiometry`·`grl_geophysical_dtu_magnetic_anomaly`), 지질도 1:250만·50만·10만,
  광물 산지 v3 따위. **그 이름으로 WMS 를 부르면 403** 이다(화면 안쪽에서만 쓴다)
- 범례 주소가 단서였다 — `data.geus.dk/arcgis/rest/services/Greenland/…`. 이 ArcGIS 폴더는 목록이 열려 있다(서비스 21 개)

## 한 것

문은 `geus.py` 안의 `ARC`(상류 이름 `geusarc`). REST `export` 를 3413 으로 받는다(서비스는 UTM 24N).

| 레이어 | 서비스 | 누르면 |
|---|---|---|
| 자력 이상 편찬 | `Magnetic_compilation` 0 (측선 6 은 뺐다) | 없음 |
| 부게 중력 이상 (DTU) | `dtu_bouguer_anomaly` 3 (관측점 0–2 는 뺐다) | 없음 |
| 지질구 (1:250만) | `Geological_provinces_2500k` — 제4기·퇴적분지·표성암·화성구·선캄브리아 기반 | 갈래·지질구 |

## 조건과 whoami

- GEUS 이용 조건(`terms_20140620.pdf`) — **개인 용도**로 쓰고 GEUS 를 출처로 밝힌다. 다시 펴내거나 남에게 내주려면 서면 동의가 든다.
  기존 GEUS 레이어와 같은 조건이라 같은 길(서버가 받아 보이기)로 두고 **정적 판에는 싣지 않았다**. 부게 중력의 저작권 칸은 DTU Space 다
- whoami 는 이 서버에도 붙여 보낸다(ArcGIS 는 쓰지 않지만 GEUS 가 부르는 이를 알 수 있게). 로그·예외 문구에서는 `whoami=…` 로 지운다 —
  사본 DB 로 돌린 로그 32 줄이 모두 지워져 있었다

## 미룬 것

- 방사능은 국지 조사 몇 곳뿐이라 넓게 보면 거의 비어 뺐다. 공중 자력 셋·1:250만·1:10만 지질도는 같은 서버에 있어 더할 수 있다 — TODOs
- 자력 편찬은 넓게 보면 한 장이 47 초 걸렸다(2026-10-05). 캐시가 받아 둔다

## 확인

- 사본 DB 로 그린란드 탭(3413, 줌 3.5): 부게 중력이 섬 전체에 그려지고 페이지 오류 없음. 지질구는 누크 둘레 "선캄브리아 기반 · Archaean basement"
