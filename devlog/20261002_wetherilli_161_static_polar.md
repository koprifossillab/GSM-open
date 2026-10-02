# 정적 판의 극지 — 상류를 브라우저가 곧장 부르는 `static-kinds.js`

2026-10-02 · `feature/static-polar` · wetherilli

연구소 밖 정적 판(GitHub Pages, 이슈 #129, 계획 wetherilli P11)의 한 몫이다. 뼈대(`static_site.py`·map.js 의 정적 모드 고리·
KIGAM 각자 키)는 gsm-31, 우리 파일 굽기(`bake_static`)는 gsm-91 이 맡았다. 이 PR 은 **극지 상류를 서버 없이 부르는 손**이다.
근거는 `docs/정적_밖_경로.md` §2·§4·§5 의 실측이다.

## 1. 꼴 — 표는 파이썬에서 뜨고, 손은 JS 에

서버 판에서는 문(`npolar.py`·`geus.py`·`grportal.py`·`elevation.py` 의 PGC·`emodnet.py`·`kopri.py`)이 브라우저의 WMS 꼴을 상류의
꼴로 옮겨 부르고 속성을 손질한다. 정적 판에는 서버가 없으니 그 일을 브라우저에서 한다.

- **표(주소·레이어 번호·받을 열·팝업 이름·지질시대 낱말)는 JS 에 적지 않았다.** 적으면 두 벌이 생기고 한쪽만 고치는 날이 온다.
  `viewer/static_tables.py` 의 `tables()` 가 문의 표를 그대로 떠 JSON 하나로 묶고(35 KB), 빌드가 `window.GSM_STATIC_TABLES` 로 싣는다.
  JS 시험이 "상류 주소를 코드에 박지 않았다" 를 지킨다
- **손(손질 로직)은 JS 로 한 벌 옮겼다** — `age_ko`, NPI·EMODnet·GEUS 의 `friendly`, MapServer text/plain 풀기, ArcGIS 점의
  `compact`·`collect`·`class_of`, 서버 `feature_info` 의 거름(같은 것 하나로·3 개까지). node 가 있으면 시험이 파이썬과 같은 입력으로
  대조한다(25 경우가 같았다). CI 에 node 가 없으면 그 대조만 건너뛴다
- `window.GSM_STATIC_KINDS[상류] = {source, info → Promise, legend → Promise, points → Promise}` — map.js 의 `LAYER_KINDS` 자리에
  선다. map.js 는 건드리지 않았다(고리는 뼈대가 둔다)

## 2. 상류마다 — 2026-10-02 에 브라우저(Chromium)로 받아 본 것

| 상류 | 그림 | 속성 | 범례 | 비고 |
|---|---|---|---|---|
| NPI 스발바르·DML | `TileArcGISRest`(MapServer `export`) | `identify` 를 손으로 지어 | `legend?f=json` → 줄(그림 base64) | 지질시대가 ICS 한글판으로("쥐라기 중기~백악기 전기") |
| PGC 경사·등고선 | `TileArcGISRest`(ImageServer `exportImage`, `renderingRule`) | `identify` 의 값 한 점 | 없다(서버도) | "사면 경사 34.4°" |
| EMODnet | `TileWMS` 3413 | JSON | `GetLegendGraphic` 그림 | |
| GEUS | `TileWMS` **512×511 타일** | text/plain 을 풀어 | HTML 쪽이라 **링크** | 아래 |
| KPDC | `TileWMS` 3031·3413 | JSON | 그림 | 아래 |
| 그린란드 포털·NPI 점 | — | — | — | ArcGIS GeoJSON 을 장을 넘겨(0.5 초 쉼), 서버의 `/points/` 와 같은 덩이로 |

## 3. 함정

- **GEUS 는 정사각 그림을 막는다.** 검토(§2.2)는 403 이 `whoami` 때문인지 정사각 때문인지 가르지 못했다. 쟀다 — `whoami` 를 비우든
  `GSM` 이든 600×600·512×512 는 403, 601×600 은 200. **정사각이 까닭이다.** GEUS 가 권하는 `singleTile`(`ImageWMS`, 화면 한 장)로
  먼저 짰다가, 뼈대(#140)의 고리가 늘 타일 레이어를 지어 얹히지 않아 바꿨다 — **타일 격자를 512×511 로** 잡는다(해상도는 여느 3857 과
  같고 세로만 한 줄 짧다). 그러면 여느 `TileWMS` 로 받히고 브라우저 캐시도 맞는다. `whoami` 는 각자의 이메일을 `gsm.key.geus` 에서
  읽는다(없으면 비운다 — 비워도 받힌다). GEUS 의 `_search` 판은 빈 곳이 많아 속성이 "없음" 인 자리가 흔하다(서버 판도 같다)
