# CLAUDE.md

한국지질자원연구원 **지오빅데이터 오픈플랫폼**(data.kigam.re.kr)의 오픈API를 받아
지질주제도를 겹쳐 보고, 클릭해 속성을 읽고, 내 좌표 자료를 얹는 지도뷰어.
문서는 한국어로 쓴다 — 커밋 메시지, devlog, 주석 모두.

**DiaRUGA·ForGIA 와 자료를 나누지 않는다.** 저장소도 DB도 배포도 따로다.
다만 **말을 고르는 규칙과 devlog 규약은 그쪽에서 물려받는다** — 같은 사람이
읽을 문서이기 때문이다. 훗날 시추 지점을 지도에 올리고 싶어지면 그때
`Locality.lat/lon` 을 내보내 `PointSet` 으로 받는다. 지금은 다리를 놓지 않는다.

## 이름

**뷰어의 이름은 `GSM` 이다.** 표기는 이 하나뿐 — `Gsm`·`gsm` 으로 쓰지 않는다.
저장소·경로(`~/projects/GSM`·`~/venv/GSM`)·URL(`/GSM/`)·DB(`GSM.db`)가 전부
`GSM` 이다. **기술이 소문자를 강제하는 자리만 `gsm`** — 파이썬 패키지(`gsmweb`),
Docker Hub 이미지(`koprifossillab/gsm`), 브라우저 `localStorage` 키.
환경변수는 `GSM_*`.

약자의 풀이는 **GreatStoneMap** 이고, **한국어 자리의 이름은 `대돌여지도`** 다
(대동여지도에 돌을 끼웠다). 화면 제목·`<title>`·README 첫 줄이 그 자리다.
**길게 쓸지 짧게 쓸지는 자리가 정한다.** 자리가 넉넉하면 풀어 쓰고
(`대돌여지도` · `GREAT STONE MAP`), 좁으면 `GSM` 으로 줄인다. 따로 막는
규칙은 두지 않는다.

## 말을 고르는 규칙

**DiaRUGA 의 규칙 그대로다.** 한 낱말이 두 뜻을 겸하지 않게 한다.

| 뜻 | 쓰는 말 |
|---|---|
| 돌다 말고 멈추다 | **멈춘다** |
| 임포트·설정이 성립하다 | **돈다** |
| 경고·띠가 나타나다 | **뜬다** |
| 행·개체가 만들어지다 | **생긴다** |

이 저장소가 더하는 것 — **지도 낱말은 상류(KIGAM)의 말을 따른다.**

| 뜻 | 쓰는 말 | 쓰지 않는 말 |
|---|---|---|
| WMS 가 돌려주는 지도 한 장 | **타일** | 이미지, 그림 |
| 겹쳐 그리는 한 겹 | **레이어** | 계층, 층 |
| 레이어를 묶은 것 | **레이어군** | 그룹, 카테고리 |
| 사용자가 올린 좌표 묶음 | **점묶음**(`PointSet`) | 마커, 포인트셋 |
| 점묶음에 든 선·면 하나 | **모양**(`Shape`) | 도형, 피처 |
| 클릭해 읽은 속성 | **속성** | 정보, 피처 |
| 지도의 보이는 범위 | **범위**(bbox) | 영역, 뷰포트 |
| 받아 두는 바깥 자료의 출처 하나 | **데이터소스**(`sources.json`) | 자료원 |

**개인 레이어**는 관리 화면(`/GSM/manage/`)에서 반입해 **그 브라우저(IndexedDB)에만 두는 것**이다 — 서버의
점묶음과 다르다. 상류가 주는 레이어와 헷갈리지 않게 늘 "개인" 을 붙인다. 양식은 `docs/개인레이어_양식.md` 하나이고
점이냐 면이냐는 좌표 값의 꼴이 정한다 (wetherilli P08·118). 남의 API 에 이은 것은 **연결 레이어**다 — 주소·키는
그 브라우저에만 두고 지도를 열 때마다 새로 받는다 (P09·122).

`층`은 **자료의 층**(권역>지역>지점)에만 쓴다 — DiaRUGA 가 그렇게 쓴다.
지도에서 겹치는 것은 언제나 **레이어**다.

## 자료의 층

```
레이어군   지질도 / 지화학도 / 해저지질도 …        LayerGroup
 └ 레이어    25만 지질도 (L_250K_Geology_Map)      Layer     ← 상류가 주는 것
점묶음     내가 올린 CSV·GeoJSON 하나              PointSet  ← 내가 만드는 것
 ├ 점        위경도 하나 + 딸린 속성                Point
 └ 모양      선·면 하나 (GeoJSON 그대로)            Shape
```

점과 모양을 가른 것은 **점은 위경도 하나**라는 뜻을 지키려는 것이다. 모양은
올린 GeoJSON 의 선·면, 잡아 둔 범위, 잰 선·면에서 온다. 이름은 여전히
점묶음이다 — 올린 것 대부분이 점이다.

**둘은 섞이지 않는다.** 레이어는 상류에서 카탈로그로 받아 채우는 것이라
사람이 손으로 만들지 않고(한글 제목 손질만 한다), 점묶음은 전부 내 것이라
상류를 타지 않는다. 화면에서만 같은 레이어 패널에 나란히 선다.

## 라이선스

**코드는 AGPL-3.0 이다**(`LICENSE`, 2026-09-30 에 사람이 정해 적었다 — 파일은 첫 커밋부터 있었다).
라이선스는 코드에만 걸리고 지도 자료는 상류마다 제 조건을 따른다(아래 "지역"). 남의 코드를 옮겨 오면
그 라이선스 전문을 `docs/licenses/` 에 두고 README "라이선스와 자료의 출처" 에 한 줄 적는다 — AGPL 과
어울리지 않는 것(비상업 조건이 붙은 코드 따위)은 옮기지 않는다. 고친 판을 밖에 열 때는 쓰는 사람이
소스로 갈 길이 있어야 한다(AGPL 13조). **그 길은 공개용 저장소 `koprifossillab/GSM-open` 이다**(2026-10-02, wetherilli 149) —
판마다 그 태그의 소스를 한 커밋으로 민다(`deploy/publish_open.sh <태그>`, `.claude`·`.github` 은 뺀다). 소개 화면의 "소스" 링크(`settings.SOURCE_URL`)가
거기를 가리킨다. 개발 저장소(`koprifossillab/GSM`)는 나중에 비공개로 돌릴 수 있게 링크에서 떼어 두었다

## 인증키

**인증키는 브라우저에 절대 내보내지 않는다.** 이것이 이 저장소에 서버가
있는 이유다. 브라우저는 `/GSM/wms/` 를 부르고, Django 가 거기에 키를 붙여
상류 `/openapi/wms` 로 넘긴다.

- 키는 `GSM_KIGAM_KEY` 환경변수로만 들어온다. `.env` 는 커밋하지 않는다
- **키를 로그에 적지 않는다.** 상류 URL 을 로그로 남길 때는 `key=…` 를 지운다
  (`viewer/kigam.py` 의 `redact()` 하나가 그 일을 한다)
- 키가 없어도 뷰어는 **돈다** — 타일 자리에 "인증키가 없다" 안내 타일이 뜨고
  레이어 패널·좌표 표시·점묶음은 그대로 쓸 수 있다. 키 신청이 심사 중인
  동안 나머지를 만들려고 그렇게 했다

