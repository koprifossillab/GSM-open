# 수성 — 화성 화면을 옮겨 짓는다 (계획)

2026-10-02 · `feature/mercury` · wetherilli

판 세션(gsm-31)이 맡긴 일이다 — `docs/새_상류_후보.md` §1 의 "수성 화면(달·화성의 틀)", TODOs "달" 의 끝줄.
아래는 오늘 상류를 한 장씩 쏴 보고 적은 것이다. 갈림길 셋(지질도·테마·공개)은 사람이 골랐다(§6).

> **같은 날 고쳐 썼다.** Trek 의 5M 도폭 일곱은 **타일이 비어 있다** — Capabilities 는 200 인데 도폭 한가운데 타일이
> 모두 404 이고(같은 자리의 MESSENGER 모자이크는 200), Capabilities 가 가리키는 ArcGIS 서비스도 "not found" 다.
> "Trek 그림 먼저" 가 설 수 없어 사람에게 다시 물었고, **1 단계는 지질 없이, 셰이프파일 굽기는 2 단계**로 정했다.
> 아이콘·대기 화면 그림도 사람이 1 단계 중에 주었다. 고친 자리는 §0·§1·§2·§6 이다.
>
> **2 단계에서 한 번 더 고쳤다.** Hunter(2016) 판은 내려받는 자리가 닫혀 있었다(S3 에 파일 없음, ScienceBase 는 Cloudflare
> 확인 화면). 같은 도폭 아홉을 이은 **Frigeri 외(2008) 합본**을 PIGWAD 에서 받아 구웠다 — 사람이 골랐다. 마리너 10 시절
> 좌표이고 시대 열이 없다. 고친 자리는 §2·§4 다 (wetherilli 144).

## 0. 한 줄

**`/GSM/mercury/` — 화성 화면(058)을 옮긴 따로 화면이다.** 문은 새로 내지 않고 `trek.py` 를 넓힌다 — NASA Trek 에
수성(Mercury Trek)이 있고 주소 꼴이 달·화성과 같다. 지질도는 **1980–90 년대의 1:500만 도폭을 MESSENGER 바탕에 맞춘
판**(USGS, Hunter 2016)이다 — Trek 의 타일이 비어 있어 셰이프파일을 우리가 굽는다(2 단계). 1 단계는 영상·표고·지명·점묶음이다.

## 1. 쏴 본 것 (2026-10-02)

### Mercury Trek — 달·화성과 같은 꼴

| 자리 | 주소 | 확인 |
|---|---|---|
| 색인 | `trek.nasa.gov/mercury/TrekServices/ws/index/eq/searchItems` | 200. 판 53·지명 517·둘러보기 1 |
| 판 타일 | `trek.nasa.gov/tiles/Mercury/EQ/<판>/1.0.0/…` | 200, **CORS `*`**. 경위도 격자(가로 2·세로 1) |
| 표고 | `trek.nasa.gov/mercury/arcgis/rest/services/mercury/Mercury_Messenger_USGS_DEM_Global_665m_v2/ImageServer` | `exportImage` F32 TIFF 200 |
| 극 표고 | 같은 폴더 `…_NPole_665m_v2_32bit`·`…_SPole_…` | 있다 |
| 지명 | 같은 폴더 `Mercury_Nomenclature_EQ/NP/SP` (MapServer) | 있다. 색인에도 517 |

**달·화성과 다른 것 둘.**

- ArcGIS 의 뿌리가 `trekarcgis/` 가 아니라 **`arcgis/rest/services/mercury/`** 다(`trekarcgis` 는 404). `_get` 의 뿌리를
  몸마다 따로 둔다
- **극 평사도법 판 타일이 없다**(`tiles/Mercury/NP/…` 404, 색인 `index/np` 404). 극 표고 ImageServer 만 있다

판 53 의 갈래 — 전 지구 영상 모자이크 넷(MDIS 250 m 2013·BDR 166 m·LOI 166 m·강조색 665 m·MD3 색·색 v3),
전 지구 DEM 과 음영·색 음영·경사, 지역 정사영상·DEM·경사 서른 남짓(크레이터 벽·봉우리 고리), 중력·지각 두께(HgM008),
**5M 지질 도폭 일곱**(Beethoven·Discovery·Kuiper·Michelangelo·Shakespeare·Tolstoj·Victoria).

### USGS Astrogeology WMS — 쓰지 않는다 (지금은)

`planetarymaps.usgs.gov/…/mercury_simp_cyl.map` 은 200·CORS `*` 이고 `MESSENGER`·`MESSENGER_Color`·`MARINER`·
`MESSENGER_Mariner`·`Mercury5M_Quads`(도폭 경계·이름) 를 준다. 극 판(`mercury_npole.map`·`_spole.map`)도 있다.
**Trek 이 같은 모자이크를 타일로 주므로 영상은 Trek 하나로 간다** — 한 몸의 배경을 두 상류로 나누면 "이 그림이 어디서
왔나" 를 답하기 어려워진다. 다만 둘은 쓸 자리가 있다.