- **KPDC 는 이 서버에서 이름이 안 풀린다** — 연구소 망의 DNS 가 `kpdcgeo.kopri.re.kr` 을 모른다. 공용 DNS 로는 203.250.180.198 이고,
  그 주소로 붙이면 타일·속성·능력 문서가 200 에 **부른 출처를 그대로** 허락한다(github.io 로 쟀다). 정적 판은 보는 사람의 브라우저가
  부르므로 걸리지 않는다. 시험은 Chromium 에 `--host-resolver-rules` 로 주소를 알려 쟀다
- **연구소 망의 TLS 가로채기** — 이 서버의 브라우저로는 NPI·PGC 가 인증서 오류다("KOPRI SSL"). 밖의 브라우저와는 상관없다. 시험은 인증서
  검사를 끄고 쟀다
- 사용자가 정한 대로 **KPDC 의 지도 서버 레이어는 싣는다.** 모아 둔 파일에서 그리는 KOPRI 점(시료·운석·KPDC 목록)은 여기서 부를 상류가
  없다 — 굽는 쪽의 몫이다(`points: null`)

- **석류석 갈래의 판정 함수** — gsm-91 의 그린란드 다이아몬드(#134)가 갈래 표에 `lambda` 셋을 넣었다. JS 는 파이썬 함수를 못 돌리고
  JSON 으로 뜨지도 못한다. 셋 다 "그 열이 0 보다 크다" 라 `{"gt0": 열}` 로 글자로 적고 `class_of` 가 그 꼴을 읽게 했다(함수도 계속 받는다).
  정적 판의 표는 함수를 만나면 깨진다 — 다음에 누가 함수를 넣으면 시험이 알린다. 연속값(지화학, wetherilli 159)·수치 구간 갈래도 JS 에
  옮겼고, 원소마다 잘라 받는 전암 화학(3 만 점)은 굽는 쪽에 맡긴다
- **뼈대에 이은 것** — gsm-31 이 같은 PR 에서 넣어 달라고 해(#144 병합 뒤) 셋을 이었다.
  (1) 지도 화면이 표를 `<script id="static-tables">` 로 싣는다(`views.map_view`, 정적 판에서만). (2) map.js 범례 칸에 정적 판 갈래 —
  `layerKind(name).legend` 의 그림·줄·링크를 그리고, 받은 것을 그 레이어 항목에 담아 다시 묻지 않는다. (3) 점 레이어가 구운 파일이
  없으면 `layerKind(name).points` 로 상류에서 곧장. `static_site.py` 의 지역에 그린란드·스발바르·북극해·남극을, 상류에 극지 여섯을
  더했다. 극지연구소는 지도 서버 레이어만 곧장이고 모아 둔 점은 구운 것이 있을 때만 싣는다(`views._static_catalog`).
  브라우저 시험(`test_static_site`)이 극지를 넷 더 본다 — 카탈로그·표·스발바르가 NPI `export` 를 곧장 부르는지·범례를 열어도 멈추지 않는지.
  실제로 정적 판을 굽고 망을 열어 띄워 보니 스발바르는 그림·범례 줄·팝업(지질시대 한글)이, 그린란드는 굽지 않은 관입암 249 점과
  GEUS 512×511 타일이 섰다

## 4. 하지 않은 것

- **NPI 도폭 하나만 켜기**(`npolar:svalbard_sheets@A4G`) — 서버가 지도 서버의 레이어 목록을 받아 대응표를 짓는다. 정적 판에서는 묶음
  전체만 그린다(`@` 뒤를 버린다)
- 그린란드 포털의 큰 점 레이어(시료 2 만 점, 장 열 개)를 보는 사람마다 받는 것은 상류에 짐이다 — 검토(§4)가 권한 대로 **굽는 쪽이
  떠서 실으면 그것을 먼저** 쓰는 것이 낫다. 고리가 고를 수 있게 `points` 는 곧장 받는 길로만 두었다
- 지명 찾기(스발바르·그린란드·DML) — 정적 판의 찾기 칸은 뼈대의 몫이다. 표(`points` 의 `place_names`)는 실려 있다
