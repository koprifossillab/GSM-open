# 영구동토 시추공 — GTN-P 지온 관측공을 받아 두고 북극해·남극 탭의 점으로

2026-10-23 · `feature/gtnp-boreholes` · wetherilli

극지 자료 2 차 조사(`docs/극지_자료_후보.md` "2 차 조사" 의 22, 순위 8)의 하나. 스발바르·그린란드·필데스반도의 영구동토 관측공이
지도에 없었다.

## 상류와 조건

- Arctic Portal GeoServer `https://flatey.arcticportal.org/geoserver/page21/ows` — 옛 GTN-P 포털이 쓰던 WFS 다. 문서에 적힌 주소가
  아니라 예고 없이 닫힐 수 있다. 그래서 **화면이 부를 때 타지 않고** `fetch_gtnp` 가 한 번 받아 둔다. 열쇠·CORS 머리가 없다
- 레이어 열여섯 가운데 `page21:tsp`(메타데이터)가 아니라 **`page21:magt`** 를 받는다. 행(1 389)과 번호가 tsp 와 똑같고(`borehole_id`
  = tsp `id`, 깊이도 1 389 모두 같다) 거기에 **1978–2016 의 해마다 연평균 지온**과 그 깊이·추세가 붙어 있다. 지온이 있는 공은 904.
  사람이 바란 "지온(있으면)" 이 이 한 장으로 된다. `magt_composite`(7 146 줄)는 자료 제공자의 전자우편이 들어 받지 않았다
- 조건 — GTN-P 웹 쪽에는 데이터 정책 문서가 남아 있지 않다(포털을 AWI 가 새로 짓는 중이다, EGU25-7435). 근거는 PANGAEA 사본 둘이다:
  - 시추공 메타데이터 `doi:10.1594/PANGAEA.842820` — "GTN-P (2015): Global Terrestrial Network for Permafrost metadata for permafrost
    boreholes (TSP)" · "Creative Commons Attribution 3.0 Unported (CC-BY-3.0)" · "Always quote citation above when using data!"
  - 지온 `doi:10.1594/PANGAEA.884711` — "GTN-P (2018): GTN-P global mean annual ground temperature data for permafrost near the depth
    of zero annual amplitude (2007-2016)" · "Creative Commons Attribution 3.0 Unported (CC-BY-3.0)" (관련 논문 Biskaborn 외 2019, Nat. Commun.)
  - GTN-P 의 출발 때 원칙은 "open data policy with free data access via the World Wide Web"(Biskaborn 외 2015, ESSD)
- 생각(CC BY 3.0)과 같아 묻지 않고 붙였다. WFS 의 `magt` 가 PANGAEA 884711 과 한 글자까지 같은 판인지는 견주지 않았다 — 같은 GTN-P
  데이터베이스에서 나온 것이라 같은 조건으로 본다. 인용은 `gtnp.CREDIT`

## 갈래

- **점 레이어 둘, 지역 둘** — `gtnp:boreholes_arctic`(북극해, 북위 50° 너머, 1 061 공)·`gtnp:boreholes_antarctica`(남극, 남위 60° 너머,
  91 공). 레이어명이 지역 하나에만 걸리므로 둘로 갈랐다. 북극해는 북극 묶음에 들어 북극 탭에서도 선다. 50° 는 KPDC 북극해 레이어와 같은 금이다.
  **몽골·중국·알프스 따위의 공(북위 27–50°, 200 남짓)과 우수아이아는 실을 탭이 없어 뺐다** — 온 지구 화면에 얹는 것은 TODOs 의 "다음"
- **색은 가장 최근 지온의 구간**(−5 밑·−5~−2·−2~0·0 넘음·자료 없음). 영구동토대로 칠하는 것도 견주었다 — 대(Continuous …)는 지도의
  영구동토 분포가 이미 말하는 것이고, 관측공이 주는 새 것은 지온이라 그것을 골랐다. 해가 공마다 달라(2008 이나 2016) 팝업에 해를 함께 적는다
- 꼴은 극지연구소 파일 레이어(`style: class`·`labels`·`legend`)와 같다 — 화면(`map.js`)은 상류 표에 한 줄만 더했다
- 추세(`timeseries_slope`)는 지온이 있는 해가 셋 이상일 때만 싣는다. 한두 해의 기울기는 읽을 것이 못 된다
- 상류의 영구동토대 표기가 대소문자로 갈려 있어(`No Permafrost`·`No permafrost`) 하나로 모았다. 값(나라·지점·대)은 옮기지 않는다
- 자료 책임자 이름은 상류가 공개로 내는 것이고 인용에 쓰여 싣는다. 전자우편은 싣지 않는다

## 정적 판

**싣지 않는다.** 조건(CC BY 3.0)은 열려 있지만 상류에 CORS 가 없어 브라우저가 곧장 못 받고, 정적 판은 `gtnp` 상류를 모른다
(`static_site.UPSTREAMS`). 구워 실으려면 `bake_static` 에 점 덩이를 더해야 한다 — 사람이 정할 때 TODOs 의 "다음" 에서.

## 버린 것

- tsp + magt 두 장을 받아 잇기 — magt 가 tsp 를 다 품는다
- 화면이 부를 때마다 WFS — 문서에 없는 주소이고, 지온이 2016 년에 멈춰 있어 받아 둘 까닭이 더 크다
- 해마다의 지온 서른아홉 열을 다 싣고 화면이 그래프로 — 팝업이 커지고 화면 일이 번진다. 마지막 해의 값과 추세로 줄였다

## 확인한 것

- 받아 둔 CSV(2026-10-23, 한 번)로 `download` 를 돌려 1 389 공 → 북극 1 061·남극 91, 필데스 1 은 −0.9 °C(2008, 0.9 m)
- `manage.py test viewer --parallel 8` 전체 — 2 299 통과(브라우저 없이). playwright 를 깔고 휴대폰 시험(`test_mobile`)을 세 번: 두 번 통과, 한 번은 서로 다른 둘이 깨졌다가 따로 돌리면 통과 — 기계가 load 100 남짓(다른 세션의 시험)일 때라 시간 흔들림으로 본다. 화면은 `map.js` 의 상류 표 한 줄뿐이다