- **`Mercury5M_Quads`** — 도폭 경계와 이름. Trek 에 없다. 지질도를 구울 때(2 단계) 함께 얹을지 본다 — 도폭이 아홉 조각이라
  어디가 빈 줄 보여 준다
- **`MARINER`** — 1974–75 마리너 10 의 모자이크. 역사로 둘 만하다 — 1 단계에는 넣지 않았다

### 지질도 — 전 지구 판이 아직 없다

판 세션이 짚은 **SIM 3456 은 수성 지질도가 아니다** — 콜로라도 Fountain Creek 의 표고 변화도다(pubs.usgs.gov 에서 확인).
수성의 첫 전 지구 지질도(Kinczyk 외, 1:1500만)는 2015–2019 학회 초록까지만 있고 USGS SIM 으로 나온 것을 찾지 못했다.
쓸 수 있는 것은 하나다.

| | |
|---|---|
| 이름 | **Mercury 5M GIS Conversion v2** — Marc Hunter, USGS Astrogeology, 2016-05-16 |
| 든 것 | 1:500만 도폭 **아홉**(Bach·Beethoven·Borealis·Discovery·Kuiper·Michelangelo·Shakespeare·Tolstoj·Victoria) — 1984–1990 I 시리즈(I-1408·1409·1658·1659·1660·2015·2048 …)를 1999 년에 GIS 로 옮긴 것을 **PAEK 10 km 로 다듬고 2013 MESSENGER 바탕에 사영 변환으로 맞췄다**. 면과 경계선 |
| 받는 곳 | `asc-astropedia.s3.us-west-2.amazonaws.com/Mercury/Geology/Mercury_5M_GIS_conversion_v2.zip` (710 MB) |
| 반지름 | **2 439 000 m** — Mercury 2000(2 439 700 m)보다 조금 작다 |
| 조건 | 접근·이용 조건 "None" |

Trek 의 `Mercury_5M_*` 일곱이 이것을 그린 타일이라고 색인이 적는다(Bach·Borealis 는 Trek 에 없다). **그러나 타일이 없다**
— 격자가 달·화성의 판과 다르게 적혀 있고(줌 0 이 3×3), 도폭 한가운데를 덮는 타일을 줌 0–5 에서 물어도 다 404 다. MapServer 도
없어 누른 자리의 단위도 읽을 수 없다. 씨앗 뽑기(`fetch_trek_catalog`)도 이 일곱을 타일 판으로 받지 않는다. 마리너 10 은 수성의 45 % 남짓만 찍었으므로 도폭도 그만큼이다 — 지질도가 덮지
않는 반쪽이 남는다.

## 2. 무엇을 짓나 — 단계

### 1 단계 — 화면 (wetherilli 137)

| 자리 | 무엇 |
|---|---|
| 문 | `trek.py` 에 `mercury_*` 마디 — 표고 격자(`mercury_dem_tile`)·점 표고(`mercury_values`)·색인. `BODIES["mercury"]`, `settings.TREK_MERCURY_URL` |
| 화면 | `mercury.js`·`mercury.html` — `mars.js`·`mars.html` 을 복사해 고친다. 이름(`eva`·`LANDING_*`·`moon-*` 클래스)을 그대로 두어 셋을 견주기 쉽게 |
| 영상 배경 | MDIS 250 m 2013(기본)·BDR 166 m·강조색 665 m·색 음영 — Trek WMTS 를 브라우저가 곧장 |
| 지질 | **없다.** 레이어 목록에 "준비 중" 한 줄. 지질 틀(`CATALOG`·`geoUrl`·범례)은 화성의 것을 비운 채 둔다 |
| 판 목록 | `fetch_trek_catalog --body mercury` → `data/mercury_trek_layers.json`. 한글 제목은 사람이 손보는 칸이라 규칙으로 채운다(080) |
| 지명 | `fetch_moon_places --body mercury` → `data/mercury_places.json` |
| 점묶음 | `PointSet.body` 에 `mercury`. 표고는 USGS DEM 665 m |
| 평면 | 위도 65° 너머는 극 평사도법 — 극지 판이 없으니 **경위도 타일을 OpenLayers 가 옮겨 그린다**(080 이 판 목록에 한 것) |
| 들어가는 길 | 숨은 차림·몸 탭에 수성 하나 더(지구·달·화성 화면 모두) |
| 아이콘·대기 화면 | 사람이 준 그림(`daedol_mercury.png`·`…_build_animation.gif`) — 달·화성·극지와 같은 꼴로 오려 꽂는다 |

**뺀 것.** 착륙지·로버 경로(수성에 내린 것이 없다 — MESSENGER 의 충돌 자리 하나는 지명으로 찾게 할지 1 단계에서 본다),
원도 굽기(화성의 068), 크레이터 목록(067), 화성의 주룽.

### 2 단계 — 5M 지질도를 우리가 굽는다 (wetherilli 144)

