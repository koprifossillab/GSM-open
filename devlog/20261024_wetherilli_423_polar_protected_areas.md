# 극지 보호구역 — 남극 ASPA 2024 와 스발바르 자연보호구역을 레이어로

2026-10-24 · `feature/polar-protected-areas` · wetherilli

극지 자료 2 차 조사(`docs/극지_자료_후보.md` "2 차 조사")의 2 순위. 현장에서 실제로 걸리는 것 — 세종 바로 옆의 ASPA 171
나렙스키 포인트, 장보고 둘레의 ASPA 161·165 — 를 지도에서 볼 길이 없었다.

## 1 단계 — 남극 특별보호구역 ASPA 2024 (AADC)

### 상류와 조건

- Terauds 외(2024) "Antarctic Specially Protected Areas (Points and Polygons) 2024 Update", AADC 자료 저장소(EDS) 5998,
  uuid `b4c92f68-…`. 2018 판에 그 뒤 지정·해제된 것(144 해제, 176–179 지정)을 더한 판이다
- 조건 — 자료 안의 `LICENSE` 가 "Creative Commons Attribution 4.0 International", `README` 가 "This data set conforms to the CCBY
  Attribution License" 라 적는다(2026-10-24 에 받아 읽었다). 저장·가공을 막는 말은 없다. 인용 꼴은 `aadc.CREDIT`
- AADC GeoServer 에는 ASPA 레이어가 없다(1 차 조사) — 파일을 받아 우리가 그린다

### 받는 길 — 이메일을 적지 않으려고 파일마다

조사 문서에 적힌 `https://data.aad.gov.au/eds/5998/download` 는 SPA 화면이고, 그 화면이 부르는 `/eds/api/dataset/5998/download` 는
`{"error": {"showEmailForm": true}}` 를 준다 — **묶음 zip 은 이메일 주소를 POST 해야 넘겨 준다.** 이메일을 저장소나 설정에 두는 것은
GEUS 의 `whoami` 처럼 따로 숨길 자리를 하나 더 만드는 일이라 버렸다.

자료 화면이 파일 목록에 거는 주소 `/eds/api/dataset/<uuid>/object/download?prefix=<경로>` 는 열쇠·이메일 없이 302 로
`transfer.data.aad.gov.au` 의 하루짜리 서명 주소를 준다. 그래서 필요한 열둘(면·점의 `.shp·.shx·.dbf·.prj·.cpg`, `LICENSE`·`README`)만
1 초 간격으로 받는다. 서명 주소는 로그에 남기지 않는다(묻은 `prefix` 만). 화면이 쓰는 문서 밖의 주소이므로 바뀌면 `aadc._file_url` 하나만
고친다.

### 문을 따로 낸 까닭

같은 AADC 의 WFS 로 받는 SCAR 지명사전은 `scar.py` 다. 그 안에 넣으면 "SCAR 의 문" 이 AADC 의 다른 서비스(EDS)까지 떠안는다.
상류를 고칠 자리를 하나로 묶는 것이 문의 뜻이라, **EDS 를 여는 `aadc.py`** 를 따로 두었다(upstream `aadc`, `REGISTRY` 한 줄).
받기·굽기·내주기를 한 파일에 둔 것은 `scar.py` 의 꼴을 따랐다.

### 굽기

- 셰이프는 EPSG:3031 미터 좌표, 글자는 UTF-8(`.cpg`). `geo3al.read_dbf` 는 latin-1 로 읽어 "Sør" 가 "SÃ¸r" 가 되니 행마다 되풀었다.
  `.prj` 가 3031(남위 71° 표준 위선)이 아니거나 `.cpg` 가 UTF-8 이 아니면 굽지 않고 멈춘다 — 판이 바뀌어 꼴이 달라졌는데 엉뚱한 자리에
  그리는 것보다 낫다
- 면은 꼭짓점 13 만 3 천. **2 m** 로 줄여(Douglas–Peucker, 3031 미터에서) 2 만 8 천 — 가장 작은 ASPA 가 100 m² 라 5 m·10 m 로 줄이면
  작은 것들이 무너진다. 구운 파일은 726 KB, 브라우저에는 gzip 으로 간다
- 점(ASPA 마다 한 점) 레이어를 따로 둔 것은 면이 너무 작아서다 — 남극 전체를 볼 때는 면이 한 점도 안 된다
- 원본은 `rawstore` 로 `<AADC_DIR>/aspa_raw/<날짜>/` — 같은 판이면 새 폴더를 만들지 않는다. `--from <폴더>` 는 받아 둔 파일로 굽기만

### 싣는 속성 · 싣지 않은 것

ASPA 번호·이름·제안국·지정 문서·넓이·바다를 품는가·ACBR(보전 생물지리구, Terauds 2012 의 번호). **`PrimProtDe`(A–I)·`EnvDomain` 은
싣지 않았다** — 부속서 V 3 조 2 항의 (a)–(i) 같아 보이고 분포(C 54 — 조류 번식지)도 그럴듯하지만 자료·메타데이터 어디에도 부호의 뜻이 없다.
짐작으로 팝업에 "주된 보호 사유" 를 적지 않는다. 색은 바다를 품은 것(7)과 땅뿐인 것(112) 둘로만 갈랐다.

