# 오프라인 묶음 굽기를 저장소 안의 독립 패키지로 — GSM 없이도 굽고, GSM 에서는 요청한다 (계획)

2026-10-21 · `main`(계획) → 단계마다 `feature/gsmpack-*` · wetherilli

사용자: 「GSM 없이 혼자 도는 굽기 도구에 가까워. 그리고 지금은 항상 터미널에서 호출해야 하잖아. GSM 에도 요청하는 길이 있으면
좋긴 하겠어」. 처음 꺼낸 말은 "하나의 모델로 구축해서 별개의 repo 로" 였다. 앞의 일은 P13(계획)·381(굽기)·382(보기)·384(속성)·385(자르기),
조건은 `docs/오프라인_묶음_조건.md`.

## 사람이 정한 것 (2026-10-21)

- **굽는 도구는 GSM 없이 혼자 돈다** — Django·`GSM.db`·GSM 의 import 없이 노트북 하나에서 박스 표를 받아 `.gsmpack` 을 굽는다
- **GSM 에서도 요청한다** — 터미널에서 `manage.py build_offline_pack` 을 부르지 않아도 연구소 판의 화면에서 박스를 잡아 요청한다
- **꼴과 읽는 쪽도 떼어 둔다** — 다른 앱(Cropobite 따위)이 같은 묶음을 열 수 있게
- **받는 길은 둘 다** — 쓰는 사람의 KIGAM·VWorld 키로 상류를 곧장 부르는 길, GSM 서버를 거치는 길. 연구실 안에서는 GSM 경유가 캐시를 나눈다
- **GSM 의 요청은 staff 가 승인해야 굽는다** — VWorld 를 수천 장 부르는 일이라 한 번 거른다
- **비공개로 시작한다** — 묶음 파일은 지금처럼 연구실 안에서만(P13). 바뀌는 것이 없다
- **별도 저장소가 아니라 이 저장소 안의 패키지다** — 아래 "버린 것"

## 버린 것 — 별도 저장소

처음 말은 저장소를 따로 두자는 것이었다. 짜임을 그려 보고 따져 보니 걸리는 것이 넷이라 저장소 안에 두기로 했다(사람, 2026-10-21).

- **AGPL 13 조** — GSM 이 비공개 저장소의 패키지에 기대면 GSM-open 에 민 소스만으로 GSM 을 다시 지을 수 없다. "소스로 갈 길" 이 반쪽이 된다.
  "비공개로 시작" 과 정면으로 부딪힌다. 걸리는 것은 코드가 아니라 **VWorld 타일을 담은 묶음 파일**이다 — 코드는 GSM 과 함께 AGPL 로 나가도 된다
- **빌드** — Docker 이미지·CI 가 비공개 저장소를 받으려면 토큰을 따로 챙겨야 하고, Actions 할당량(wetherilli 397)에 저장소가 하나 더 붙는다
- **판 맞추기** — 꼴(`GSMPACK1`)을 바꾸면 두 저장소의 판을 함께 올려야 한다. 지금은 커밋 하나다
- **문이 두 벌** — KIGAM·VWorld 를 부르는 코드가 두 곳에서 따로 늙는다

패키지가 GSM 을 import 하지 않게 지어 두면 **나중에 떼는 것은 옮기기뿐이다** — 다른 앱이 정말 쓰게 되거나 맡는 사람이 달라지면 그때 뗀다.

그 밖에 버린 것
- **브라우저에서 굽기** — VWorld WMTS 의 키가 브라우저로 나가고, 한 박스가 75 분(장성)이라 탭을 열어 둘 수 없다
- **요청하면 바로 굽기** — 위의 승인
- **다 구운 묶음을 NAS 로 저절로 옮기기** — 컨테이너에 NAS 가 붙어 있지 않다. 지금처럼 판 세션이 옮긴다(영어 이름·chmod 666)

## 짜임

```
tools/gsmpack/                     파이썬 패키지 `gsmpack` (이름은 기술이 소문자를 강제하는 자리) — Django·viewer 를 import 하지 않는다
  pyproject.toml                   의존은 Pillow(자르기), requests 는 곧장 받는 길에만(선택 의존 `[direct]`)
  gsmpack/format.py                꼴 쓰기·읽기 — 지금의 viewer/offlinepack.py 를 옮긴다
  gsmpack/boxes.py                 박스 표 읽기·검사 — data/offline_boxes.json 꼴
  gsmpack/bake.py                  굽는 고리 — 예산 맞추기(fit_budget)·박스로 자르기(clip_tile·clip_polygons)·이어 굽기(Parts)·빠르기(1 초에 한 장, 3 번 실패면 멈춤)
  gsmpack/sources/base.py          소스의 꼴 — grid_zoom·tiles·cached·fetch (지금의 KigamSource·VWorldSource 가 가진 것 그대로)
  gsmpack/sources/via_gsm.py       GSM 경유 — 화면이 부르는 주소(`/GSM/wms/`·`/GSM/vworld/…`)를 그대로 부른다. 키 없음
  gsmpack/sources/direct.py        곧장 — 쓰는 사람의 KIGAM·VWorld 키로 `/openapi/wms`·VWorld WMTS 를 부른다
  gsmpack/cli.py                   `gsmpack bake <박스표> <박스> --via gsm=<주소> | --direct [--dry-run] [--out DIR]`
  js/gsmpack-reader.js             꼴 읽기 — 지금 offline.js 안의 `Blob.slice` 읽기를 뗀다
  tests/                           unittest — Django 없이 돈다
web/viewer/offlinepack.py          지운다 — `gsmpack.format` 을 쓴다
web/viewer/management/commands/build_offline_pack.py
                                   얇아진다 — 박스 표·소스를 짓고 `gsmpack.bake` 를 부른다. 소스는 GSM 안의 것(아래)
```