`marsmap.py`(068)의 틀을 빌려 `mercurymap.py` — 셰이프파일 → sqlite(R*Tree) → 수성 경위도 타일·누른 자리의 단위·범례.
아홉 도폭 전부, 속성(단위 기호·무리·설명·원도 색)과 구조선 넷(급사면·능선·단층·분지 고리). 원본은 Hunter 판이 아니라
Frigeri 외(2008) 합본이다(머리말). 원본은 NAS `N:\GSM\sources\` 에, 구운 것은 `<DB 옆>/mercury`
(`GSM_MERCURY_DIR`). 도폭 경계·이름(USGS WMS `Mercury5M_Quads`)을 같이 얹을지는 그때 본다 — 지질이 없는 반쪽이 어디인지 보여 준다.

### 3 단계 — 전 지구 지질도가 나오면

Kinczyk 외의 1:1500만이 USGS 판으로 나오면 그것을 기본 지질도로 올리고 5M 은 "옛 도폭" 갈래로 내린다.

## 3. 수성의 크기와 좌표

- **구다.** 화성(058)과 같은 까닭이다. 반지름은 Trek 의 경위도(`GCS_Mercury_2000`, ESRI `104974`)가 적는 **2 439 700 m**.
  표고 판은 2 439 400 m 구에서 잰다 — Cesium 에 얹을 때 높이는 그 기준의 값을 그대로 쓴다(수백 m 의 차는 1 단계에서
  견주어 적는다)
- 우리 이름은 PSDI 의 `IAU_2015:19900`(경위도)·`19910`(등거리 원통)·`19930`/`19935`(극 평사) — 달 30100·화성 49900 의 짝.
  상류에 물을 때만 `104974` 다. 그 바꿈은 `trek.py` 에만 둔다
- 평면·구 문턱 — 수성은 달(1 737 km)보다 크고 화성(3 396 km)보다 작다. 달 250/400 km 과 화성 400/640 km 사이에서
  반지름 비로 **350/560 km** 를 잡는다
- "처음" 단추 — 경도 0°·위도 0°. 수성의 본초 자오선은 Hun Kal 크레이터(20°W)로 정한다

## 4. 지질시대

5M 도폭의 시대는 **수성의 다섯 기**다 — 선톨스토이기(pre-Tolstojan)·톨스토이기(Tolstojan)·칼로리스기(Calorian)·
만수르기(Mansurian)·카이퍼기(Kuiperian). 이름은 기준이 된 분지·크레이터(톨스토이·칼로리스·만수르·카이퍼)에서 왔다.
한국어는 달·화성처럼 **땅 이름 + 기** 로 옮긴다 — ICS 밖이라 한글판 표가 없다. **사람이 다시 본다.**

**2 단계에서는 시대를 매기지 않았다**(wetherilli 144). 합본에 시대 열이 없고, 크레이터 물질의 등급(c1–c5)을 다섯 기에 잇는
법이 도폭마다 조금씩 다르다. 누르면 등급(c1 가장 닳음 … c5 가장 또렷함)만 보이고, 범례는 갈래로 묶는다. 전 지구 지질도(3 단계)가
나오면 그때 시대로 묶는다.

## 5. 이용 조건과 출처

- Trek·USGS 의 자료는 미국 정부 저작물이고 5M GIS 의 조건은 "None" 이다 — **밖에 연다**(`LAB_ONLY` 에 넣지 않는다)
- 출처 표기: MESSENGER MDIS — **NASA/Johns Hopkins University Applied Physics Laboratory/Carnegie Institution of
  Washington**. 표고 — USGS(Becker 외, 2016). 5M 지질 — 원도의 저자들과 USGS(Hunter, 2016). Trek — NASA/JPL-Caltech
- 판 목록의 지역 DEM·정사영상은 MESSENGER 팀 산출물이라 같은 표기로 묶는다

## 6. 사람이 고른 것 (2026-10-02)

| 갈림길 | 고른 것 |
|---|---|
| 지질도 | Trek 그림 먼저, 셰이프파일 굽기는 다음 단계 → Trek 타일이 비어 **1 단계는 지질 없이, 굽기는 2 단계** |
| 테마 | **MESSENGER 강조색 — 청회색·황갈.** 강조색 모자이크의 푸른 저반사 물질(LRM)과 황갈 평원(HRP)에서 딴다 |
| 공개 | 밖에도 연다 |

버린 것 — "처음부터 셰이프파일을 굽는다"(첫 PR 이 늦어진다), "지질 없이 영상·지형만"(5M 이 반쪽이라도 있다),
테마 "흑백"(달과 갈리지 않는다)·"금빛"(지구 한국 탭의 금과 겹친다).

## 7. 겹침

`mars.js` 를 옮기므로 **달·화성을 고치는 세션과 한 짐을 진다** — CLAUDE.md 의 "달 화면을 고치면 화성에도 옮길지
본다" 를 "화성·수성" 으로 넓힌다. 공통 틀(`trek/<몸>/map/…`·`client_catalog`·`fetch_trek_catalog`)의 몸 목록에
`mercury` 를 더하는 것은 이 브랜치가 한다. 지구 화면(`map.js`·`earth.js`)은 숨은 차림에 한 줄을 더하는 것뿐이다.
