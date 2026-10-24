# 극지 탭 — 과학 해양 시추공(DSDP·ODP·IODP)과 남극 대륙붕 시추를 점 레이어로

2026-10-23 · `feature/polar-boreholes` · wetherilli

극지 자료 2 차 조사(`docs/극지_자료_후보.md` "## 2 차 조사", 순위 4)의 하나. 남극·북극 탭에 시추 자리가 없었다 — 해저 코어를 쓰는
연구는 "어느 공이 여기 있나" 부터 묻는다.

## 상류와 조건

- `https://kml.iodp.org/Drilled_Holes.csv` — 690 KB, 4 283 공, Last-Modified 2025-12-09. 열은 레그(DSDP·ODP)·항차(IODP)·사이트·공·
  위경도·도착 일시·수심·뚫은 길이·회수 길이·코어 보기·검층 링크. 열쇠·CORS 머리 없음. 남위 60° 남쪽 115 공, 북위 66° 북쪽 112 공
- 목록과 `kml.iodp.org` 첫 화면에는 조건이 한 줄도 없다. 그래서 시추 프로그램의 자료 정책을 읽었다 —
  「Scientific Ocean Drilling Programs Sample, Data, and Obligations Policy」(gcr.tamu.edu, "becomes effective on October 1, 2024",
  DSDP·ODP·IODP·IODP³ 의 시료·자료에 걸린다):
  > After the moratorium period ends, samples are given or loaned to persons whose requests have been approved by a Scientific
  > Ocean Drilling Curator. Project data are publicly available after the moratorium period.

  > Researchers are requested to comply with the following acknowledgement guidelines in their publications: …
  > Acknowledge the scientific ocean drilling program (i.e., IODP3, US Scientific Ocean Drilling, … ODP, DSDP) …
- 비공개 기간(대개 항차 뒤 1 년)은 **시료와 선상 자료**에 걸린다. 공의 자리는 항차 보고서·이 목록으로 이미 열려 있다.
  저장·가공 금지나 비상업 조건은 없다 — "미국 연방 과학 자료라 열려 있을 것" 이라는 추정은 **열려 있고, 프로그램을 밝혀 달라**
  로 맞았다. 그래서 묻지 않고 붙였다. 범례의 원본 자료 글에 "프로그램을 밝힌다" 를 적었다

## 틀 — 새 화면 길 없이 `earthpoints` 에 한 자료로

지역 탭의 지구 자료 점(wetherilli 185·390)이 이미 "모아 둔 파일 → 지역의 네모 → `kind: points`·`style: class` GeoJSON" 을 한다.
시추공은 점 하나에 열 몇 개라 그 틀에 꼭 맞다. `earthpoints.SOURCES` 에 `iodp` 를 더하고 씨앗 둘(`earth_antarctica`·
`earth_arctic_ocean`)에 "시추" 레이어군을 두었다 — 북극은 북극해에 두면 그린란드·스발바르… 가 빌린다(map.js 의 `borrow`).
화면(map.js)은 손대지 않았다.

- **극지 탭에만** — `POLAR_ONLY` 로 다른 묶음(유럽·북미…)의 레이어 이름이 생기지 않게 했다. 맡은 것이 극지라서다.
  온 세계의 4 283 공은 파일에 다 있으니 묶음에 더하는 것은 씨앗 한 줄씩이다
- 문은 `iodp.py` 하나(받기 + 읽기, scar.py 처럼). 받기는 `fetch_iodp_holes` 가 한 번 — 1 초 간격이 필요 없는 한 요청이다.
  cron 에 두지 않는다. `<EARTH_DIR>/iodp_holes.json`(줄인 것 600 KB 남짓)
- 색은 프로그램 넷 — DSDP·ODP·IODP·남극 대륙붕 시추(손으로 더한 것). 레그 1–96 은 DSDP, 100–210 은 ODP, `expedition` 이 있으면 IODP
  (Integrated·International·IODP³ 를 가르지 않았다 — 목록이 가르지 않는다)
- 누르면 공 이름·프로그램·항차·시추 일시·해저 수심·뚫은 길이·회수한 코어·코어 보기·검층 자료. "수심 (m)" 은 이미 "Depth (m)" 로
  옮겨지는 말이라 뚫은 길이와 헷갈리지 않게 "해저 수심 (m)"(Water depth) 으로 따로 두었다