### 소스가 셋이다

| 소스 | 어디서 | 키 | 캐시 | 쓰는 자리 |
|---|---|---|---|---|
| **GSM 안** | `kigam`·`vworld` 문과 `tilecache` 를 곧장 | GSM 의 것(문 안에서만) | 서버 캐시 | `manage.py build_offline_pack`, 요청 일꾼 |
| **GSM 경유** | GSM 서버의 HTTP 길 | 없음 | 서버 캐시(서버가 탄다) | 연구소 망 안의 노트북 |
| **곧장** | 상류 | 쓰는 사람의 것 | 없음(이어 굽기의 parts 뿐) | GSM 이 닿지 않는 곳 |

- **GSM 안 소스는 패키지가 아니라 viewer 에 둔다** — `kigam`·`vworld`·`tilecache` 를 import 하는 것은 viewer 뿐이어야 패키지가 혼자 돈다.
  패키지는 소스의 꼴만 정하고 viewer 가 그 꼴을 채운다
- **GSM 경유는 화면과 한 글자까지 같은 주소를 짓는다** — 그래야 서버 캐시의 열쇠가 맞는다(029). KIGAM 은 `prewarm.plan_for` 의 계획(3857,
  512 px)을 주소로 옮긴 것이라, 계획을 패키지에 복사하지 않고 **GSM 이 박스마다 받을 주소의 꼴을 알려 주는 길**을 하나 둔다
  (`/GSM/offline/plan/?layer=…` — 격자·타일 크기·주소 틀). 계획이 바뀌어도 패키지는 따라간다
- **지층 면(속성)** 도 GSM 경유는 GSM 에 묻는다(`/GSM/offline/units/?layer=&bbox=` — 지금 `gather_units` 가 하는 일을 길로 연다). 곧장은
  `/mgeo/geoserver` WFS 를 부른다 — 키를 묻지 않는 곳이라 키를 붙이지 않는다(CLAUDE.md "두 개의 상류 주소")
- **곧장 소스는 문이다** — CLAUDE.md 의 "상류마다 문이 하나" 에 **묶음 굽기에만 쓰는 둘째 문**으로 적는다. GSM 자신은 이 문을 쓰지 않는다
  (GSM 안 소스를 쓴다). 키는 환경변수(`GSM_KIGAM_KEY`·`GSM_VWORLD_KEY`)로만 받고 묶음·로그·parts 에 적지 않는다(`redact` 를 패키지에도 둔다).
  VWorld 는 서버에서 부를 때 `domain=` 없이 돈다(vworld.py, 2026-09-27). **부르는 IP 도 잡지 않는다** — 사람이 제 키로 다른 자리에서 불러 확인했다(2026-10-21)
- 빠르기 규칙(1 초에 한 장, 차단 조짐이면 멈춤, devlog 010)은 **패키지의 굽는 고리에 박는다** — 소스가 셋이어도 하나다. GSM 경유는
  GSM 의 `usage.paused()` 를 보지 못하므로 503·429 를 차단 조짐으로 읽는다

## GSM 에서 요청하는 길

```
지역 지도의 범위 팝업 ──"오프라인 묶음 요청"──▶ /GSM/offline/request/   박스·레이어·줌을 고르고 어림(장수·MB·덜 줌)을 본다
                                                  │ 요청 한 줄 (기다림)
관리 화면 "오프라인 묶음" 탭 ── staff 승인 ──────▶ │ (승인)
일꾼 ── 한 번에 하나 ── gsmpack.bake ───────────▶ │ (굽는 중 → 됨 / 실패)
/GSM/offline/ 목록 ── 내려받기                     ▼ <DB 옆>/offline/<박스>-<날짜>.gsmpack
```

