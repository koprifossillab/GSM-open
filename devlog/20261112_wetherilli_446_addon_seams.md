# 덧붙이의 이음매 — 다른 저장소의 앱을 얹을 자리, 차림, 형제 화면의 입구 (P19 1 단계)

2026-11-12 · `feature/addon-seams` · wetherilli

P19 의 1 단계다. ASM(남극 덧붙이, 따로 저장소)이 GSM 의 이미지 위에 앱 하나로 얹히려면 GSM 이 먼저 꽂을 자리를 내야 한다.
**GSM 은 ASM 을 모른다** — 이 판에는 "남극" 이라는 낱말이 든 이음매가 없다. 덧붙이가 없으면(`GSM_ADDONS` 가 비면) 전과 같이 돈다.

## 낸 것

| 이음매 | 자리 | 덧붙이가 두는 것 |
|---|---|---|
| 앱 | `settings.ADDONS` → `INSTALLED_APPS` | Django 앱 |
| 주소 | `gsmweb/urls.py` — `<접두사>x/<이름>/` | `urls.py` |
| 문 | `doors._modules` 가 덧붙이 폴더도 긁는다 | `REGISTRY = ` 가 든 파일 |
| 남극 격자 | `views.POLAR_SETS` 에 `doors.polar_sets()` | 그 파일의 `SETS`·`legend()` |
| 카탈로그 | `seed_catalog` | `data/*_layers.json`(`_지역`·`_상류` 를 꼭) |
| 번역·구운 자료 표 | `apps.ready` → `addons.merge()` | `i18n.py`·`datastatus.py` |
| 차림 | `GSM_REGIONS`·`GSM_HIDE_SCREENS` | — |
| 입구 | `GSM_SIBLINGS="ASM=/ASM/"` → 아이콘의 숨은 차림 | — |

읽는 손은 `viewer/addons.py` 하나에 모았다 — 이음매가 무엇무엇인지 그 파일 머리의 표가 답한다.

## 왜 그렇게 했나

- **이름으로 찾는다(등록하지 않는다).** 덧붙이가 `ready()` 에서 GSM 의 표에 스스로 끼워 넣는 꼴도 됐다. 그러면 무엇이 끼워졌는지가
  덧붙이의 코드에 흩어진다. 문이 이미 "파일 끝의 `REGISTRY`" 로 모이고 있어(wetherilli 371) 같은 꼴로 맞췄다 — 정해진 이름의 것이 있으면 싣는다
- **주소는 `x/` 밑에.** 덧붙이의 이름이 GSM 의 주소(`map/`·`earth/`…)와 부딪히지 않고, 나중에 GSM 이 같은 이름의 주소를 내도 깨지지 않는다
- **남극 격자는 뷰 없이 선다.** P19 는 "3 단계(빙저 값 격자)는 화면 이음매 없이 간다" 고 적었는데 재어 보니 틀렸다 — 화면은 상류 이름으로
  그리는 손을 고르고(`LAYER_KINDS`), 모르는 상류는 WMS 로 그린다. 그래서 둘을 더했다: 덧붙이의 문이 `SETS`(`polargrid.Set`)를 두면 GSM 의
  `polargrid/…` 길이 타일·누른 자리·카탈로그 행·3D 를 다 내고, 그 행이 `hand: "polargrid"` 를 실어 화면이 손을 고른다. 덧붙이는 굽기만 하면 된다.
  구운 자리는 `ADDON_DIR`(`<DB 옆>/addons`) — `Set.where` 가 설정 이름이라 GSM 이 모르는 설정을 가리킬 수 없다
- **차림은 탭만 줄이고 카탈로그는 줄이지 않는다.** 정적 판의 `_static_catalog` 처럼 서버에서 지역을 걸러 낼 수도 있었다. 그러면 다른 지역에 둔
  레이어를 빌리는 탭(`borrow` — 온 지구의 점은 한국 지역에 있다)이 빈다. 화면의 줄이기는 정적 판의 것을 그대로 쓴다(`STATIC.regions` → `ONLY`).
  값은 카탈로그 JSON 이 가벼워지지 않는다는 것이다 — 재어 보고 무거우면 "적힌 지역 + 빌리는 지역" 으로 줄인다