**연구소 밖 정적 판(https://koprifossillab.github.io/GSM-open/)은 예외가 아니다 — 거기에는 우리 키가 없다.** 보는 사람이 각자
KIGAM·VWorld 키를 넣고(처음 열 때 묻는다, wetherilli 174)(그 브라우저 localStorage, 30 일), 브라우저가 `/openapi/wms` 를 곧장 부른다(`map.js` 의 `STATIC_KIGAM`).
서버 없이 돌므로 위의 "서버가 키를 붙인다" 가 없다. 판 세션이 판마다 `deploy/publish_pages.sh` 로 굽고 민다
(wetherilli P11·162). 밀기 전에 `deploy/static_smoke.py` 가 구운 판을 띄워 소개·실린 지역마다 페이지 오류·레이어 목록·판 이력을 보고, 깨지면 밀지 않는다(wetherilli 315). 실을 지역·상류는 `deploy/static_site.py` 의 `REGIONS`·`UPSTREAMS`. 조건은 열렸지만 실을지 사람이 정할 것은
`OPTIONAL` 에 두고 고를 때만 싣는다(`--with colombia` — 콜롬비아 1:50만, wetherilli 201; `--with usa` — 미국 USGS, 공공 도메인, wetherilli 205; `--with australia` — 호주 GA, CC BY 4.0, wetherilli 212; `--with sweden` — 스웨덴 SGU, CC0, wetherilli 213; `--with netherlands`·`belgium`·`austria`·`poland` — `arcwms.Door` 상류를 표 하나·손 하나(`static-kinds.js` 의 `arcKind`)로, wetherilli 257).

## 상류의 함정 — 문서를 믿지 않는다

오픈API 안내 문서(`/guide/openapi`)와 레이어 목록 페이지에 **틀린 것이 있다.**
2026-09-23 에 `GetCapabilities` 와 대조해 확인했다 (devlog 001).

- 레이어 목록 페이지가 지화학도 12 종을 전부 `L_geochemMP_V`(바나듐)로 적었다.
  실제로는 `L_geochemMP_ZN`(아연)·`_CU`(구리)·`_FE2O3`(철)·`_PB`(납)·`_CAO`(칼슘)
  처럼 다 다르다
- 변성암 동위원소는 `L_1M_isotope_plutonic` 이 아니라 `L_1M_isotope_metamorphic`,
  광상은 `L_1M_isotope_ore` 다
- 문서에 아예 없는 레이어가 15 개 있다 — 좋은물지도 14 종과 수원정보

**그래서 레이어 카탈로그를 표로 둔다.** 사람이 문서를 보고 옮겨 적지 않는다.
`GetCapabilities` 가 준 것을 씨앗으로 넣고(`data/kigam_layers.json`),
한글 제목과 레이어군만 사람이 손질한다.

## 두 개의 상류 주소 — 갈라 쓴다

| 주소 | 쓰는 자리 | 키 |
|---|---|---|
| `/openapi/wms` | **제품이 도는 길** (`GetMap`·`GetLegendGraphic`) | 필요 |
| `/mgeo/geoserver/wms` | **속성**(`GetFeatureInfo`), 씨앗 뽑기, 개발 스위치를 켰을 때 | 없어도 된다 |

아래쪽은 **문서에 없는 주소다.** 오픈API 예제 소스에 주석으로 남아 있던 것을
보고 알았다. 키를 묻지 않고 `GetMap`·`GetFeatureInfo`·`GetLegendGraphic`
·`GetCapabilities` 를 다 준다.

**뚫은 것은 아니다.** 플랫폼이 자기 지도 페이지에 쓰는 타일 소스와 같은
계열이다 — `/gives/mapService/serviceInfo.do` 가 `{"store":"GeoEnv",
"url":"../geoserver"}` 를 내려주고 그 페이지의 OpenLayers 가 키 없이 타일을
받아간다. 즉 **인증키는 자료를 감추려는 것이 아니라 프로그램 접근을 식별하고
계량하는 공식 창구다.** 이용제한("지나치게 잦은 호출") 조항이 거기 걸려 있다.

그래서 이렇게 갈랐다.

- **제자리는 `/openapi/wms` + 인증키다.** 식별되는 쪽으로 나가는 것이 옳고,
  문서에 없는 주소는 예고 없이 닫혀도 할 말이 없다. 요청의 대부분인 타일이
  이 길로 간다
- **속성만은 GeoServer 로 간다.** 2026-09-27 에 키를 받아 대조하니
  `/openapi/wms` 가 `GetFeatureInfo` 를 막아 두었다(500, devlog 006). 문서의
  "`REQUEST=GetMap` 고정" 이 그 뜻이었다. 속성을 못 읽는 뷰어는 반쪽이라
  이것만 갈랐다. 이 길에는 **키를 붙이지 않는다** — 묻지 않는 곳에 흘릴 까닭이
  없다. 갈림은 `kigam.DIRECT_REQUESTS` 한 줄이고, `/openapi/wms` 가 열어주면
  거기서 지운다
- **"5만 지질도 (층리 등 제외)" 의 그림도 GeoServer 로 간다** (2026-09-30, jikhanjung 003).
  `L_50K_Geology_Map` 은 묶음이라 자세 기호만 뺄 수 없어, 낱레이어(`Geology_map:l_50k_geology_*`)
  여섯을 엮어 부른다. `/openapi/wms` 는 낱레이어에 빈 그림을 준다. 예외는 그 레이어 하나뿐이고
  (`kigam.COMPOSED`), 속성·범례는 바탕 묶음으로 바꿔 지금 길로 묻는다. 기본 5만 지질도는 그대로
  `/openapi/wms` 다. KIGAM 이 같은 판을 열어 주면 `COMPOSED` 에서 지운다
- `GSM_DEV_DIRECT_WMS=1` 은 **인증키가 없을 때의 임시 조치다.** 켜면 모든
  상류 요청이 GeoServer 로 곧장 가고 화면 맨 위에 띠가 뜬다
  (`map.html` 의 `.warn.direct`). 기본값은 꺼짐이다. 2026-09-23~27 에는
  배포본에서 켜 두었고, 키가 들어와 껐다
- 씨앗 뽑기(`seed_catalog --from-upstream`)는 사람이 직접 부를 때만 간다.
  평소의 씨앗은 저장소에 든 `data/kigam_layers.json` 이다

받아둔 타일은 길이 바뀌어도 **버리지 않아도 된다** — 캐시 열쇠에 상류 주소가
안 들어가고, 두 길이 같은 GeoServer 를 보므로 같은 그림이다 (`tilecache.py`).

GeoServer 로 갈 때는 레이어명에 워크스페이스 접두사(`geoOpen:`)가 붙는다 —
GeoServer 는 그것을 요구하고 `/openapi/wms` 는 접두사 없는 이름을 받는다.
그 갈림은 `kigam._endpoint()` 와 `kigam._qualify()` 둘이 맡는다.

문서화된 `/openapi/wms` 는 `GetCapabilities` 를 막아놨다(400). 그래서 카탈로그를
제품 스스로 새로 고칠 길이 지금은 없다. 대신 `manage.py verify_layers` 가
레이어를 한 장씩 받아보고 `Layer.verified_at` 에 남긴다 — 2026-09-27 에 61 개
전부 그려졌다. 2026-10-05 부터는 **모든 상류**를 본다 — 레이어 범위 한가운데 칸 하나를 화면이 받는 꼴로 문에서 곧장 받아
그림·빈 그림·오류·건너뜀을 상류마다 표로 낸다. 1 초 간격, 차단 조짐이면 멈춘다. 사람이 부르는 명령이고 cron 에 두지 않는다 (wetherilli 298).

**상류 방화벽은 curl 의 User-Agent 를 막는다**(400 `Request Blocked`). 손으로
찔러볼 때는 `curl -A 'GSM/0.1'` 을 붙인다. 코드는 늘 `GSM/0.1` 을 보낸다.

## 받아온 것의 순위 — 새 것이 이긴다

타일은 세 곳에서 올 수 있다. 부딪히면 **위가 이긴다.**

1. **방금 상류에서 받은 것** (`/openapi/wms` + 인증키)
2. **우리 캐시에 있던 것** (`viewer/tilecache.py`)
3. 옆 저장소에서 옮겨온 것 — **지금은 없다.** 앞으로도 1·2 를 덮지 않는다

까닭 둘.

- **새 것이 더 나중이다.** 상류가 판을 올리면 우리 것은 따라가지만, 옮겨온
  것은 옮겨온 그날에 멈춰 있다
- **받아온 길이 다르다.** 우리는 제품이 도는 길을 `/openapi/wms` + 인증키
  하나로 묶어 두었다. 다른 길로 받은 것을 섞으면 "이 타일이 어느 길로 왔나" 를
  나중에 답할 수 없다

2026-09-23 에 phyloserver 의 지질도 캐시(789 MB)를 가져올지 견주고
**안 가져오기로 했다** — 지질 폴리곤은 같은데 주향·경사·단층·지명이 빠진
2015 년 판이었다. 자세한 것은 devlog 002. (002 가 "5만 원도 스캔" 이라 적은
`uploads/geolmap` 은 원도가 아니라 한반도 지질도 한 장이었다 — 026)

**받아온 것은 계속 보탠다** (2026-09-27, devlog 007). 타일·범례·속성을
모두 캐시에 담고 스스로 지우지 않는다 — 다음에 같은 자리를 볼 때 상류를
타지 않게 하려는 것이다. 그래도 위의 순위는 지킨다. 3 년이 지난 것은
**상류에 다시 묻고 새 것으로 덮으며**, 상류가 못 줄 때만 옛것을 낸다.
디스크 여유가 5 GB 밑이면 더 담지 않는다.

**미리 데우기(`manage.py prewarm`)는 천천히 간다** — 1 초에 한 번, 차단
조짐이면 멈춘다. **호출 제한을 재려고 두드리지 않는다.** 재다 걸리면 서버
IP 가 막혀 모든 것이 멈춘다 (devlog 010). 얼마나 묻는지는
`manage.py upstream_stats` 로 지켜본다. 받는 타일은 브라우저가 부르는 것과
**한 글자까지 같아야** 캐시가 맞는다 — 상류마다 꼴이 달라(3857 WMS·극지 투영
WMS·z/x/y·우리가 굽는 것) 계획을 따로 둔다 (029).

**브라우저 캐시** (wetherilli 151) — 응답마다 ETag 가 붙어 하루(`TILE_CACHE_SECONDS`)가 지나면 304 로 되묻는다
(`ConditionalGetMiddleware`). 주소에 판(`?v=`)이 든 우리 타일만 1 년 `immutable` 이다(`views._immutable`) — 판이 바뀌면 주소가
바뀌기 때문이다. 상류에서 받은 것에는 판이 없으니 길게 두지 않는다. 그리는 법을 고쳐 `RENDERER` 를 올리면 주소의 판도 따라 오른다.
화면(JS)이 주소를 짓는 타일(달·화성·수성 원도, 온 지구의 판 회전·화석·화산·지진·지각·지명 따위, IBCSO 배경)은 판을 페이지의
`tile-versions` 로 받는다(`views.tile_versions`, wetherilli 183). 판은 서버 캐시 열쇠에 든 것과 같은 것(그리는 법과 파일의 판)이다 —
새 우리 타일을 더하면 거기 한 줄 더한다.
속성·범례 JSON 도 하루이고 언어(쿠키)로 가른다(`views.browser_cached`, wetherilli 158). 3D 의 `warp/` 는 원본의 판을 열쇠에 넣어
디스크에 담는다 — 스캔판(phyloserver)만 빼고. 다시 펴는 법을 고치면 `views.WARP_RENDERER` 를 올린다.

캐시는 여전히 **덤이지 자료가 아니다.** 통째로 지워도 뷰어는 그대로 돌고,
줄이고 싶으면 사람이 `manage.py prune_tiles` 를 부른다. 자료의 주인은
한국지질자원연구원이다 — 우리는 받은 것을 다시 내주지 않는다.

## 지역 — 한국·일본·중국·대만·몽골·인도·사우디아라비아·인도네시아·말레이시아·필리핀·태국·그린란드·스발바르·얀마옌·북극해·노르웨이·스웨덴·핀란드·아이슬란드·영국·프랑스·독일·스페인·아일랜드·포르투갈·이탈리아·스위스·오스트리아·폴란드·네덜란드·벨기에·콜롬비아·브라질·페루·에콰도르·아르헨티나·우루과이·파라과이·미국·멕시코·니카라과·파나마·도미니카공화국·카리브·아프리카·캐나다·호주·뉴질랜드·누벨칼레도니·프랑스령 폴리네시아·남극, 그리고 동아시아·북극·유럽·남미·북미·중미·카리브·오세아니아·동남아

화면 위 지역 탭으로 가른다 (devlog 016). **한국이 기본**이고 다른 지역은
"+ 추가 지역" 에서 더한다. 탭 줄에는 한국·북극·남극만 늘 서고 나머지는 "그 외" 하나로 접힌다 — 접힌 지역을 보면
단추가 그 이름이 된다(`map.js` 의 `PINNED`, wetherilli 214). 지역마다 레이어 목록·켠 레이어·보던 자리·배경·색이
따로다 — 한국은 먹갈색·금, 일본은 벚꽃, 중국은 청화백자, 대만은 보라얼룩나비, 몽골은 고비 바얀작 절벽의 주황, 인도는 사프란, 사우디아라비아는 홍해 산호의 청록, 인도네시아는 라플레시아의 적갈, 말레이시아는 보르네오 우림의 초록, 필리핀은 필리핀 해의 남청, 태국은 비단의 자홍, 그린란드는 빙하빛, 스발바르는 노르웨이
국기의 남색·빨강, 얀마옌은 현무암 숯빛·용암 주황, 북극해는 극야의 얼음 라일락, 노르웨이·스웨덴·핀란드는 타이가의 순록이끼, 아이슬란드는 용암밭의 루피너스 꽃, 영국은 히스꽃 자주, 프랑스는 포도잎 초록, 독일은 점판암 청회, 스페인은 리오하 장밋빛, 아일랜드는 코네마라 대리석, 이탈리아는 카라라 대리석의 테라코타, 포르투갈은 아줄레주의 코발트 청, 스위스는 빙하 호수의 옥빛, 오스트리아는 할슈타트 석회의 분홍, 폴란드는 발트해 호박, 네덜란드는 튤립 밭의 주홍, 벨기에는 아르덴의 붉은 대리석, 콜롬비아는 커피 열매의 진홍, 브라질은 이페 꽃의 노랑, 페루는 티티카카 호수의 쪽빛, 에콰도르는 푸른발부비새의 하늘청록, 미국은 모뉴먼트밸리의 붉은 사암, 멕시코는 로사 메히카노, 니카라과는 마사야 용암 호수의 주황, 파나마는 황금개구리의 노랑, 도미니카공화국은 라리마르의 하늘청, 카리브는 블루마운틴의 남청, 아르헨티나는 페리토 모레노 빙하의 청록, 우루과이는 마노 지오드의 보라, 파라과이는 테라 로하의 적갈, 아프리카는 사바나 황토, 캐나다는 단풍잎의 붉은빛, 호주는 그레이트배리어리프의 산호빛, 뉴질랜드는 포후투카와 꽃의 진홍, 누벨칼레도니는 석호의 비취빛, 프랑스령 폴리네시아는 흑진주의 청보라, 남극은 오로라 청록, 북극은 흰 얼음빛(색을 빼고 밝기로), 동아시아는 청자, 남미는 안데스의 구리빛, 북미는 대평원의 밀빛, 오세아니아는 남태평양 석호의 청록, 동남아는 몬순 숲 이끼의 연두, 중미·카리브는 카리브 바다의 청록,
유럽은 백악의 회백.

- **달은 지역이 아니다** — 대돌여지도 아이콘의 숨은 차림에서 들어가는 따로 화면(`/GSM/moon/`)이다.
  CesiumJS 의 둥근 달(극까지 온전하다)에 USGS 달 통합 지질도와 LOLA 지형을 얹고, 테마는 늘 흑백이다
  (036, P05). 지질도·표고·속성·범례는 `trek.py` 를 거치고, 영상 배경(LRO WAC·Kaguya TC·LOLA 음영)만 브라우저가
  Trek 을 곧장 부른다. 루나 오비터·클레멘타인 배경은 브라우저가 USGS Astrogeology WMS 를 칸의 경위도 범위로 곧장 부른다(공공 도메인,
  CORS `*`, wetherilli 229) — 극 평면에서는 USGS 극 판이 우리 극 격자와 맞지 않아 WAC 를 쓴다. 좌표는 달 경위도다 — 지구의 `toLL`·좌표계를 타지 않는다. 평면은 위도 65° 너머면
  달 극 평사도법(`IAU_2015:30130`·`30135`)이고 Trek 의 극지 판을 받는다 (052). 달 지명은
  `data/moon_places.json`(`manage.py fetch_moon_places`). 원도 6 장(1971–1979)은 우리가 굽는다 — 아래 "파일을 받아"
- **화성도 지역이 아니다** — 달 화면을 옮긴 따로 화면(`/GSM/mars/`, `mars.js`·`mars.html`, 058)이다. 틀은 달과 같고
  자료만 다르다 — USGS 화성 지질도(SIM 3292)·MOLA–HRSC 지형, 영상 배경은 Viking·THEMIS·MOLA. 문은 같은 `trek.py`
  (`mars_*`, 주소 `TREK_MARS_URL`)다 — 같은 NASA Trek 의 다른 몸이라 문을 새로 내지 않았다. 테마는 녹슨 주황이다.
  평면은 달처럼 위도 65° 너머면 극 평사도법인데, Trek 의 화성 극지 판이 **극 반지름(3 376.2 km)의 구**라
  이름이 `IAU2000:49918`·`49920` 이다 (065). **달 화면을 고치면 화성에도 옮길지 본다** — 두 파일은 일부러 나란히 두었다. 화성 지명은
  `data/mars_places.json`(`manage.py fetch_moon_places --body mars`). 달·화성은 아이콘(`emblem-moon.png`·
  `emblem-mars.png`)과 대기 화면(`splash-*.gif`)이 따로다 — 원본은 `docs/brand/`
- **수성도 지역이 아니다** — 화성 화면을 옮긴 따로 화면(`/GSM/mercury/`, `mercury.js`·`mercury.html`, wetherilli P10·137)이다.
  문은 같은 `trek.py`(`mercury_*`, 주소 `TREK_MERCURY_URL`)인데 ArcGIS 의 뿌리가 `arcgis/rest/services/mercury/` 다. 영상은 MESSENGER
  MDIS(마리너 10 모자이크는 USGS Astrogeology WMS, wetherilli 229), 표고는 USGS 665 m. **지질도는 우리가 굽는다**(`mercurymap.py`, wetherilli 144) — Trek 의 5M 도폭은 Capabilities 만 있고
  타일이 404 라, USGS 1:500만 도폭 아홉의 합본(Frigeri 외 2008, 마리너 10 시절 좌표)을 쓴다. 마리너 10 이 찍은 반쪽 남짓만 덮고
  시대 열이 없어 범례는 갈래(평원·분지·크레이터)로 묶는다. 극지 판 타일이 없어 극 평면(`IAU_2015:19930`·`19935`)은 경위도 타일을 옮겨 그린다.
  테마는 MESSENGER 강조색의 청회색·황갈. **화성 화면을 고치면 수성에도 옮길지 본다.** 지명은 `data/mercury_places.json`
  (`fetch_moon_places --body mercury`)
- **온 지구도 지역이 아니다** — 화성 화면을 옮긴 따로 화면(`/GSM/earth/`, `earth.js`·`earth.html`, wetherilli P06·086)이다.
  지역 탭이 "그 나라의 지도를 그 나라의 투영으로" 보는 자리라면, 여기는 둥근 지구 하나에 온 지구의 자료를 얹는다.
  지질도는 Macrostrat(`macrostrat.py`, CC BY 4.0)이고, 배경(NASA GIBS Blue Marble)·표고(AWS Terrarium)는 브라우저가
  곧장 부른다. 평면은 경위도(4326) 그대로이고 위도 65° 너머는 지역 탭과 같은 3413·3031 이다. **carto 는 한 대역
  아래만 채워**(세계 지질도뿐인 한반도는 줌 6 부터 빈다) 서버가 더 거친 대역의 타일을 늘려 밑에 깐다
  (`macrostrat.fill`) — 가장 가까운 칸으로 늘리면 계단이 져서 **색마다 매끄럽게** 늘린다(`macrostrat.enlarge`, wetherilli 105).
  까는 법을 고치면 `views.MACROSTRAT_FILL_VERSION` 을 올린다. 점묶음은 지역 탭의 것(`earth`)을 같이 읽는다.
  누른 자리는 **그때의 자리**(`paleo.py`, wetherilli 087)도 보인다 — PALEOMAP 2016 판 회전(`data/paleomap2016.json`, CC BY 4.0,
  `manage.py build_paleomap <zip>`)으로 단위의 윗·밑 연대나 사람이 넣은 연대로 옮긴다. EarthThruTime3D 와 같은 모델·같은 줄임이다 —
  건너갔을 때 같은 자리에 핀이 서게. 셈은 ETT 의 코드(MIT, `docs/licenses/`)를 옮겼다. **계산이지 관측이 아니다**.
  옮겨진 연대에는 ETT 를 여는 링크가 붙는다(`earth.js` 의 `ettHref`, wetherilli 088) — 오늘의 좌표와 연대만 넘긴다.
  **시간 축**(wetherilli P07·091) — 연대 하나를 로그 막대로 고른다(`?age=`). 1 Ma 부터는 오늘의 영상·지형·지질도를 끄고
  서버가 판을 돌려 칠한 경위도 타일(`paleo.render_tile`, 그리는 법을 고치면 `paleo.RENDERER` 를 올린다)을 바다색 구에 그린다.
  판을 돌리는 셈은 서버의 `paleo.py` 하나다 — 브라우저에 두지 않는다. 레이어의 `then: true` 는 1 Ma 부터만 뜬다 — 옛 해안선
  (`paleocoast.py`, PaleoCoastlines v7.1, `<EARTH_DIR>/paleocoastlines_v7.json` — `manage.py build_paleocoastlines <zip>`, wetherilli 097).
  `always` 는 늘 뜬다 — **화석 산지**(PBDB 27 만 곳, 문 `pbdb.py`, `manage.py fetch_pbdb` 가 받아 `fossils.py` 가 `<EARTH_DIR>/pbdb.sqlite`
  로 굽는다, wetherilli 098). 화면이 부를 때 PBDB 를 타지 않는다. 옛 연대에는 그 연대를 품은 산지를 우리 판 회전으로 옮겨 찍는다.
  **홀로세 화산**(스미스소니언 GVP 1 214 곳, 문 `gvp.py`, `manage.py fetch_gvp` 가 `<EARTH_DIR>/gvp_volcanoes.json` 에 적고 `volcanoes.py`
  가 그린다, wetherilli 134)은 오늘의 레이어다 — 1 Ma 부터 꺼진다. 비상업·인용 조건이고 사진은 담지 않는다.
  **플라이스토세 화산**(1 452 곳)은 같은 명령이 `gvp_pleistocene.json` 에 따로 받아 따로 레이어로 그린다 — 마지막 분화 열이 없어 한 색이다(wetherilli 194).
  **지진**(USGS M5 이상 1900 년부터 10 만 7 천 곳, 문 `usgs.py`, `manage.py fetch_quakes` 가 5 년씩 1 초 간격으로 받아 `quakes.py` 가
  `<EARTH_DIR>/quakes.sqlite` 로 굽는다, wetherilli 138)도 오늘의 레이어다. 규모 칸 셋(M6 이상·M5.5–6·M5–5.5)이 따로 레이어다.
  **제4기 고생태 산지**(Neotoma, CC BY 4.0, 문 `neotoma.py`, `manage.py fetch_neotoma` 가 자료 번호를 500 개씩 묶어 한 시간쯤 받아
  `paleoeco.py` 가 `<EARTH_DIR>/neotoma.sqlite` 로 굽는다, wetherilli 139)는 자료형 칸 다섯이 따로 레이어다. 1 Ma 안쪽의 연대에는
  그 연대를 품은 자료가 있는 산지만 뜨고 1 Ma 부터 꺼진다.
  오늘의 레이어로 **지각 두께**(CRUST 2.0, `crust.py`, 1° 격자 `data/crust2_thickness.json` — `manage.py build_crust <zip>` 은
  h5py 가 있는 파이썬으로만 돈다. 제품은 h5py 를 쓰지 않는다, wetherilli 101)와 **해양 지각 연대·해저 퇴적층 두께**(Seton 2020 CC BY 4.0·GlobSed v3 이용 제약 없음, `seafloor.py`, `<EARTH_DIR>/seafloor_*` —
  `manage.py build_seafloor --age <grd> --sediment <xyz>`, numpy 없이, wetherilli 264), **세계 암상**(GLiM 0.5°, CC BY 3.0, `glim.py`, `data/glim_05deg.json` — `manage.py build_glim <zip>`)·**지열류**
  (IHFC 2024, CC BY 4.0, `heatflow.py`, `<EARTH_DIR>/heatflow.sqlite` — `manage.py build_heatflow <zip>`, 점 레이어, wetherilli 267)·**판 경계·세계 지질구**(Hasterok 2022, CC BY 4.0, `tectonics.py`, `data/earth_tectonics.json` —
  `manage.py build_tectonics <폴더>`, 레이어 `tbound`·`tprov` — 판 회전의 `plates` 와 섞지 않는다, wetherilli 272)·**지각 응력**(World Stress Map 2025, CC BY 4.0, `stress.py`, `<EARTH_DIR>/stress.sqlite` — `manage.py build_stress <csv>`,
  품질 E 는 뺀다, wetherilli 273)·**세계 광상**(USGS MRDS·세계 광상 평가, 공공 도메인, `minerals.py`, `<EARTH_DIR>/minerals.sqlite` —
  `manage.py build_minerals <폴더>`, 광종 칸 여섯, 골재·석재는 뺀다, wetherilli 276)·**세계 활성단층**(GEM Global Active Faults, **CC BY-SA 4.0** — 구운 것도 같은 조건, `faults.py`,
  `<EARTH_DIR>/earth_faults.json` — `manage.py build_faults <geojson>`, wetherilli 279)·**충돌구·거대 화성암 지대**(Wikidata CC0·Johansson 2018 CC BY 4.0,
  `impacts.py`, `data/earth_impacts.json` — `manage.py build_impacts`. LIP 레이어는 `always` — 대륙 위의 것은 PALEOMAP 판으로 옮긴다, wetherilli 283)·**세계 빙하**(RGI 7.0 속성 표, CC BY 4.0, `glaciers.py`, `<EARTH_DIR>/glaciers.sqlite` —
  `manage.py build_glaciers <csv>`, 줌 3 부터 — 그 밑은 Natural Earth, 윤곽은 Earthdata 로그인 뒤라 아직, wetherilli 289)와 **지명 찾기·산맥·바다 이름·강·호수·빙하**
  (Natural Earth 10 m, `naturalearth.py`, `data/earth_places.json`·`earth_water.json`·`earth_ice.json` — `manage.py build_natural_earth`,
  wetherilli 102). 이름표는 타일이 아니라 화면이 쓴다(`labels: true` 레이어). `ka: true` 는 0 보다 오래고 1 Ma 안쪽일 때만 —
  **최근 빙기의 빙상 가장자리**(NADI-1·DATED-1, `icemargins.py`, `data/ice_margins.json` — `manage.py build_ice_margins`, wetherilli 104).
  `mantle: true` 는 구에서만 — **맨틀 슬랩·하부 더미**(Müller 2022 OPT1, `mantle.py`, `<EARTH_DIR>/mantle/` — `manage.py build_mantle <zip>`,
  wetherilli 106). 켜면 땅이 비친다. 옛 연대는 맨틀 기준틀이라 판 조각과 어긋난다고 캡션에 적는다
- **점묶음은 몸을 갖는다**(`PointSet.body` — `earth`·`moon`·`mars`·`mercury`, 037·058·P10). 지구 화면은 `earth` 만, 달 화면은
  `moon` 만, 화성 화면은 `mars` 만, 수성 화면은 `mercury` 만 읽는다. 몸을 적지 않은 요청은 지구다. 달 점묶음의 표고는 LOLA(`trek.lola_values`),
  화성은 MOLA–HRSC(`trek.mars_values`, 화성 기준면), 수성은 MESSENGER(`trek.mercury_values`, 2 439.4 km 구)
- **지역마다 화면 투영이 다르다** — 한국·일본·중국·대만·몽골·인도·사우디아라비아·인도네시아·말레이시아·필리핀·태국·동남아·동아시아·영국·프랑스·독일·스페인·아일랜드·포르투갈·이탈리아·스위스·오스트리아·폴란드·네덜란드·벨기에·유럽·콜롬비아·브라질·페루·에콰도르·아르헨티나·우루과이·파라과이·남미·멕시코·니카라과·파나마·도미니카공화국·카리브·중미·카리브·아프리카·호주·뉴질랜드·누벨칼레도니·프랑스령 폴리네시아·오세아니아 3857, 그린란드·스발바르·얀마옌·북극해·노르웨이·스웨덴·핀란드·아이슬란드·북극
  3413, 남극 3031 이고 남극점이 가운데다 (017). **캐나다·미국·북미는 캐나다 람베르트(3978)** 다(미국은 wetherilli 210 부터) — 3857 은 북극 섬을 크게 부풀리고 3413 은 서경 45° 가
  위라 나라가 50° 기운다. 범위는 3857 과 같은 너비라 줌 번호가 같은 해상도다(`map.js`·`tilegrid.EXTENT`, wetherilli 204). 좌표를 옮길 때는 `toLL`/`fromLL`
  (화면 투영)을 쓰고 `ol.proj.toLonLat` 을 투영 없이 부르지 않는다. 지금의 투영은 축척 막대 옆에
  EPSG 번호로 늘 떠 있다 (jikhanjung 001)
- **북극은 지역이 아니라 묶음이다** — `REGIONS.arctic.includes` 가 그린란드·스발바르·
  얀마옌·북극해·노르웨이·스웨덴·핀란드·아이슬란드의 레이어군을 한 화면에 모은다. DB 의 `REGIONS` 에는 없다 (021).
  **동아시아도 묶음이다** — `REGIONS.eastasia.includes` 가 한국·일본·중국·대만·몽골을 모은다. 묶음
  탭(3857)에서는 레이어가 제 범위(`bbox` + 0.5°) 밖 타일을 묻지 않는다 (024).
  **유럽도 묶음이다** — `REGIONS.europe.includes` 가 영국·아일랜드·프랑스·독일·스페인·포르투갈·이탈리아·스위스·오스트리아·폴란드·네덜란드·벨기에를 모은다 (wetherilli 143·147·211·237).
  **남미도 묶음이다** — `REGIONS.south_america.includes` 가 콜롬비아·에콰도르·페루·브라질·파라과이·우루과이·아르헨티나를 모은다 (wetherilli 188·191·195·196·198·256).
  **동남아도 묶음이다** — `REGIONS.southeast_asia.includes` 가 태국·말레이시아·인도네시아·필리핀을 모은다. 베트남·라오스·캄보디아·미얀마는
  공개 서비스가 없어 동아시아의 CCOP 200만이 덮는다 (wetherilli 228).
  **중미·카리브도 묶음이다** — `REGIONS.central_america.includes` 가 니카라과·파나마(STRI 1:25만, wetherilli 253)·도미니카공화국·카리브(USGS 1:250만, wetherilli 248)를 3857 한 화면에 모으고, 미국 탭의 푸에르토리코(`mrdata:pr:`)를 빌린다.
  북미 묶음(3978)에 넣지 않았다 — 북위 10–20° 는 캐나다 람베르트의 가장자리다 (wetherilli 242).
  **오세아니아도 묶음이다** — `REGIONS.oceania.includes` 가 호주·뉴질랜드·누벨칼레도니·프랑스령 폴리네시아를 모은다(뒤의 둘은 wetherilli 260). 3857 의 가장 넓은 줌(5)에 두 나라가 다 들지 않아 처음엔 호주 동부와 뉴질랜드를 연다 (wetherilli 218).
  **북미도 묶음이다** — `REGIONS.north_america.includes` 가 캐나다·미국·멕시코를 캐나다 람베르트(3978) 한 화면에 모은다. 미국 탭도 3978 이다 —
  알래스카가 부풀지 않게 (wetherilli 210).
  지역 하나가 다른 지역의 상류 하나만 **빌릴** 수도 있다(`REGIONS.<지역>.borrow`) — 스발바르가 북극해의 EMODnet 을(135),
  프랑스·독일·스페인·아일랜드가 영국에 둔 EGDI 1:100만을(143·147). 레이어명이 지역 하나에만 걸리기 때문이다.
  상류 이름 대신 `:` 로 끝나는 레이어 이름 앞머리도 된다 — 브라질·페루·에콰도르·아르헨티나·우루과이가 콜롬비아 지역의 SGC 가운데 남미 1:500만(`sgc:sa:`)만 빌린다(191·195·196·198)
- 레이어군은 지역을 갖고(`LayerGroup.region`), 레이어는 상류를 갖는다
  (`Layer.upstream` — kigam·kigam50k·geus·geusarc·vworld·grportal·npolar·gsj·gsitile·ccop·gsjows·gsmma·emodnet·ngu·gtk·sgu·natt·bgs·bgsgi·brgm·egdi·bgr·igme·gsi·gsni·sgc·sgb·ingemmet·segemar·dinamige·iige·mrdata·sgm·cgmw·aga·ispra·lneg·swisstopo·cgs·gsn·bumigeb·irgm·ga·gsq·gsv·gssa·ntgs·gns·mris·gsiindia·sgs·esdm·jmg·mgb·dmr·nrcan·ogs·sigeom·ygs·skgs·nsgs·ags·bcgs·calgs·nbmg·wadnr·dogami·dggs·geosphere·pig·tno·dov·spw·ineter·stri·usgscarib·vmme·georep·bas·phyloserver·geomap·janmayen·geo3al·kopri·earth). 서버는 레이어의
  상류를 보고 문을 고른다
- 레이어는 그리는 법도 갖는다 — 타일(WMS)이 거의 전부이고, `kind: vector` 는 단층
  선을 1° 칸으로 받아 우리가 그리고(020), `kind: points` 는 점·모양을 한 덩이로
  받아 우리가 그린다(019·022·025). 면이 만 개를 넘는 중국은 `render: image`
  (`ol.layer.VectorImage`)로 한 장씩 굽는다. 점의 `style: value` 는 **연속값 색**이다 — 서버가 고를 열(`values`)을 싣고
  화면이 고른 열의 분위수 일곱 칸을 viridis 로 칠한다(`map.js` 의 `valueStyle`, 그린란드 지화학, wetherilli 159). 점이 많아
  열을 다 실을 수 없는 레이어(`slice`, 그린란드 전암 화학 3 만 점)는 서버가 **고른 열의 점만 잘라** 준다(`?value=`, wetherilli 163)
- **WMS 는 대개 3857 로 받고 OpenLayers 가 옮겨 그린다** — 캐시 열쇠가 앞 판과
  같다. **NPI 만은 지역의 투영으로 곧장 받는다** — 3857 로 물으면 축척이 부풀어
  1:25만 대신 1:75만을 준다 (021). **일본(GSJ)은 WMS 가 아니라 z/x/y 타일**이다 —
  GSJ 의 WMS 는 옛 판(V1)이라 타일 API(V2)를 `gsj/<레이어>/{z}/{x}/{y}.png` 로 중계하고,
  속성은 `point=위도,경도`(`gsj/info/`), 범례는 보는 범위의 것만 JSON 으로(`gsj/legend/`) 받는다 (024).
  **대만(GSMMA)은 4326 으로 받는다** — 상류 MapGuide 가 4326 말고는 `InvalidCRS` 다. 줌 0 이 180° 네모 두 장인 4326 격자
  (`map.js` 의 `TAIWAN_GRID`)로 받아 옮겨 그린다. WMS 가 속성·범례를 주지 않아, 누른 자리의 지층은 같은 기관의 지질운
  GeoJSON API 에 작은 네모로 묻는다(점 레이어 — 온천·시추공 — 는 화면의 8 픽셀). 지질시대는 번체 중국어에서
  옮긴다(`i18n.age_zh`, wetherilli 136). **3D 는 3857 로 묻는다** — 문이 4326 으로 받아 줄(위도)만 다시 골라 편다
  (`gsmma.mercator_map`, wetherilli 141). 3857 의 가로는 경도에 비례해서 줄만 고르면 된다
  범례는 상류가 주지 않아(559·401) 보는 범위의 지층 면(지질운)과 지층 그림(WMS)을 맞대어 견본 조각을 뜬다
  (`gsmma.extent_legend`, `gsmma/legend/`, wetherilli 142) — 일본처럼 화면이 HTML 로 그린다
- 카탈로그 씨앗은 상류마다 `data/*_layers.json` 이다. KIGAM 씨앗처럼 사람이
  제목·레이어군만 손질하고, `seed_catalog` 가 컨테이너가 뜰 때 다 넣는다
- **공유 링크는 해시(`#r=…&c=…&z=…&l=…&b=…`)다** (wetherilli 189, `share.js`) — 지역 지도·온 지구·달·화성·수성이 "링크" 단추로 짓고,
  들어올 때 읽어 지운다. 링크로 연 동안에는 기억을 메모리 덧층에만 쓴다 — 그 사람의 localStorage 를 덮지 않는다. 그래서 **화면의 기억은
  `map.js` 의 `stored`·`store`, 구 화면의 `saved`·`save` 를 거친다** — localStorage 를 곧장 부르지 않는다. 점묶음·개인 레이어는 싣지 않는다
- VWorld 배경·주소 찾기·한국 좌표계·KIGAM 인증키 띠는 한국과, 한국을 품은 동아시아에서만 보인다. 하나만 예외다 —
  남극의 "세종·장보고 기지 위성"(VWorld 테마 영상 2013, 두 기지 둘레만) 배경 (wetherilli 093)
- 극지 배경(EOX·PGC·Esri 남극 위성)과 일본 배경·주제도 겹침(국토지리원 지리원 타일 — 활단층도·화산토지조건도는
  카탈로그 레이어 `gsitile` 이 지리원 주소를 그대로 화면에 준다, wetherilli 172), 대만 배경(국토측회중심 WMTS, wetherilli 141)은 VWorld 처럼
  브라우저가 곧장 부른다. **조건이 열린 배경 — NASA GIBS(Blue Marble)와 모든 지역의 해저 지형 배경 GEBCO(공공 도메인 — 극 평사도법 탭은
  4326 을 옮겨 그린다, wetherilli 135), 그리고 NPI 의 스발바르 지형도·위성 타일(CC BY 4.0, wetherilli 200) — 은 서버가 받아 캐시에 담는다**(`basemaps.py`, wetherilli 184). 브라우저가 부르던 주소 그대로 받고,
  정적 판만 곧장 부른다. 조건을 읽지 않은 배경은 이 길로 옮기지 않는다. 일본의 찾기 칸(국토지리원 주소·지명 검색, 지리원 지도가 쓰는 것)과 팝업의 주소(역지오코더 — 시군구 코드를
  `japan-muni.json` 으로 옮긴다, `manage.py build_japan_muni`, wetherilli 230)도 브라우저가 곧장 부른다 —
  열쇠가 없고 CORS 가 열려 있다. 지리원 지도를 위한 것이라 예고 없이 바뀔 수 있다 (wetherilli 155).
  EOX Sentinel-2 는 **비상업(CC BY-NC-SA)** 조건이고 Esri 남극 위성은 **Esri 이용 조건**이다 — 밖에 열 때 다시 본다 (040)
- **남미 1:500만은 CGMW 의 지도다** — SGC 가 WMS 를 열어 두었지만 CGMW 는 지도를 판다. 정적 판에 싣지 않았고, 밖에 열기 전에
  사람이 조건을 읽는다(TODOs). 콜롬비아 1:50만은 SGC 열린자료(CC BY 4.0)다 (wetherilli 188). **브라질 SGB 는 비상업(CC BY-NC 4.0)**
  이다 — GeoSGB 사이트가 그렇게 적는다. EOX 처럼 밖에 열 때 다시 본다 (wetherilli 191). **페루 INGEMMET 도 비상업(CC BY-NC-SA 4.0)** 이다 — 정적 판에 싣지 않았다 (wetherilli 195) **아르헨티나 SEGEMAR** 는 "SEGEMAR 의 재산,
  CC 아르헨티나 라이선스로 쓸 때 저작자를 밝힌다", **우루과이 DINAMIGE** 는 적힌 조건이 없다 — 둘 다 CORS 가 없어 서버 문으로만 가고 정적 판에 싣지 않는다 (wetherilli 196) **에콰도르 IIGE 도 팔지 못하게 한다**(비상업) (wetherilli 198) **캐나다 NRCan·온타리오 OGS 는
  열린 정부 라이선스**(OGL–Canada·OGL–Ontario, 브리티시컬럼비아는 OGL–BC — CORS 가 없다, wetherilli 231)이고 CORS 를 되비춘다 — 정적 판에 실을 수 있지만 기본값에는 넣지 않았다(#153, wetherilli 204) **주 판 둘째**(wetherilli 235) — 앨버타는 OGL–Alberta,
  사스카치원은 Standard Unrestricted Use Data Licence 2.0, 노바스코샤는 "출처를 밝히면 원본째·가공물로 쓰고 나눈다" 는 사용 허락이다. 정적 판에는 아직 싣지 않았다
- **아프리카 1:1000만도 CGMW 의 지도다**(CGMW–BRGM 2016) — 서버의 조건 칸은 비었지만 CGMW 가 인쇄판을 판다. 정적 판에 싣지 않고
  밖에 열기 전에 사람이 읽는다(TODOs). **BGS 아프리카 지하수 지도책은 CC BY-SA 4.0** 이다 (wetherilli 207).
  **남아공 CGS(정부 DPME 사본)·나미비아 GSN 은 자료를 판다** — 보기는 열려 있지만 받은 것을 **서버 캐시에 담지 않는다**(`views.NO_STORE`) —
  그때그때 받아 보여 주기만 한다. 정적 판에 싣지 않는다 (wetherilli 209). **부르키나파소 BUMIGEB·카메룬 IRGM 1:100만은 비상업**
  ("personal, teaching, research or non-commercial use") — 파는 자료가 아니라 캐시에 담고, 정적 판에 싣지 않는다 (wetherilli 246)
- **호주의 주 판(퀸즐랜드 GSQ·빅토리아 GSV·남호주 GSSA)은 CC BY 4.0** 이다 — 남호주는 Capabilities 가, 퀸즐랜드·빅토리아는 주 열린자료 목록이
  그렇게 적는다. 정적 판에는 아직 싣지 않았다(`static-kinds.js` 가 없다). 서호주 SLIP 은 "개인 이용 허락" 이라 싣지 않았다(TODOs, wetherilli 225)
- **중국 geo3al 은 연구실 내부용이다** — USGS 메타데이터의 이용 조건이 "내부 용도만,
  가공물 포함 제3자 재배포 금지" 다(UNESCO·CGMW·ESRI 지적재산). 화면에 보이는 것 자체가
  재배포라 **밖에 열 때는 이 레이어를 먼저 내린다.** 파일은 `.gitignore`·`.dockerignore` 가 막는다 (025).
  내리는 스위치는 `GSM_PUBLIC=1`(또는 `<DB 옆>/public`)이다 — geo3al·phyloserver·peninsula 를
  목록에서 빼고 그 길도 닫는다(`views.LAB_ONLY`). 연구실 내부용 상류가 새로 오면 거기 더한다 (029).
  극지연구소(`kopri`)도 KPDC 공개 정책을 사람이 읽기 전까지 거기 있다 (053)
- GEUS 는 부르는 이를 `whoami` 로 밝혀 달라고 한다. 이메일이라 **저장소에
  적지 않는다** — `GSM_GEUS_WHOAMI` 나 `<DB 옆>/geus_whoami`
- NPI 의 `Basisdata_Intern/*` 은 "Svalbardkartet 안에서만" 이라 부르지 않는다 (P01)
- **파일을 받아 우리가 그리는 것 열** — 달 지질도 원도 6 장(`GSM_MOON_DIR`, 기본 `<DB 옆>/moon`, 039 —
  `manage.py build_moon_originals <zip>` 이 sqlite 한 장으로 굽는다. 같은 자리에 남극–에이트켄 분지 지질도 원본
  `spa_geomap_iqbal2026.tif` — 그리지는 않고 누른 자리만 읽는다, wetherilli 081), 남극 GeoMAP(`GSM_GEOMAP_DIR`, 기본 `<DB 옆>/geomap`,
  018), 얀마옌 지질도(`GSM_NPOLAR_DIR`, 기본 `<DB 옆>/npolar`, 022), 중국 USGS geo3al
  (`GSM_USGS_DIR`, 기본 `<DB 옆>/usgs`, 025), 한반도 지질도 음영판·민판(`GSM_PENINSULA_DIR`,
  기본 `<DB 옆>/peninsula`, 027·028 — PDF·PNG 를 `manage.py build_peninsula` 로 잘라 둔다), 남극 해저·빙저 지형
  IBCSO v2(`GSM_IBCSO_DIR`, 기본 `<DB 옆>/ibcso`, 047 — 칠한 GeoTIFF 둘을 `manage.py build_ibcso` 로 3031 에 잘라 둔다), 남극 자력 이상 ADMAP-2(`GSM_ADMAP_DIR`, 기본 `<DB 옆>/admap2`, wetherilli 262 — `manage.py build_admap <grid.zip>`), 화성 크레이터
  목록 Robbins 2012(`GSM_MARS_DIR`, 기본 `<DB 옆>/mars`, 067 — `manage.py build_mars_craters <zip>` 이 sqlite 한 장으로 굽고 타일은 그때그때 그린다), 화성 옛 지질도·지역도 — I-1802·SIM 2888·I-2650·MTM(같은 자리, 068·wetherilli 079 —
  `manage.py build_mars_originals <zip…>`, 달 원도의 틀을 빌렸다), 수성 지질도 — USGS 1:500만 도폭 합본(`GSM_MERCURY_DIR`, 기본
  `<DB 옆>/mercury`, wetherilli 144 — `manage.py build_mercury_geology <zip>`), 온 지구의 옛 해안선(`GSM_EARTH_DIR`, 기본 `<DB 옆>/earth`,
  wetherilli 097), 카리브 대앤틸리스 지질도 USGS SIM 3534(`GSM_CARIBBEAN_DIR`, 기본 `<DB 옆>/caribbean`, wetherilli 254 —
  `manage.py build_caribbean <zip>`, 옛 판 OFR 2019-1036 의 셰이프 zip — 웹서비스가 없다). 운영은
  `/srv/GSM/db/` 아래다 — 배포한 자리의 compose 를 못 고쳐도 `db/` 는 붙어 있다. **저장소에 두지 않는다.** 원본은 NAS 의 `N:\GSM\sources\` 에 있다.
  파일이 없어도 뷰어는 돌고 그 자리에 안내가 뜬다. **새로 굽는 파일을 더하면 `datastatus.ITEMS` 에 한 줄 더한다** —
  `manage.py data_status` 가 운영에 무엇이 있고 언제 구웠는지 한 표로 내고, healthz 가 없는 것의 수를 낸다(wetherilli 312). GeoMAP 의 그리는 법을 고치면
  `geomap.RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다
- **극지연구소(053–057)는 모아 두고 그린다** — 암석 시료 목록과 KPDC 자료·운석의 상세(3 500 쪽)를
  `manage.py fetch_kopri` 가 2 초 간격으로 받아 `GSM_KOPRI_DIR`(기본 `<DB 옆>/kopri`)에 적는다. 처음 세 시간 남짓,
  다음부터는 새 것만. 화면이 부를 때 상류를 타지 않는다. 기지(WFS)와 해안선 변화 따위(3031 WMS)는 다른 상류처럼
  그때그때 받아 캐시에 보탠다. 저장소에 두지 않는다
- **phyloserver(026)는 같은 서버의 연구실 자료다** — 캐시는 하루만 믿는다(`FRESH_SECONDS`).
  한반도 지질도는 카카오 격자(EPSG:5181)를 다시 굽지 않고 화면이 옮겨 그린다. 캐시에 담지 않는다
- **한반도 지질도 음영판(027)·민판(028)은 원본의 좌표를 고쳐 쓴다** — 음영판 PDF 는 해안선보다
  355 m 북쪽·가로 0.134%, 민판 월드파일은 가로 0.267%·세로 0.137% 늘어나 있어 판마다
  `Sheet.extent` 로 고쳤다. 원본이 적은 좌표는 믿지 않고 OSM 해안선에 댄다. 스캔판처럼 출처를 몰라 밖에 열지 않는다

## 영어판

**화면의 글을 새로 적거나 고치면 영어도 같은 커밋에서 적는다.** 판을 붙일
때 영어판이 한국어판을 따라가지 못한 채 나가지 않게 하려는 것이다.

- 원문은 한국어다. JS 는 `T("…")`, 템플릿은 `{% t "…" %}`, 파이썬 메시지는
  `msg("…")` 로 감싸고, 영어는 `viewer/i18n.py` 의 표에 적는다 — 화면 문장은
  `EN`, 팝업 속성 이름은 `PROP_EN`, 레이어는 `LAYER_EN`·`GROUP_EN`
- 숫자·이름이 끼면 `{n}`·`{name}` 자리표로 적는다. 조각을 `+` 로 잇지 않는다
- **시험이 지킨다.** `test_i18n` 이 코드를 긁어 표에 없는 문장이 있으면 깨진다.
  카탈로그처럼 자료에서 오는 것은 `manage.py i18n_missing` 으로 본다 — 레이어가
  새로 들어오면 돌려 보고 `LAYER_EN` 을 채운다
- 영어판의 화면 제목은 `Great Stone Map`, 그 밑 작은 줄에 `대돌여지도` 다 —
  한국어판의 짝을 뒤집었다
- 지질시대는 **ICS 국제층서표**(https://stratigraphy.org/chart)의 명칭을 따른다.
  영어 → 한국어는 ICS 가 싣는 **한글판**(대한지질학회 옮김, v2024/12)의 표기다 — 절(Age)
  이름도 이것으로 옮긴다(`i18n.AGE_STAGES`, 029)
- **옮기지 않는 것** — 속성 값(지층명·암석명·도폭명·사람 이름), 판 이력
  (`CHANGELOG.md`), 타일 안에 그려진 글자(상류·VWorld 가 그린다). 지질시대
  값만은 낱말을 조합한 것이라 옮긴다

영어 낱말도 한 뜻에 하나만 쓴다.

| 한국어 | 영어 |
|---|---|
| 타일 | tile |
| 레이어 | layer |
| 레이어군 | layer group |
| 점묶음 | point set |
| 속성 | attributes |
| 범위 | extent |
| 배경(지도) | basemap |
| 데이터소스 | source |

## 구조

```
web/gsmweb/       Django 설정
web/viewer/       뷰어 앱 하나뿐이다. 앱을 더 가르지 않는다
  kigam.py        KIGAM 으로 나가는 문 (지질도 타일·속성·범례, 자료 API `/openapi/data` — 모아 둔다 `fetch_kigam_data`, 5만 구조 요소 WFS — 사람이 가끔 부른다 `fetch_kigam50k`, cron 에 두지 않는다)
  vworld.py       VWorld 로 나가는 문 (주소·장소 검색, 좌표→주소, 주소→좌표, 지질 참고 WMS·WFS)
  geus.py         GEUS 로 나가는 문 (그린란드 지질도. 같은 기관의 ArcGIS 의 자력 편찬·DTU 부게 중력·지질구도 — 상류 `geusarc`, wetherilli 259)
  grportal.py     그린란드 정부 포털(ArcGIS)로 나가는 문 (시료·연대 점을 통째로)
  npolar.py       노르웨이 극지연구소(NPI)로 나가는 문 (스발바르·드로닝모드랜드)
  gsj.py          일본 지질조사종합센터(GSJ)로 나가는 문 (심리스 지질도 V2 타일·속성·범례, 새 호스트의 CCOP 200만 지질도 WMS, 지질도Navi 판 목록,
                  1:200만 일본 지질도·부게 중력·지구화학도 WMS — 상류 `gsjows`, 정부표준이용규약 2.0, wetherilli 255.
                  1:200만·중력은 누른다 — 번호를 범례 SLD 로 풀고 시대는 일본어에서 옮긴다 `i18n.age_ja`, wetherilli 316)
  gsmma.py        대만 경제부 지질조사·광업관리중심(GSMMA)으로 나가는 문 (지질도 WMS 는 4326 만, 누른 자리의 지층은 지질운 GeoJSON)
                  지질운 열린자료 가운데 WMS 가 없는 것(탄층·토석류·낙석·암체 등급·GPS)을 통째로 한 번 — 끊기면 네모를 넷으로 나눈다(`fetch_taiwan_open`, wetherilli 305)
  emodnet.py      EMODnet Geology 로 나가는 문 (유럽 바다의 해저 퇴적물·해저 지질 WMS). 북극해에 두고 스발바르 탭이 빌린다. 3413 으로 곧장
  ngu.py          노르웨이 지질조사소(NGU)로 나가는 문 (본토 기반암 1:135만·25만·5만 MapServer WMS). 3413 을 안 그려 북극 람베르트(3575)로.
                  같은 mapserver 의 금속·산업·핵심 광물(3857)·지구물리 편찬(3575)도 — `OTHER`, wetherilli 326
  gtk.py          핀란드 지질조사소(GTK)로 나가는 문 (기반암 1:100만·20만 ArcGIS WMS). 3413 으로 곧장
                  항공 자력·방사능(GTK_Geofysiikka_WMS)과 북유럽 광상 FODD(kokoavaWMS)도 — 레이어가 주소를 고른다 (wetherilli 270)
  sgu.py          스웨덴 지질조사소(SGU)로 나가는 문 (기반암 1:100만·5만–25만 GeoServer WMS, CC0). 3413 으로 곧장. 레이어 하나가 두 판을 함께 부른다
                  뿌리 주소(`/geoserver/ows`)에 워크스페이스를 붙여 묻는다 — 광물·암석 산지(`berg:`)·자력 이상(`fysik:`)도 (wetherilli 270)
  natt.py         아이슬란드 자연사연구소(NÍ)로 나가는 문 (1:60만 기반암·1:10만 GeoServer WMS). 3413 으로 곧장, 1:60만의 부호는 범례 이름으로 푼다
  bgs.py          영국 지질조사소(BGS)로 나가는 문 (그레이트브리튼 1:5만 ArcGIS WMS, 줌 13 부터). 같은 서버의 북아일랜드 GSNI 1:25만도,
                  아프리카 지하수 지도책의 나라별 1:500만 암상(`aga`, 38 나라를 레이어 하나로, wetherilli 207)도, BGS 의 다른 MapServer
                  (`ogc.bgs.ac.uk`)가 대신 내주는 나미비아 GSN 1:100만(`gsn`, wetherilli 209)·부르키나파소 BUMIGEB 1:100만(`bumigeb`, 246)도,
                  영국 GeoIndex 의 자력·중력 이상·광산·광물 산지(`bgsgi`, OGL, wetherilli 258)도
                  GeoIndex 의 수리지질·G-BASE 하천 퇴적물 시료 지점, CMIC 하천 퇴적물 지화학 31 원소(REST export·identify, 목록 범례)도 (wetherilli 324)
  cgs.py          남아공 지질조사소(CGS) 1:100만으로 나가는 문 — 정부(DPME) GIS 사본. WMS 가 꺼져 WMS 변수를 ArcGIS REST export·identify 로 옮긴다
                  같은 서비스의 광업·석탄·우라늄 지역(레이어 0·1·2, 면 8·86·19)도 — NO_STORE 를 따른다 (wetherilli 285)
  brgm.py         프랑스 지질광물조사소(BRGM)로 나가는 문 (1:100만·25만·5만 스캔, 1:100만 단순 암상도 MapServer WMS). mapsref 서버의
                  CGMW–BRGM 아프리카 1:1000만(`cgmw`, 속성은 GML, 범례는 정적 PNG, wetherilli 207)·카메룬 IRGM 1:100만(`irgm`, 4326 만, 246)도
                  해외 영토의 스캔도(앤틸리스·폴리네시아·레위니옹·마요트·생피에르 미클롱 — 지역은 씨앗마다, wetherilli 260)
                  같은 geologie WMS 의 광상·광화 지점(BD Gîtes `GITES_PT`)·광산(`MINES_PT`)도 (wetherilli 296)
  egdi.py         EGDI(EuroGeoSurveys)로 나가는 문 (범유럽 1:100만 지표 지질 GeoServer WMS). 느리다. 속성은 두 판 모두 암상 판에 묻는다(wetherilli 177)
  bgr.py          독일 연방 지구과학·자원청(BGR)으로 나가는 문 (GK1000·GÜK250 ArcGIS WMS). 이름은 `bgr:<판>:<번호>`. 유럽 1:500만 IGME5000 도
                  (축척마다 갈린 상류 레이어는 `+` 로 잇는다, 독일 탭에 두고 유럽 나라 탭이 빌린다, wetherilli 217)
                  원료 — 지표 부근 원료 1:25만 KOR250·지하자원 1:100만 BSK1000(`wms/rohstoffe` 폴더, 속성은 text/plain, wetherilli 296)
  igme.py         스페인 지질광물연구소(IGME)로 나가는 문 (1:100만은 4326, MAGNA 1:5만은 3857 ArcGIS WMS). 이름은 `igme:<판>:<번호>` 같은 서버 PSysmin 폴더의 도미니카공화국 SGN 1:25만(판 `sgnrd`, wetherilli 242)도
                  광물 산지·산업 광물 채굴지 BDMIN(`BasesDatos` 폴더, 판 `bdmin`·`bdminexp`, 상류 레이어 여럿은 `+`, wetherilli 296)
  gsi.py          아일랜드 지질조사소(GSI)로 나가는 문 (섬 전체 1:100만·공화국 1:10만 ArcGIS WMS)
  sgc.py          콜롬비아 지질조사소(SGC)로 나가는 문 (남미 1:500만 CGMW 2019·콜롬비아 1:50만 2023 ArcGIS WMS, 3857 로. 금속광상도·지구물리 이상 2022 도 — wetherilli 265). 이름은 `sgc:<판>:<번호>`
  ingemmet.py     페루 지질광업야금연구소(INGEMMET)로 나가는 문 (GEOCATMIN 1:5만·1:10만 통합판 — 그림은 REST 타일 캐시 z/x/y 중계, 누른 자리는 REST query, 범례는 보는 범위의 통계 질의. 단층·습곡은 SERV_GEOLOGIA_FALLAS 의 export 를 타일 칸으로, 1:5만 지질 단위만은 암상 레이어 export — 줌 9 부터, wetherilli 234)
                  광물 산지·광상·사업·금속 광화대·부게 이상·항공 자력도 — 다른 서비스의 export(자력은 ImageServer exportImage)를 타일 칸으로, 누른 자리는 REST query (wetherilli 277)
                  지화학 지도첩(원소 열하나의 분산도·이상점 — 그림은 둘을, 누르기는 이상점의 `layer`)·산업 광물·리튬도 (wetherilli 303)
  ispra.py        이탈리아 지질조사소(ISPRA)로 나가는 문 (1:100만·1:10만 ArcGIS WMS 를 3857 로, 속성은 GeoJSON. 1:100만은 WMS·REST 번호가 거꾸로)
  lneg.py         포르투갈 국립 에너지·지질연구소(LNEG)로 나가는 문 (1:50만 ArcGIS WMS 를 3857 로, 속성은 ESRI XML)
                  광상 1:20만·자력·중력·방사능(같은 서버의 다른 서비스 — 이름 `lneg:<판>:<번호>` 의 판이 서비스를 고른다, wetherilli 296)
  swisstopo.py    스위스 연방 지형청(swisstopo)으로 나가는 문 (1:50만·GeoCover geo.admin.ch WMS 를 3857 로, 속성은 geo.admin.ch REST identify)
  ga.py           Geoscience Australia 로 나가는 문 (호주 지표 지질 1:250만·1:100만 ArcGIS WMS — 두 판을 함께 물어 상류가 축척에 맞는 판을 그린다, 범례는 보는 범위.
                  지질구·핵심 광물·지구물리 격자도(`OTHER`, 격자는 png8 로, wetherilli 241), 확인 자원 광종 29·수리지질도(wetherilli 325))
  austates.py     호주 주 지질조사소로 나가는 문 셋 — 퀸즐랜드 GSQ(ArcGIS REST export·identify, 1:200만·1:10만)·빅토리아 GSV·남호주 GSSA(GeoServer 의 GeoSciML 포트레이얼). 범례는 보는 범위의 것 — 빅토리아는 빈 규칙 빼기, 퀸즐랜드는 REST 통계, 남호주는 WFS+SLD(wetherilli 232)
                  광산·광물 산지(퀸즐랜드 MINOCC·빅토리아 광상·남호주 SARIG)와 퀸즐랜드 지구물리 영상도 (wetherilli 269)
  gns.py          GNS Science(뉴질랜드)로 나가는 문 (QMAP 1:25만 합본·1:100만 GeoServer WMS, 3857 로. 같은 서버의 남극 남빅토리아랜드 1:25만은 3031 로. 속성은 열을 골라 묻는다)
                  중력 이상은 GNS 전체 서비스(`/gns/wms`, `GNS_ALL_WMS_URL`)에서 (wetherilli 269)
  mris.py         몽골 국가지질조사소 MonGeoCat 으로 나가는 문 (국가지질도첩 지질도·1:50만 단층 ArcGIS WMS, 3857 로. 문서에 없는 주소, WMS·REST 번호가 거꾸로, 시대는 러시아식 층서 지수에서 푼다)
                  희토류(Atlas 12_REE — WMS 가 없어 REST export·identify, wetherilli 280)
  gsiindia.py     인도 지질조사소(GSI) 1:200만으로 나가는 문 (그림은 BGS 의 OneGeology WMS, 누른 자리는 GSI 의 ArcGIS Online 피처 서비스 — Bhukosh 가 나라 밖에서 닿지 않아 둘을 엮는다)
  sgs.py          사우디 지질조사소(SGS) 국가 지질 자료로 나가는 문 (1:25만 합본 ArcGIS WMS, 원본 3857. 범례는 1 337 칸이라 보는 범위의 것 — REST 통계 질의)
                  광물 산지 MODS 5 751·광화대(다른 서비스의 WMS, wetherilli 280)
  esdm.py         인도네시아 지질청(ESDM)으로 나가는 문 (1:10만 편집 2018 ArcGIS WMS, 3857 로. 줌 10 너머는 상류가 그리지 않아 화면이 늘린다. 속성은 ESRI XML, 범례는 보는 범위의 REST 통계 — wetherilli 243)
                  금속·비금속 광물 잠재력(BGD_TU 폴더, WMS 가 없어 REST export·identify — `arcwms.rest_*`, wetherilli 280)
  jmg.py          말레이시아 광물지구과학국(JMG MyGEMS)으로 나가는 문 (주별 암상·연대 ArcGIS REST — WMS 가 꺼져 있어 export·identify 로 옮긴다, 주 열다섯을 한 장에)
  mgb.py          필리핀 광산지질국(MGB)으로 나가는 문 (지역 지질도 ArcGIS WMS, 공개 폴더만. 속성은 ESRI XML)
                  금속·비금속 광물 자원(같은 공개 폴더의 다른 서비스, 문을 하나씩, wetherilli 280)
  dmr.py          태국 광물자원국(DMR)으로 나가는 문 (암석 단위 1:25만 ArcGIS WMS. 속성이 기호뿐이라 REST 범례에서 이름을 찾아 붙이고, 시대는 기호에서 푼다)
                  광물 산지·핵심 광물(MINERAL 폴더 WMS, 산지의 열은 태국어 별칭, wetherilli 280)
  sgm.py          멕시코 지질조사소(SGM)로 나가는 문 (1:25만·1:5만 ArcGIS REST — WMS 가 400 이라 WMS 변수를 export·identify 로 옮긴다, 범례는 보는 범위)
                  같은 서버의 지질 연대 측정·고생물 산지·광상 1:25만도(`sgm:<서비스>:<번호>`, `SERVICES`, wetherilli 219), 지화학·원소 이상·광산 1:5만도
                  (원소 이상의 범례는 REST 범례의 기호 그림 — 함량 구간, wetherilli 233)
  mrdata.py       USGS mrdata 로 나가는 문 (미국 본토 SGMC·알래스카 SIM 3340·하와이·푸에르토리코(wetherilli 238)·광물 자원 MRDS·광산 기호 USMIN·
                  지질 연대·자력·중력(wetherilli 247) MapServer WMS. 본토의 속성은 WFS 1.0, 알래스카는 WMS text/plain.
                  알래스카의 물 면은 받은 그림에서 지운다 — 고침의 판이 캐시 열쇠에 든다 `views.map_cache_key`, wetherilli 224.
                  본토 SGMC 의 범례는 보는 범위의 일반화 암상 — 색은 단위가 아니라 `generalize` 로만 칠해 떠 둔 표 `SGMC_COLORS`, wetherilli 334)
  iige.py         에콰도르 지질·에너지 연구소(IIGE)로 나가는 문 (일반 지질도 ArcGIS WMS 를 3857 로, 범례는 보는 범위의 REST 통계 질의)
  nrcan.py        캐나다 천연자원부(NRCan·GSC)로 나가는 문 (캐나다 지질도 1:500만 Wheeler ArcGIS WMS 를 3978 로, 속성은 GeoJSON.
                  같은 서버의 편찬 지질도 CGMC·핵심 광물 시설·광상 유망도도 — `SERVICES`, wetherilli 250.
                  CGMC 래스터는 REST identify 의 OBJECTID − 1 을 범례 34 칸으로 풀어 누른다, wetherilli 320)
  ogs.py          온타리오 지질조사소(OGS)로 나가는 문 (기반암 1:25만·제4기 ArcGIS WMS 를 3978 로, 속성은 REST identify — WMS 번호와 REST 번호가 다르다)
                  광물 산지 목록 MDI(OMEIS, WMS 11·REST 46, wetherilli 288)
  sigeom.py       퀘벡 SIGÉOM 으로 나가는 문 (일반·지역 지질 GeoServer WMS 1.1.1 만, 3978 로. Origin 이 붙으면 403 이라 문으로만, 속성은 text/plain —
                  시대는 프랑스어라 `i18n.age_fr` 로 옮긴다, wetherilli 224)
                  가동 광산·진행 사업(`SGM:Mines_projets`, wetherilli 288)
  ygs.py          유콘 지질조사소(YGS)로 나가는 문 (기반암 1:25만 ArcGIS WMS 를 3978 로, 넓게 보면 느려 줌 7 부터, 속성은 geo+json — 시대는 ICS 영어)
                  MINFILE 광물 산지(같은 서비스, WMS 57, wetherilli 288)
  skgs.py         사스카치원 지질조사소로 나가는 문 (기반암 1:100만·1:25만 ArcGIS WMS 를 3978 로 — WMS 번호가 REST 와 거꾸로다, wetherilli 235)
                  광물 산지 SMDI·광산(`Economy/Mineral_Exploration` — WMS 가 없어 REST export·identify, wetherilli 288)
  nsgs.py         노바스코샤 자연자원부로 나가는 문 (기반암 1:50만 Keppie 2000 — WMS 가 없어 REST export·identify 로 옮긴다, 화면의 투영 그대로, wetherilli 235)
  ags.py          앨버타 지질조사소로 나가는 문 (기반암 1:100만 Map 600 의 누른 자리만 — 피처 서비스 query. 타일은 ArcGIS Online 의 3857 z/x/y 를 화면이 곧장, wetherilli 235)
  bas.py          영국 남극조사소(BAS)로 나가는 문 (Bedmap3 빙저 지형·얼음 두께·윗면의 범례만 — 타일은 ArcGIS Online 의 Esri 극 격자(3031)를 화면이 곧장, wetherilli 261)
  bcgs.py         브리티시컬럼비아 지질조사소(BCGS)로 나가는 문 (BC Digital Geology GeoServer WMS 를 3978 로. 상류 색 스타일이 1:50만 너머를 칠하지 않아 넓게 볼 때는
                  그 스타일을 47 KB 로 줄여 POST 의 SLD_BODY 로 보낸다 — 줌 5 부터, wetherilli 317. 속성은 열을 골라)
                  MINFILE 광물 산지(같은 openmaps 의 다른 레이어 — 레이어마다 주소가 따로다, wetherilli 288)
  calgs.py        캘리포니아 지질조사소(CGS)로 나가는 문 (1:75만 ArcGIS REST — WMS 가 없어 export·identify 를 3978 로. 상류가 레이어 지정을 무시해 인쇄도 한 장. `cgs` 는 남아공)
  usstates.py     미국 주 지질조사소로 나가는 문 셋 — 네바다 NBMG 1:50만·워싱턴 DNR 1:50만·1:10만 GeMS·오리건 DOGAMI OGDC-6. 모두 REST export·identify 를 3978 로,
                  주 밖 칸은 묻지 않는다(`clip`). 범례는 REST 목록에 단위 표의 이름·시대를 붙인다 (wetherilli 291)
                  알래스카 DGGS 의 중요 광산·산지(DDS 18)·광업 지구도 — 상류 `dggs`, 지질도는 SIM 3340 이 덮는다 (wetherilli 322)
  geosphere.py    GeoSphere Austria(옛 GBA)로 나가는 문 (1:100만 지질·단층 ArcGIS WMS 두 서비스, 3857 로. 시대는 "암상; 시대" 의 독일어에서. 1:5만은 WMS 가 없어 REST export·identify, 줌 11 부터)
  pig.py          폴란드 지질연구소(PIG-PIB)로 나가는 문 (1:50만 2022 ArcGIS WMS — 기반·제3기·제4기 세 층을 겹친다, WMS 번호가 REST 와 거꾸로. 1:5만 SMGP 는 줌 13 부터)
  tno.py          네덜란드 TNO 지질조사부로 나가는 문 (지표 지질도 GeoServer WMS, CC0. 속성은 열을 골라 — 모양째 7 MB)
  dov.py          플랑드르 지하 자료은행(DOV)으로 나가는 문 (제3기 1:5만·제4기 1:20만 GeoServer WMS. 속성은 열을 골라, 시대 열이 없다)
  spw.py          왈로니아 공공서비스(SPW)로 나가는 문 (지질도 개정판 1:2.5만 ArcGIS WMS, 줌 9 부터. 시대는 프랑스어 계·통·절에서)
  ineter.py       니카라과 국토연구원(INETER)으로 나가는 문 (나라 지질도·단층 GeoServer WMS, 3857 로. 속성은 열을 골라, 시대는 스페인어 — 단층은 글자가 깨져 누르지 않는다)
  stri.py         스미스소니언 열대연구소(STRI)로 나가는 문 (파나마 1:25만 MICI 1990 피처 서비스 — 면·단층을 한 덩이씩 받아 캐시에 30 일, 화면이 그린다. 시대는 기호 앞머리)
  usgscarib.py    USGS World Energy Project 지질도로 나가는 문 — 카리브(French & Schenk 2004)와 남미(Schenk 외 1999, wetherilli 256). ArcGIS Online 피처 서비스라 면을 한 덩이로 받아 캐시에 30 일, 화면이 그린다
  vmme.py         파라과이 광업·에너지 차관실(VMME)로 나가는 문 (개략 지질도 피처 서비스 — 면 61 을 한 덩이로, 색은 우리가 붙인다)
  georep.py       누벨칼레도니 정부 Géorep 으로 나가는 문 (DIMENC 지질도 1:100만·1:20만·1:5만 ArcGIS WMS 를 3857 로 — 축척마다 상류가 판을 바꾼다. 속성은 REST identify, 범례는 REST 목록)
  sgb.py          브라질 지질조사소(SGB)로 나가는 문 (GeoServer 둘 — 1:250만 2025·1:100만·1:25만, 속성은 `propertyName` 으로, 범례는 보는 범위의 것). 단위 이름표는 모아 둔다(`fetch_sgb_units`). 노두·연대측정·화석 산지·광물 산출(wetherilli 265) 점도 같은 WMS 로
  segemar.py      아르헨티나 지질광업조사소(SEGEMAR)로 나가는 문 (SIGAM GeoServer — 1:250만 단위·구조선·화산, 1:25만 간행 도폭, 지역 판 1:100만·주별 1:75만·국경 1:50만·포클랜드(말비나스), 제4기 변형·화산 위험도, 금속·산업 광상 1:25만 — wetherilli 265). 이름은 `segemar:<상류 이름>`. CORS 가 없다
  dinamige.py     우루과이 광업지질국(DINAMIGE, MIEM)으로 나가는 문 (1:50만 ArcGIS WMS, 3857 로). 이름은 WMS 번호 — REST 와 거꾸로다. 범례는 REST 를 목록으로
  pbdb.py         Paleobiology Database 로 나가는 문 (화석 산지를 통째로 한 번). 모아 둔다(`fetch_pbdb`)
  gvp.py          스미스소니언 Global Volcanism Program 으로 나가는 문 (홀로세 화산 WFS 를 통째로 한 번). 모아 둔다(`fetch_gvp`)
  usgs.py         미국 지질조사국(USGS)으로 나가는 문 (지진 목록 FDSN, M5 이상을 5 년씩). 모아 둔다(`fetch_quakes`)
  neotoma.py      Neotoma 고생태 데이터베이스로 나가는 문 (자료 목록을 번호 500 개씩 묶어). 모아 둔다(`fetch_neotoma`)
  gfs.py          NOAA GFS 로 나가는 문 (지금의 바람 u·v, 10 m·250 hPa, 구름량 넷, 분석과 +12 시간까지 예보). 호스트 cron 이 받는다(`fetch_gfs_wind`)
  gmgsi.py        NOAA GMGSI(AWS 공개 버킷)로 나가는 문 (위성 구름 — 정지궤도 적외선 온 지구 합성, 한 시간마다). 호스트 cron 이 받는다(`fetch_gmgsi`)
  era5.py         ARCO-ERA5(Google Cloud 공개 버킷)로 나가는 문 (지난 바람). 37 층 덩이에서 그 층만 Range 로. 사람이 부른다(`build_era5_wind`)
  ecco.py         ECCO2(NASA NAS 데이터 포털, 로그인 없음)로 나가는 문 (해류, 3 일 평균 표층). netCDF 머리를 읽고 표층만 Range 로. 사람이 부른다(`build_ecco2`)
  kopri.py        극지연구소로 나가는 문 (암석 시료 DB·KPDC 자료 목록·KPDC 지도 서버·아라온호 위치). 목록은 모아 둔다(`fetch_kopri`), 아라온호는 매시간 쌓아(`fetch_araon`) 항적 레이어로 낸다 — 남극·북극해 탭과 온 지구. 지난 1 년은 한 번 떠 둔 것(`fetch_araon --past`, 날짜는 하루 단위)
  trek.py         NASA Trek 으로 나가는 문 (달·화성·수성의 지질도·표고·지명·착륙지). 달·화성·수성 화면(Cesium)만 쓴다
  macrostrat.py   Macrostrat 으로 나가는 문 (온 지구의 지질도 타일·누른 자리의 단위·범례). 온 지구 화면만 쓴다
  phyloserver.py  연구실 phyloserver 로 나가는 문 (암맥 기록 한 덩이, 한반도 지질도 카카오 격자 타일). 읽기만 한다
  zhurong.py      주룽 로버 경로 파일(data/mars_zhurong.json) -> 착륙지·경로. Trek 에 없는 것을 덧붙인다. 문이 아니다
  elevation.py    표고로 나가는 문 — AWS 표고 타일·국토지리원 표고 타일·PGC(ArcticDEM·REMA). 시료 고도, 3D 의 일본 지형
  arcpoints.py    ArcGIS 점을 받아 담는 틀. grportal·npolar 가 함께 쓴다. 칠하기 규칙 → 색 표(`renderer_colors`, ingemmet·iige). requests 없음
  arcwms.py       ArcGIS WMS 를 중계하는 문들의 틀 — 문이 제 `_get` 을 넘기고 이것은 변수를 고치고 응답(geojson·ESRI XML)·REST 범례를 읽는다(esdm·mgb·dmr). requests 없음. WMS 를 켜지 않은 서비스는 WMS 꼴 변수를 REST export·identify 로 옮긴다(`rest_export_params`·`rest_identify_params`). ArcGIS WMS 의 `text/plain` 속성(한 줄에 머리와 값)도 읽는다(`fields_plain`, wetherilli 296)
  geomap.py       남극 GeoMAP 파일을 sqlite3·struct·Pillow 로 그린다. 3031 타일 격자
  janmayen.py     얀마옌 지질도 파일(NPI) -> 위경도 GeoJSON
  geo3al.py       중국 USGS geo3al 셰이프파일(람베르트) -> 위경도 GeoJSON. 연구실 내부용
  moonmap.py      달 지질도 원도 6 장 셰이프파일 -> sqlite(R*Tree) -> 달 경위도 타일. 문이 아니다
  peninsula.py    한반도 지질도 음영판·민판 — 좌표가 붙은 QGIS PDF·PNG -> EPSG:5179 타일(미리 잘라 둔다)
  twopen.py       대만 지질운 열린자료 — 받아 둔 GeoJSON(<DB 옆>/taiwan_open)을 줄여 한 덩이로(`/points/`). 문이 아니다
  kigamdata.py    KIGAM 오픈플랫폼의 자료(시료·분석·조사·주제도) 목록·상세를 모아 둔 JSON. 지도에 올리는 것은 아직(#153). 문이 아니다
  kigam50k.py     KIGAM 5만 지질도의 층리·엽리·편리·절리·화석산지·시료·광산·광종·도폭 틀·단층·습곡·선구조·신장광물·습곡축·유동구조·변질대 — 받아 둔 WFS 파일(<DB 옆>/kigam50k/raw/날짜/)에서 자리와 값, 장미도. 문이 아니다
  ibcso.py        남극 해저·빙저 지형 IBCSO v2 — 칠한 GeoTIFF(9354) -> 3031 타일(미리 잘라 둔다). 문이 아니다
  admap.py        남극 자력 이상 ADMAP-2 — Geosoft 압축 격자(numpy 없이) -> 칠한 3031 타일(미리 잘라 둔다)·누른 자리의 nT. 문이 아니다
  ntgeo.py        노던테리토리 1:250만 지질도·단층 — 열린자료 셰이프 ZIP(CC BY)을 위경도 GeoJSON 한 덩이로, 색은 ICS(원생누대는 기까지). 지도 서비스가 없다. 문이 아니다
  sarad.py        남호주 방사능 농도 격자 K·Th·U(SARIG 2024, CC BY 4.0) — ER Mapper 격자를 네 칸에 하나(320 m) int16 로 골라 적고 누른 자리의 값. 타일은 SARIG 영상 WMS 의 것. 문이 아니다
  marscraters.py  화성 크레이터 38 만 개(Robbins 2012) -> sqlite(3 차원 R*Tree) -> 화성 경위도·극 타일. 문이 아니다
  marsmap.py      화성 옛 지질도·지역도(USGS I-1802·SIM 2888·I-2650·MTM) 셰이프파일 -> sqlite -> 화성 경위도·극 타일. moonmap 의 짝. 문이 아니다
  mercurymap.py   수성 지질도(USGS 1:500만 도폭 아홉의 합본) 셰이프파일 -> sqlite -> 수성 경위도 타일·누른 자리·범례. marsmap 의 짝. 문이 아니다
  caribmap.py     USGS 대앤틸리스 지질도(SIM 3534 의 옛 판 OFR 2019-1036) 셰이프파일(람베르트) -> sqlite(3857 미터) -> 3857 타일·누른 자리·범례. 문이 아니다
  spamap.py       남극–에이트켄 분지 지질도 원본(팔레트 GeoTIFF) -> 누른 자리의 단위. 타일은 Trek 의 것. 문이 아니다
  paleo.py        PALEOMAP 2016 판 회전(data/paleomap2016.json) -> 오늘의 한 자리가 옛 연대에 있던 곳. 문이 아니다
  paleocoast.py   옛 해안선 PaleoCoastlines v7.1 -> 그때의 지구에 얹는 경위도 타일. 문이 아니다
  naturalearth.py 온 지구의 지명·강·호수·빙하 Natural Earth (data/earth_*.json) -> 찾기·이름표·경위도 타일. 문이 아니다
  mantle.py       맨틀 슬랩 Müller 2022 OPT1 — ParaView VTK(numpy 없이) -> 시점마다 삼각형 덩이. 문이 아니다
  icemargins.py   최근 빙기의 빙상 가장자리 NADI-1·DATED-1 (data/ice_margins.json) -> 연대마다 경위도 타일. 문이 아니다
  ocean.py        해류 u·v 표층 -> PNG 텍스처(R=u·G=v·B=바다), 목록. 유속 파일의 밀린 경도를 바로잡는다. 굽기는 호스트에서만(numpy). 문이 아니다
  wind.py         바람 u·v 격자 -> PNG 텍스처(R=u·G=v), 구름량 -> 회색 PNG, 그리고 목록. 굽기는 호스트에서만(numpy). 문이 아니다
  crust.py        지각 두께 CRUST 2.0 (data/crust2_thickness.json) -> 경위도 타일·누른 자리의 두께. 문이 아니다
  glaciers.py     세계 빙하 RGI 7.0 속성 CSV -> sqlite(R*Tree) -> 넓이만 한 점의 경위도 타일(줌 3 부터)·누른 자리. 문이 아니다
  impacts.py      지구 충돌구(Wikidata CC0)·거대 화성암 지대(Johansson 2018) (data/earth_impacts.json) -> 경위도 타일. LIP 는 PALEOMAP 판으로 그때의 자리에. 문이 아니다
  faults.py       세계 활성단층 GEM Global Active Faults (<EARTH_DIR>/earth_faults.json, CC BY-SA 4.0) -> 경위도 선 타일·누른 자리의 단층. 문이 아니다
  minerals.py     USGS MRDS·세계 광상 표 여섯 CSV -> sqlite(R*Tree) -> 광종 칸 여섯의 경위도 점 타일·누른 자리. 문이 아니다
  stress.py       World Stress Map 2025 CSV -> sqlite(R*Tree) -> 경위도 S_Hmax 막대 타일(체제의 색, 품질의 길이)·누른 자리. 문이 아니다
  tectonics.py    판 경계·세계 지질구 Hasterok 2022 (data/earth_tectonics.json) -> 경위도 선·면 타일·누른 자리의 지질구. 판 회전(paleo)과 다른 모형. 문이 아니다
  glim.py         세계 암상 GLiM 0.5° 격자(data/glim_05deg.json) -> 경위도 타일·누른 자리의 갈래. 문이 아니다
  heatflow.py     IHFC 세계 지열류 2024 글 파일 -> sqlite(R*Tree) -> 경위도 점 타일·누른 자리. 문이 아니다
  seafloor.py     해양 지각 연대 Seton 2020(NetCDF-3)·해저 퇴적층 두께 GlobSed v3(글 격자) — numpy 없이 -> <EARTH_DIR> 의 칠한 PNG·int16 값 -> 경위도 타일·누른 자리. 문이 아니다
  sources.py      받아 두는 데이터소스의 명세(<DB 옆>/sources.json — 서버에서 손으로 고친다) — 읽기·검사·씨앗 덧붙이기·바뀐 판 떠 두기. 씨앗은 data/sources.seed.json, 새 fetch_*·build_* 를 더하면 거기 한 줄 (jikhanjung P02). 문이 아니다
  fetchlog.py     받은 차례의 기록(<DB 옆>/store.sqlite 의 fetch_log) — fetch_*·build_* 가 끝날 때 한 줄(apps.py 가 BaseCommand.execute 를 감싼다), 명령은 fetchlog.note() 로 보탠다. 호스트(GSM_RUN_PLACE=host)는 sqlite 에 쓰지 않는다 — hourly_status.json·fetch_log_host.jsonl 을 컨테이너가 옮겨 적는다(jikhanjung P02). 문이 아니다
  rawstore.py     받은 원본을 날짜 폴더(`<자리>/<YYYYMMDD>/` + manifest)에 — 바뀐 판만(sha256 이 같으면 확인한 때만), 지우기는 사람이 부르는 `prune_raw`(최근 3 벌, `--dry-run` 먼저). kigam50k 의 틀을 뽑았다(jikhanjung P02 4 단계). 문이 아니다
  datastatus.py   구운 자료의 나이 — <DB 옆> 의 파일마다 있는지·크기·고친 날·원본 판(`ITEMS` 한 표). data_status·healthz·관리 화면의 "데이터소스" 탭(산출물 칸, jikhanjung 013)이 읽는다. 문이 아니다
  earthpoints.py  지역 탭의 화석 산지·홀로세 화산·지진·고생태 산지 — 온 지구의 모아 둔 sqlite·JSON 에서 지역의 네모만 점 GeoJSON 으로. 문이 아니다
  pointvalues.py  점묶음 CSV 에 붙일 값 — 점마다 GeoMAP 단위·지각 두께·가까운 PBDB 산지, 달·화성·수성은 그 지질도 단위. 우리 파일만. 문이 아니다
  profileband.py  높이 그래프 밑의 지질 띠 — 잰 선의 점마다 GeoMAP·geo3al·달·화성·수성 파일의 단위, 온 지구는 지각 두께 칸. 상류뿐인 레이어는 띠가 없다. 문이 아니다
  static_tables.py 정적 판(GitHub Pages)이 극지 상류를 곧장 부를 때 쓸 표 — 문의 명세·이름 표를 JSON 으로 뜬다. `static-kinds.js` 가 읽는다. 문이 아니다
  basemaps.py     조건이 열린 배경으로 나가는 문 (NASA GIBS Blue Marble WMTS·WMS, GEBCO 해저 지형 WMS). 받아 캐시에 담는다
  linked.py       연결 레이어로 나가는 문 — 사람이 준 주소(남의 API)를 대신 부른다. 사설망·낮은 포트를 막고 검사한 IP 로만 붙는다
  fossils.py      PBDB 화석 산지 CSV -> sqlite(R*Tree) -> 연대마다 그 자리의 점 타일·밀도 열지도(1° 칸, wetherilli 286)·누른 자리. 문이 아니다
  volcanoes.py    GVP 홀로세 화산 JSON -> 경위도 세모 타일(마지막 분화의 색)·누른 자리. 문이 아니다
  quakes.py       USGS 지진 CSV -> sqlite(R*Tree) -> 규모 칸마다 경위도 원 타일(깊이의 색)·누른 자리. 문이 아니다
  paleoeco.py     Neotoma 자료 JSON Lines -> sqlite(R*Tree) -> 자료형 칸·연대마다 경위도 점 타일·누른 자리. 문이 아니다
  warp.py         평면 격자(5179·5181·3031) 타일 -> 3857 타일. 3D 가 한반도 지질도·GeoMAP 을 얹는 길. 문이 아니다
  catalog.py      GetCapabilities XML -> 카탈로그
  coords.py       십진도 <-> 도분초. import 가 없다
  crs.py          평면 좌표계(TM·UTM-K·옛 Bessel·람베르트·북극 람베르트 등적) <-> 위경도. pyproj 없이
  i18n.py         한국어 원문 -> 영어 번역표. 지질시대 옮기기
  tilecache.py    받아온 타일을 디스크에 둔다. 같은 것을 두 번 받지 않는다
  models.py       Layer·LayerGroup·PointSet·Point·Shape·PointSetDeletion·UpstreamDay
  views.py        화면 하나 + 프록시 둘 + 업로드
deploy/           Docker·nginx·배포 스크립트. cron 이 부르는 것은 deploy/scripts/ — 컨테이너가 뜰 때 /srv/GSM/scripts/ 에 깔고
                  호스트 cron 은 그 사본을 전용 venv 로 돌린다(run.sh). 저장소를 부르지 않는다 (koprifossillab 005)
                  사람이 부르는 점검 둘 — 정적 판 연기 시험(`static_smoke.py`, wetherilli 315)·출처 링크 점검(`check_links.py`, wetherilli 339)
data/             카탈로그 씨앗
web/.tilecache/   받아둔 타일. 커밋하지 않는다 (운영은 /data/GSM/tiles, 컨테이너 안에서는 /srv/GSM/tiles)
devlog/           왜 그렇게 했는지 — 색인은 devlog/README.md
```

**상류마다 문이 하나다 — `kigam.py`·`vworld.py`·`geus.py`·`grportal.py`·`npolar.py`·`gsj.py`·`gsmma.py`·`emodnet.py`·`ngu.py`·`gtk.py`·`sgu.py`·`natt.py`·`bgs.py`·`brgm.py`·`egdi.py`·`bgr.py`·`cgs.py`·`igme.py`·`gsi.py`·`sgc.py`·`sgb.py`·`ingemmet.py`·`iige.py`·`mrdata.py`·`sgm.py`·`ga.py`·`austates.py`·`gns.py`·`mris.py`·`gsiindia.py`·`sgs.py`·`esdm.py`·`jmg.py`·`mgb.py`·`dmr.py`·`segemar.py`·`dinamige.py`·`ispra.py`·`lneg.py`·`swisstopo.py`·`nrcan.py`·`ogs.py`·`sigeom.py`·`ygs.py`·`skgs.py`·`nsgs.py`·`ags.py`·`bas.py`·`bcgs.py`·`calgs.py`·`usstates.py`·`geosphere.py`·`pig.py`·`tno.py`·`dov.py`·`spw.py`·`ineter.py`·`stri.py`·`usgscarib.py`·`vmme.py`·`georep.py`·`phyloserver.py`·`elevation.py`·`trek.py`·`kopri.py`·`macrostrat.py`·`pbdb.py`·`gvp.py`·`usgs.py`·`neotoma.py`·`basemaps.py`·`linked.py`·`gfs.py`·`era5.py`·`gmgsi.py`·`ecco.py`.**
이 일흔여섯 말고는 어디서도 `requests` 를 쓰지 않는다. `gfs.py`·`era5.py`·`gmgsi.py`·`ecco.py` 는 **호스트에서만** 부른다 — 바람·해류를 받아
굽는 일(numpy·ecCodes·numcodecs, `requirements-wind.txt`)이 `/srv/GSM/scripts/run.sh` 의 전용 venv 에서 돌고(koprifossillab 005), 컨테이너는 구운 PNG 를 내주기만 한다(koprifossillab P02). `linked.py` 만은 주소를 우리가 정하지 않는다 — 개인 레이어를 남의 API 에
이을 때 브라우저가 곧장 못 받으면 거친다(wetherilli P09·122). 사설망은 `GSM_LINKED_ALLOW` 에 적은 호스트만, 밖에 열면 닫는다. 뷰가 직접 부르지 않는다. 상류가 바뀌거나 주소가
닫힐 때 고칠 자리를 하나로 묶어두려는 것이다. `geomap.py`·`janmayen.py`·`geo3al.py`·`peninsula.py`·`moonmap.py`·`caribmap.py`·`ibcso.py`·`admap.py`·`ntgeo.py`·`sarad.py`·`kigam50k.py`·`kigamdata.py`·`twopen.py`·`zhurong.py`·`marscraters.py`·`marsmap.py`·`mercurymap.py`·`spamap.py`·`paleo.py`·`paleocoast.py`·`fossils.py`·`volcanoes.py`·`quakes.py`·`paleoeco.py`·`crust.py`·`glaciers.py`·`impacts.py`·`faults.py`·`minerals.py`·`stress.py`·`tectonics.py`·`seafloor.py`·`glim.py`·`heatflow.py`·`naturalearth.py`·`icemargins.py`·`mantle.py`·`earthpoints.py`·`pointvalues.py`·`sources.py`·`fetchlog.py`·`rawstore.py` 는
상류가 아니라 우리 디스크의 파일을 읽으므로 문이 아니다. `warp.py` 도 문이 아니다 — 원본은 부르는 쪽이 넘긴다. 문은 서로를 타지 않는다 —
주소 검색은 KIGAM 을 거치지 않고, KIGAM 인증키도 쓰지 않는다.

VWorld 배경지도(WMTS)만은 문을 거치지 않고 브라우저가 곧장 부른다 — 타일이
너무 많고, VWorld 가 그렇게 쓰라고 열쇠에 도메인 제한을 건다 (003).
**곧장 닿지 못할 때만 문을 거친다** — 사내 VPN 이 `api.vworld.kr` 연결을 끊는다.
브라우저가 한 장을 받아 보고 끊기면 `vworld/…` 로 돌린다. 캐시에 담지 않는다 (033).
**VWorld 의 WMS·WFS 는 문을 거친다** — 속성·WFS 가 CORS 로 막히고, 도메인 없이도
돌아 열쇠가 나가면 안 된다 (020).

## 커밋과 PR

WegenersDream 의 규약을 따른다(2026-09-30 부터).

**각자 자기 Linux 계정에서, 자기 GitHub 계정으로 작업한다**(대응표는 [devlog/README.md](devlog/README.md)).
저장소에 git 이름을 따로 두지 않는다.

**코드 작업은 기능마다 `feature/<기능 이름>` 브랜치에서 한다** — 기능 이름은 영어 kebab-case
(`feature/tile-cache`). 고침은 `fix/<이름>`. **코드에 손대기 직전에** `main` 에서 만들고
(`git switch -c feature/<이름> main`), **커밋·push·확인을 전부 그 브랜치에서** 한다. **작업이 끝나면 PR 을
만든다**(`gh pr create --base main`) — CI(`시험`)를 통과해야 하고, **`main` 병합은 사람이 정한다.**
판을 올리는 것은 그 PR 안에서 한다(`CHANGELOG.md`·`web/gsmweb/version.py`·HANDOFF). 병합하고 판이 올랐으면
CHANGELOG 의 그 절로 GitHub 릴리스(`v<판>`)를 만든다 — 태그마다 CI 가 Docker Hub(`koprifossillab/gsm:<태그>`)에
이미지를 올린다. 그리고 `sh deploy/publish_open.sh v<판>` 으로 그 판의 소스를 GSM-open 에 민다(위 "라이선스"). 2026-09-30 전에는 `main` 에 곧장 커밋하고 한 세션이 판을 모아 붙였다.

**휴대폰 화면은 손으로 찍어 보지 않는다** — CI 의 "휴대폰 화면" job(`viewer/tests/test_mobile.py`)이 390×844 터치로
화면마다 가로 넘침·페이지 오류·손잡이 자리를 본다(wetherilli 132). 그 job 이 통과하면 확인한 것이다. 휴대폰에서 새로
지켜야 할 것이 생기면 거기에 검사를 더한다. 로컬에서 돌리려면 `pip install -r requirements-browser.txt` 와
`python -m playwright install chromium` — 없으면 그 시험은 건너뛴다.

**시험은 나란히 돌린다** — `manage.py test viewer --parallel 8`(CI 는 `--parallel auto`). 오래 걸리는 브라우저 시험은 반으로 나눠
두어야 갈래들이 나눠 받는다(지역 탭 `RegionTabs*`, 구 화면 `GlobeScreens`). 카탈로그 씨앗은 `setUp` 이 아니라 `setUpTestData` 에서
넣는다 — 시험마다 0.5 초씩 든다. 깨진 시험은 tblib 가 넘겨 보인다(`requirements-dev.txt`, wetherilli 294).

**문서·기록만 고치는 커밋은 `main` 에 바로 올린다**(HANDOFF·TODOs·CLAUDE.md·devlog 색인 같은 것).
브랜치는 부딪힐 수 있는 것을 격리하려고 있는 것이다. 애매하면 묻는다.

**한 단계가 끝날 때마다 커밋하고 push 한다** — 기능 여럿을 한 커밋에 몰지 않는다. 단계마다 devlog 하나.

메시지는 **한국어로 무엇을 했는지**를 쓰고 끝에 devlog 를 붙인다 — 옛 꼴은 번호만(`(047)`), 새 꼴은
글쓴이와 번호(`(jikhanjung 001)`):

```
남극 — IBCSO v2 해저·빙저 지형을 배경으로 (047)
배경 타일도 서버 캐시에 담는다 (jikhanjung 001)
```

**`git add` 는 내가 고친 파일만 지정한다** — `git add -A`·`git add .`·`git commit -a` 는 쓰지 않는다.
`git commit -F <메시지 파일> -- <파일…>`. 커밋 전에 `git status --short` 를 보고, 내가 손대지 않은 파일은
그대로 둔다. 작업 전에 `git pull --rebase` — 여러 계정이 같은 저장소에서 일한다.

## devlog

**그때의 판단과 근거를 남기는 곳이다.** 실제로 한 작업은 `devlog/YYYYMMDD_{author}_{nnn}_{title}.md`, 계획은
`YYYYMMDD_{author}_P{nn}_{title}.md` 로 **단계마다 끊어** 적는다. 머리줄 아래에 `날짜 · \`브랜치\` · 글쓴이` 를
적는다. **무엇을 했는지가 아니라 왜 그렇게 했고 무엇을 버렸는지를 적는다.** 무엇을 했는지는 `git log` 가 안다.

**파일 이름은 글쓴이마다 번호를 센다**(2026-09-30 부터). `author` 는 **작업하는 Linux 계정의 GitHub 계정 이름**
소문자, `title` 은 영어 snake_case, 번호는 **그 글쓴이의** 다음 번호다. **옛 꼴(`YYYYMMDD_NNN_slug.md`,
001~077·P01~P05)은 이름을 그대로 두고** 번호만으로 가리킨다("devlog 017"). 새 꼴은 "jikhanjung 001" 로 가리킨다.
자세한 것과 계정 대응표는 [devlog/README.md](devlog/README.md) — **새 파일은 그 색인에 한 줄 더한다.**

DiaRUGA·ForGIA·WegenersDream 의 devlog 를 가리킬 때는 `DiaRUGA 063` 처럼 저장소 이름을 붙인다 —
맨 번호와 "글쓴이 번호" 는 언제나 이 저장소의 것이다.

**계획이 아닌 검토는 `docs/`** 에 둔다 — "이렇게 하겠다" 가 정해진 것은 devlog 의 P 문서이고, "할까 말까·
언제 하나" 를 따진 것은 `docs/` 다. 검토가 계획으로 정해지면 그때 P 문서를 쓴다.

**HANDOFF.md 는 지금만 말한다** — 지난 일은 devlog 의 몫이고, HANDOFF 는 근거가 필요한 자리마다
devlog 번호를 건다. **TODOs.md 에는 끝난 일을 쌓지 않는다.**