- 도착 일시의 꼴이 여섯 가지다(`07/18/2024 04:00`·`9/7/24`·`11/2005` …). 두 자리 해는 60 부터 1900 년대. `01/00/1900` 은 빈 값

## 죽은 링크

DSDP 의 "코어 보기"(`www.ngdc.noaa.gov/mgg/geology/dsdp/…`, 1 064 공)는 2026-10-23 에 http 는 https 로 넘기고 https 는 403 이었다
(브라우저 UA 로도). NCEI 가 내린 자리다. 죽은 링크를 팝업에 걸지 않으려고 담지 않는다(`iodp.DEAD`). 검층 링크(LDEO)는 산다.
DSDP 공은 코어 보기 링크 없이 선다 — 대신 걸 안정된 쪽(deepseadrilling.org 의 보고서 권)은 공마다의 주소가 아니라 두지 않았다.

## 손으로 더한 것 — ANDRILL·CRP·CIROS·MSSTS

IODP 목록에 없는 맥머도 해협의 해빙·빙붕 위 시추 여덟을 `data/polar_boreholes.json` 에 두었다. 자리·일시·수심·뚫은 길이·회수 길이는
**PANGAEA 자료의 Event(s) 줄을 그대로** 옮겼고, 줄마다 그 자료의 DOI 를 `source` 로 — 팝업의 링크가 된다.

| 공 | PANGAEA |
|---|---|
| MSSTS-1 (1979) | 52013 |
| CIROS-1 (1986) · CIROS-2 | 52025 · 55366 |
| CRP-1 · CRP-2A · CRP-3 (1997–99) | 667128 · 58401 · 734089 |
| AND-1B (2006) · AND-2A (2007) | 858483 · 743269 |

- "수심" 은 이벤트의 ELEVATION 을 뒤집었다. AND-1B 의 −917 m 는 빙붕 밑 물까지의 값으로 보인다 — 그대로 둔다
- **CRP-3 의 자리가 의심스럽다.** PANGAEA 는 −77.006, 163.719 로 CRP-2A 와 거의 같게 적었는데, 같은 줄의 설명은 "11.76 km at 76° true
  from Cape Roberts, 2.04 km at 225° true from CRP-2" 다 — 2 km 떨어져야 한다. 설명에서 셈하면 둘이 서로도 1 km 남짓 어긋나서 어느 것이
  맞는지 모른다. 상류의 값을 고치지 않고 옮겼다. 초기 보고서(Terra Antartica 7)를 볼 사람이 고친다
- CIROS-2 는 일시가 없다(PANGAEA 가 적지 않았다). 1984 년이라 알지만 근거 없이 적지 않았다
- 더 찾지 않은 것 — DVDP(드라이밸리, 1971–76)·SHALDRIL·SMS 의 다른 공. TODOs 에 남긴다

## 정적 판

**싣지 않았다.** 조건은 열렸지만 지역 탭의 지구 자료 점은 모두 서버의 `points/` 길이고, 정적 판에 실으려면 덩이를 따로 굽는 손이
든다(wetherilli 185 와 같은 까닭). 

## 다음 (TODOs)

- **온 지구 화면** — 틀이 다르다. 온 지구의 점 자료는 서버가 경위도 타일로 굽고(`volcanoes.render_tile` 따위) 누른 자리는 `*_at`
  으로 묻는다. 아라온 항적처럼 GeoJSON 을 Cesium 개체로 얹는 길도 있지만 화면 코드가 백 줄은 든다. 이번에는 하지 않았다
- 극지 밖 묶음에 더하기(씨앗 한 줄씩), 손으로 더할 공 더 찾기

## 판에서 고친 것 (2026-10-23, 판 1.3.0)

`_KEEP["iodp"]`(점이 `CAP` 을 넘어 모을 때 남길 것을 고르는 값)가 팝업용으로 천 자리 쉼표를 넣은 `penetrated`("1,234.5")를 `float` 로 바꾸다 깨질 자리였다 — 시추공은 4 천 남짓이라 닿지 않았지만 판 세션이 쉼표를 빼고 읽게 고쳤다.
