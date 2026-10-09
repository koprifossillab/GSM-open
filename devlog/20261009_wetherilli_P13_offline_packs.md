# 오프라인 묶음 — 박스 하나를 파일 하나로 구워 현장에서 키·망 없이 본다

2026-10-09 · 계획 · wetherilli (판 세션)

## 왜

사람이 바랐다(2026-10-09): 우리 서버·NAS 가 받아 둔 타일을 **박스 단위로 묶어** 현장(망 없음·키 없음)에서 폰으로 본다.
**다음 주 태백 야외 조사가 첫 쓰임이다 — 5만 지질도 장성 도폭과 그 둘레의 VWorld 를 굽는 것이 가장 급하다.**

사람이 정한 것
- **연구실 안에서만 나눈다** — 묶음 파일은 NAS(`N:\GSM\offline\`)와 연구소 판의 내려받기 칸에만 둔다. 공개 판(Pages)·GSM-open 에 올리지 않는다.
  비상업·연구실 현장용이라 KIGAM·VWorld 타일을 묶어 다시 내주는 것을 이 범위에서는 받아들인다(사람, 2026-10-09). CLAUDE.md 의 "받은 것을
  다시 내주지 않는다" 의 예외이고, **밖으로 나가는 길이 생기면 다시 정한다**
- **묶음 하나 200 MB 까지** — 넘으면 가장 깊은 줌부터 덜어 낸다
- 처음 구울 박스 — **장성(태백) 현장**, **한국 전체(얕게)**

## 모양 — 두 쪽이 따로 일하므로 파일 꼴을 먼저 못 박는다

### 박스 표 `data/offline_boxes.json`

```json
{"jangseong": {"title": "장성 도폭 (태백)", "region": "korea",
               "bbox": [128.75, 37.0, 129.0, 37.25],
               "layers": {"L_50K_Geology_Map": [8, 16], "vworld:Base": [8, 16], "vworld:Satellite": [8, 15]},
               "budget_mb": 200},
 "korea":     {"title": "한국 전체 (얕게)", "region": "korea",
               "bbox": [124.5, 33.0, 131.0, 38.7],
               "layers": {"L_250K_Geology_Map": [6, 11], "L_50K_Geology_Map": [6, 11], "vworld:Base": [6, 10]},
               "budget_mb": 200}}
```

- `bbox` 는 경위도. **장성 도폭의 네모는 KIGAM 도폭 틀(5만 도폭 색인)에서 확인해 고친다** — 위 값은 짐작이다(1:5만 도폭은 15′×15′)
- `layers` 의 값은 `[처음 줌, 마지막 줌]`. 레이어 이름은 카탈로그의 이름, 배경은 `vworld:<WMTS 레이어>`
- 굽기 전에 장수·크기를 어림하고(`--dry-run`), 200 MB 를 넘으면 마지막 줌이 높은 레이어부터 한 단계씩 내린다. 무엇을 덜었는지 머리에 적는다

### 묶음 파일 `<박스>-<날짜>.gsmpack`

라이브러리 없이 브라우저가 `Blob.slice` 로 읽게 단순하게 둔다.

```
0      8 B   "GSMPACK1"
8      4 B   머리 길이 N (uint32, little-endian)
12     N B   머리 JSON (UTF-8)
12+N   …     타일 바이트를 잇달아
```

머리 JSON

```json
{"box": "jangseong", "title": "장성 도폭 (태백)", "built": "2026-10-10", "gsm": "0.77.0",
 "bbox": [128.75, 37.0, 129.0, 37.25], "region": "korea",
 "note": "연구실 현장용 — 밖으로 나누지 않는다",
 "dropped": {"vworld:Satellite": 16},
 "layers": {"L_50K_Geology_Map": {"grid": "EPSG:3857", "type": "image/png", "zooms": [8, 16],
                                  "attribution": "한국지질자원연구원"},
            "vworld:Base": {"grid": "EPSG:3857", "type": "image/png", "zooms": [8, 16], "attribution": "VWorld"}},
 "tiles": {"L_50K_Geology_Map/12/3510/1580": [0, 18234], "...": [18234, 9120]}}
```

- `tiles` 의 열쇠는 `<레이어>/<z>/<x>/<y>` — **화면의 타일 격자(OpenLayers 의 tileCoord, 위에서 아래로 y)** 그대로다. 값은
  `[타일 바이트 시작(머리 뒤에서 센다), 길이]`
- 빈 타일(상류가 투명 한 장을 준 것)은 넣지 않는다 — 없는 열쇠는 "그 자리에 그릴 것이 없다" 로 본다
- **키는 어디에도 넣지 않는다** — 머리에도, 타일 주소에도

## 나눈 일

### 굽는 쪽 (서버) — 영미 세션 (`Git pull`), wetherilli 381, `feature/offline-pack-build`

1. `viewer/offlinepack.py` — 위 꼴의 쓰기·읽기(시험용). 문이 아니다. 먼저 올려 두면 보는 쪽이 시험 묶음을 이것으로 짓는다
2. `manage.py build_offline_pack <박스> [--dry-run] [--out DIR]` — 박스 표를 읽어 레이어마다 화면이 부르는 것과 **한 글자까지 같은** 요청을
   짓는다(`prewarm.plan_for` 의 계획을 빌린다, 029). 캐시에 있으면 그것을, 없으면 지금 길(문·캐시)로 1 초에 한 장씩 받는다 — **미리 데우기의
   빠르기 규칙 그대로**(CLAUDE.md, devlog 010). VWorld 는 `vworld.py` 의 WMTS 중계로 받는다 — 키는 문 안에서만
3. 출력은 `<DB 옆>/offline/` — 운영은 `/srv/GSM/db/offline/`. NAS 로 옮기는 것은 판 세션이 한다(영어 이름·chmod 666)
4. 연구소 판에 `/GSM/offline/` — 묶음 목록(이름·날짜·크기·덮는 범위)과 내려받기. **`GSM_PUBLIC` 이면 닫는다**(`views.LAB_ONLY` 와 같은 뜻)
5. 시험 — 작은 박스 하나를 가짜 타일로 굽고 다시 읽기, 예산을 넘으면 줌을 덜기, 머리에 키가 없기

### 보는 쪽 (화면) — 민수 세션 (`geological timeline ui`), wetherilli 382, `feature/offline-pack-view`

1. 묶음 들이기 — 지도(정적 판 포함)의 설정이나 관리 화면에 "오프라인 묶음 불러오기". 고른 파일(Blob)을 **IndexedDB 에 통째로** 두고 머리만
   읽어 목록에 보인다(이름·날짜·크기·지우기). 개인 레이어처럼 그 브라우저에만 있다
2. 타일 대신 내기 — 묶음이 덮는 레이어·배경은 **묶음에 그 타일이 있으면 묶음에서**, 없으면 지금처럼 망으로. `tileLoadFunction` 을 감싸
   `Blob.slice(시작, 끝)` → `URL.createObjectURL`. 묶음이 있으면 **키가 없어도 그 레이어가 켜진다**(정적 판의 KIGAM·VWorld)
3. 화면 — 묶음이 덮는 동안 작은 표(예: "오프라인: 장성 · 10-10")와 출처. 박스 밖으로 나가면 망이 없으면 빈다
4. 시험 — 휴대폰 화면 job 에 작은 시험 묶음을 들여 망을 끊은 채 장성 자리의 타일이 그려지는지
5. 정적 판의 서비스 워커(wetherilli 380)는 그대로다 — 묶음은 워커가 아니라 IndexedDB 가 맡는다

### 판 세션 — 철수 세션 (대장)

PR 을 모아 판을 올리고, 운영에서 `build_offline_pack jangseong` 을 굽고 NAS `N:\GSM\offline\` 에 둔다. 태백 조사 전에 폰에서 한 번 열어 본다.

## 현장에서 쓰는 순서 (사람에게 알릴 것)

1. 연구소 망에서 폰으로 `http://paleolab/GSM/offline/` 에 들어가 묶음을 내려받는다(또는 NAS 에서 옮긴다)
2. 공개 판 https://koprifossillab.github.io/GSM-open/ 을 "홈 화면에 추가" 해 앱으로 연다
3. 앱의 "오프라인 묶음 불러오기" 로 내려받은 파일을 고른다 — 그다음부터는 망·키 없이 그 박스가 보인다

## 하지 않는 것 (이번에는)

- 속성(누른 자리의 팝업) — 타일만 묶는다. 속성까지는 다음에 본다
- 공개 판에 묶음을 싣는 것
- 연구소 판(평문 http)에서 오프라인 — 서비스 워커가 돌지 않는다
