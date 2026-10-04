# 페루 — INGEMMET 의 광물 산지·광상·광화대, 부게 이상·항공 자력

2026-10-05 · `feature/peru-resources` · wetherilli

남미 광물·지구물리(265)에서 페루만 남겼던 것이다. 페루 문은 상류의 타일 캐시를 중계하는 기계(`ingemmet/<판>/z/x/y`)라 미뤘는데,
단층·습곡(222)과 지질 단위만의 판(234)이 이미 "다른 서비스의 `export` 를 타일 칸만큼" 받는 길을 냈다. 그 길에 표(`RESOURCES`)
하나를 더 얹었다.

| 레이어 | 서비스 | 수 | 처음 줌 |
|---|---|---|---|
| 광상 | `SERV_METALOGENETICO` 1 | 1 672 | 7 |
| 광산 사업·가동 광산 | `SERV_METALOGENETICO` 0 | 532 | 7 |
| 금속·비금속 광물 산지 | `SERV_OCURRENCIA_MINERAL` 0·1 | 1 859·686 | 7 |
| 금속 광화대 | `SERV_METALOGENETICO` 4 | 면 66 | — |
| 부게 중력 이상 | `SERV_GEOFISICA` 5 | 래스터 | — |
| 항공 자력 | `SERV_AEROMAGNETIICO` (ImageServer) | 래스터 | — |

## 왜 이렇게

- **타일 칸 export 를 그대로 썼다.** 서비스가 4326 이어도 `bboxSR`·`imageSR` 3857 로 물으면 된다. 한 칸이 2–3 초(2026-10-05, 페루 전체 400×560 도 2–3 초)
- **항공 자력은 ImageServer** 라 `exportImage` 다. 그냥 받으면 조사하지 않은 곳이 흰 바탕이다 — `noData=255,255,255` 와
  `noDataInterpretation=esriNoDataMatchAll`, `png32` 로 비웠다
- **누른 자리는 REST `query`** — 점 레이어는 화면이 보낸 8 픽셀만큼의 도(`r`)로 네모를 지어 묻고, 가까운 것 셋. 상류가 페이지 나눔을 받지
  않아 `resultRecordCount` 를 붙이면 400 이다. 면(광화대)은 그 점으로
- 광상과 사업은 한 표를 상류가 둘로 거른 것이다(열이 같다). 둘 다 두었다 — 사업은 지금 움직이는 곳만 따로 보고 싶을 때다
- 광물 산지는 **남위 10–18° 의 연구 띠만** 덮는다(Capabilities 의 범위). 제목에 적었다
- 산지의 `TIPO` 는 글자가 깨져 온다(`Met\xa0lico`) — 레이어가 이미 금속·비금속으로 갈라 싣지 않는다
- 범례는 두지 않았다 — 기호가 광종마다 수십 가지라 상류 범례 그림이 크다. 누르면 광종이 뜬다
- 비상업(CC BY-NC-SA 4.0)이라 정적 판에 싣지 않는다 — 페루 상류 전체가 이미 그렇다

## 버린 것

- 광업 권리(`SERV_CATASTRO_MINERO`)는 면이 수만이라 다음으로 미뤘다(TODOs). 지화학 지도첩·산업 광물도 그렇다
- `SERV_GEOFISICA` 의 중력 측점·자기지전류 측선은 점·선뿐이라 뺐다

## 확인

- 사본 DB: 광상 Azúca(Au,Ag · Exploracion · 자원량), 산지 Cerro Campana Ragra(Zn - Cu · 상세 링크), 광화대 XV(반암 Cu-Mo …) 팝업.
  다섯 레이어 타일 200(1.7–2.2 초)