- **한국이 없는 차림.** `map.js` 에 `"korea"` 가 첫 탭으로 박혀 있었다(처음 지역·더한 탭의 머리·탭을 뺐을 때 돌아갈 곳). `HOME` 하나로 모았다 —
  한국이 있으면 한국, 없으면 차림에 적힌 첫 지역. 저장 열쇠의 `"korea"`(지역 이름이 붙지 않는 열쇠)는 그대로 뒀다
- **숨긴 화면은 링크와 주소를 함께.** 링크만 빼면 주소를 아는 사람에게는 그대로 뜬다 — 뷰 첫 줄의 `_shown()` 이 404 를 낸다.
  템플릿 여섯의 링크는 컨텍스트 프로세서(`viewer/context.py`)의 `hide` 로 가린다 — 뷰마다 넘기면 빠뜨린다
- **입구는 밖에 연 판에 서지 않는다**(`PUBLIC` 이면 `SIBLINGS` 가 빈다). 정적 판에서도 `server-only` 라 숨는다

## 버린 것·남긴 것

- **`map.js` 에 도구·패널을 등록하는 자리는 내지 않았다.** 모형 화면을 따로 두기로 해서(P19) 쓰는 것이 아직 없다. 연 것은 약속이 된다
- **데이터소스 씨앗(`sources.seed.json`)에 덧붙이는 길은 내지 않았다** — 덧붙이의 `fetch_*` 가 생길 때 낸다. 지금 `apps._record_fetch_commands` 는
  `viewer.management.commands.` 의 명령만 적는다
- **온 지구·3D·남극 고지형 3D 에 덧붙이의 레이어를 얹는 자리**도 아직이다. 다만 3D 는 `POLAR_SETS` 를 보므로 격자는 3D 의 목록에 선다(재어 보지 않았다)
- **`localStorage` 가 겹친다.** ASM 이 같은 사이트의 `/ASM/` 에 뜨면 GSM 과 저장 열쇠(`gsm.region`·켠 레이어)를 나눠 쓴다 — ASM 에서 켠 레이어 이름이
  GSM 의 기억에 남고(없는 레이어라 무시된다), 마지막 지역이 서로 덮인다. 2 단계에서 푼다 — 차림에 이름을 실어 열쇠를 가르거나, 덧붙이가 제 머리말을 둔다
- **소개 화면(`/`)** 은 GSM 의 것 그대로다. 차림이 숨긴 화면의 문만 뺀다. ASM 이 제 첫 화면을 둘지는 2 단계에서

## 확인

- `viewer/tests/test_addons.py` — 가짜 덧붙이(`tests/fake_addon`)가 이음매마다 한 번씩 지나간다. 덧붙이가 없을 때 손이 다 비어 있는지,
  같은 상류를 겹쳐 적으면 멈추는지, 같은 번역 열쇠는 GSM 것이 이기는지도 본다
- 브라우저(`ProfileScreen`) — 남극만 세운 차림으로 화면이 뜨고 탭이 하나다. `HOME` 을 `"korea"` 로 되돌려 보니 `Cannot read properties of
  undefined (reading 'proj')` 로 깨졌다 — 시험이 고침을 본다
- `manage.py test viewer --parallel 8` — 2 526 개(건너뜀 14). 처음엔 하나가 깨졌다: 새 자료 자리 `ADDON_DIR` 을 시험 러너의 표(`testrunner.REDIRECT`)에 더하지 않았다 — 더하고 통과

## 판 세션에

- CLAUDE.md 에 "덧붙이" 절이 필요하다(환경변수 넷, `addons.py`, `x/` 주소, 가짜 덧붙이 시험) — 병렬 갈래라 여기서 고치지 않았다
- `.env`·compose 는 고치지 않았다 — 운영 GSM 은 넷 다 비워 둔다. `GSM_SIBLINGS` 는 ASM 이 뜬 뒤에 운영에 건다