- **박스는 범위잡기에서 온다** — 범위 팝업(wetherilli 401 에서 경위도 네모로 고쳤다)에 단추 하나. 한국·동아시아 탭에서만(지금 소스가 KIGAM·VWorld 뿐)
- **모델 `OfflinePackRequest`** — 요청한 이(이름 칸, 로그인 없이), 박스 JSON(`offline_boxes.json` 의 한 칸 꼴), 상태(기다림·승인·굽는 중·됨·실패·거절),
  승인한 staff, 묶음 파일 이름, 마지막 줄, 시각들. 박스 표(`data/offline_boxes.json`)는 사람이 손으로 적는 씨앗으로 남는다
- **어림은 요청 화면에서 곧장** — `--dry-run` 과 같은 셈(캐시에 있는 타일의 평균, 없으면 `GUESS_BYTES`)을 길로 열어, 200 MB 를 넘으면 무엇을 덜지 미리 보인다
- **승인은 staff 만** — 관리 화면(`/GSM/manage/`)의 탭. 승인할 때 박스·레이어를 고칠 수 있다
- **일꾼** — 승인하면 웹이 `manage.py build_offline_pack --request <번호>` 를 떨어진 프로세스로 띄운다. 잠금 파일로 **한 번에 하나**, 나머지는 줄을 선다.
  호스트 cron 에 두지 않는다 — 호스트는 `GSM.db` 를 열지 않는다(jikhanjung P03). 매시 일(`hourly.sh`)에 얹지도 않는다 — 75 분이 매시 일을 막는다
- **배포로 컨테이너가 다시 뜨면** 굽는 중이던 것은 멈춘다. 컨테이너가 뜰 때 "굽는 중" 이 남아 있으면 이어 굽는다 — 받은 것은 parts.sqlite 가 안다.
  배포 전에 굽는 중인 것이 있는지는 판 세션이 본다(배포 전 확인에 한 줄)
- `GSM_PUBLIC` 이면 요청·승인·목록이 다 닫힌다(`views.LAB_ONLY` 와 같은 뜻, 지금의 `/GSM/offline/` 처럼)
- 다 되면 목록에 뜬다. 알림(메일·메시지)은 두지 않는다

## 단계

단계마다 `feature/gsmpack-*` 브랜치·devlog 하나, 판 세션에 넘긴다. **1·2 는 동작이 바뀌지 않는 옮기기다.**

1. **패키지 뼈대와 굽는 고리 옮기기** (`feature/gsmpack-core`) — `tools/gsmpack/` 를 만들고 꼴(`offlinepack.py`)·박스 표·굽는 고리(예산·자르기·parts·빠르기)를
   옮긴다. viewer 에 GSM 안 소스를 두고 `build_offline_pack` 이 패키지를 부르게 한다. Docker 이미지와 CI 가 `pip install ./tools/gsmpack` 하고,
   CI 가 `python -m unittest discover tools/gsmpack/tests` 를 함께 돌린다. **확인 — 장성 박스를 옛 명령과 새 명령으로 구워 머리(`tiles`·`dropped`·`layers`)가 같다**
2. **읽는 쪽 떼기** (`feature/gsmpack-reader`) — `offline.js` 의 꼴 읽기를 `tools/gsmpack/js/gsmpack-reader.js` 로. GSM 은 정적 파일로 받아 쓴다
   (`STATICFILES_DIRS`). 꼴 명세를 패키지의 README 로 옮기고 P13 의 꼴 절은 거기를 가리킨다
3. **혼자 도는 소스와 명령** (`feature/gsmpack-cli`) — GSM 경유·곧장 소스, `gsmpack` 명령, GSM 의 `offline/plan/`·`offline/units/` 길. CLAUDE.md 의 문 목록·
   구조 절에 패키지를 적는다. `.claude/skills/offline-pack` 에 노트북에서 굽는 길을 더한다. **확인 — 연구소 망의 노트북에서 GSM 경유로 장성을 구워 1 단계의 머리와 같다**,
   곧장은 작은 박스 하나
4. **GSM 에서 요청하는 길** (`feature/gsmpack-request`) — 모델·요청 화면·어림·관리 탭의 승인·일꾼·이어 굽기. 화면의 글은 영어도 같은 커밋에서(i18n).
   휴대폰 화면 시험에 요청 화면을 더한다

## 열어 둔 것

- **곧장 소스를 연구실 밖 사람이 쓰는 것** — 코드가 GSM-open 으로 나가면 누구나 제 키로 VWorld 를 구워 담을 수 있다. VWorld 약관 19 조 ⑥("사전 승낙 없이
  데이터를 저장하지 못한다")은 굽는 사람의 일이지만, 도구의 README 에 그 조항을 적어 둔다. 공개 판(Pages)에 굽기를 여는 일은 하지 않는다
- **다른 상류** — 지금 소스는 KIGAM·VWorld 둘이다(스킬 2 절). 패키지의 소스 꼴이 정해지면 GSJ·BGS 따위를 더하는 것은 그 뒤의 일이다