번호 179 처럼 한 ASPA 가 여러 조각(Site A–F)인 것이 있어 행은 119, 번호는 75 다.

### 하지 않은 것

- **ASMA** — Quantarctica 의 셰이프는 같은 폴더의 "ERA APAD License Terms and Conditions.pdf" 를 읽어야 한다. 읽지 않았으니 하지 않는다
- ATS 보호구역 DB 의 관리 계획 링크 — ASPA 번호로 쪽 주소를 지을 길이 없다(DB 의 번호가 ASPA 번호가 아니다)
- 정적 판 — 구운 점 레이어(`bake_static`)에 싣는 것은 판 세션이 정한다

### 운영에서 할 일 (1 단계)

1. 컨테이너 안에서 `docker compose exec web python manage.py fetch_aspa` — `<DB 옆>/aadc/aspa_2024.json` 과 `aadc/aspa_raw/<날짜>/` 가 생긴다
   (1 초 간격으로 열두 번, 2.4 MB)
2. `seed_catalog` 가 컨테이너가 뜰 때 `data/aadc_layers.json` 을 넣는다 — 남극 탭 "보호구역 (AADC)" 레이어군
3. `manage.py data_status` 에 "남극 특별보호구역 ASPA" 가 있음으로 뜨는지 본다

## 2 단계 — 스발바르 자연보호구역 (NPI)

### 상류와 조건

- `geodata.npolar.no/arcgis/rest/services/Temadata/N_Nature_Reserves_Svalbard/MapServer` — 레이어 넷: 조류 보호구역(점 16)·람사르(면 9)·
  보호 경계(선 70)·보호구역(면 56). 서비스의 `copyrightText` 는 "Norsk Polarinstitutt, Sysselmesteren på Svalbard" 뿐이고 조건 칸이 비었다
- 조사 문서의 표는 "NPI 는 CC BY 4.0 [확인]" 이라 적었지만 이 서비스의 것으로는 읽지 못했다. NPI 자료 목록(`api.npolar.no/dataset`)을 뒤져
  **"Protected areas"(f0e95d92-…)** 를 찾았다 — 그 레코드가 바로 이 MapServer 를 `service` 링크로 걸고 `licences` 가 CC BY 4.0 이다
  (2026-10-24). 출처 링크는 그 레코드, 표기는 서비스가 적은 대로 NPI 와 주지사를 함께(`npolar.PROTECTED_CREDIT`)
- 맡긴 말에는 "`where: features` 틀" 이라 했지만 이 서비스는 ArcGIS Online 이 아니라 NPI 의 지도 서버라 `where: "map"` 이다 — 틀은 같다

### 고른 것

- **갈래 색을 `arcpoints` 로 옮겼다.** NPI 의 점 레이어는 한 색(`style`)뿐이었고 갈래(`classes`)는 그린란드 포털(`grportal.class_of`)에만
  있었다. 보호구역은 국립공원(7)·자연보호구역(48)·지질 보호지(1)를 갈라 칠해야 읽힌다 — 문이 다른 문을 import 하지 않게 갈래 틀
  (`class_of`·`class_body`)을 `arcpoints` 로 옮기고 grportal 은 그것을 부른다. 정적 판의 JS(`static-kinds.js` 의 `classOf`)는 이미
  명세의 `classes` 를 따라 하므로 고치지 않았다
- 국립공원 안에 자연보호구역이 겹친다. 면은 옅은 속(0.08)과 테두리로만 그려 지질도를 가리지 않는다(`classStyle` 의 면 갈래)
- `verneform` 은 색으로만 쓰고 팝업에 올리지 않는다 — 값이 `naturreservatSvalbard` 같은 부호다. `iucn` 도 같은 까닭으로 뺐다
- 지정일 `vernedato` 는 `20191220` 꼴이라 `arcpoints.clean` 에 `ymd` 갈래를 더했다(서버·정적 판 둘 다)
- 보호 경계선은 속성이 자료 날짜·정확도뿐이라 팝업에 아무것도 올리지 않는다. 바다 쪽 경계는 면의 테두리보다 이 선이 또렷해 남겼다
- 람사르의 `omraadebeskrivelse`(노르웨이어 긴 글)는 싣지 않는다 — Naturbase 링크가 같은 글로 간다
- 면·선은 0.0001°(위도 11 m 남짓)로 줄여 받는다 — 보호구역 0.93 MB → 0.19 MB. 조류 보호구역 섬이 작아 더 거칠게는 줄이지 않는다
- 보호구역에 얀마옌 자연보호구역 하나가 든다. 얀마옌 탭에 빌려 주는 것(`borrow`)은 하지 않았다 — 얀마옌 탭은 지금 우리가 그린 지질도뿐이다

### 운영에서 할 일 (2 단계)

없다 — 다른 NPI 점 레이어처럼 처음 열 때 받아 서버 캐시에 담는다. `seed_catalog` 가 "스발바르 보호구역 (NPI)" 레이어군을 넣는다
