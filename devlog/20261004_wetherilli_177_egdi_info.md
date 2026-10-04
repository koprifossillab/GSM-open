# 유럽 — EGDI 1:100만의 속성을 암상 판으로 켠다

2026-10-04 · `feature/egdi-info` · wetherilli

143 에서 EGDI 1:100만을 깔 때 속성을 꺼 두었다(`egdi.QUERYABLE = False`). 2026-10-02 에 쏴 보니 시대 판은 DB 오류를 냈고, 암상 판은
20 초 뒤 빈 답을 줬다. TODOs 에 "살아나면 켠다" 로 남겼던 것을 gsm-31 이 넘겨 다시 쟀다.

## 1. 몇 번만 쟀다

2026-10-04 에 두 판 × 두 자리(프랑스 중부·독일 헤센), 3 초 간격으로 네 번 물었다. 한도를 재려는 것이 아니니 더 묻지 않았다.

| 판 | 답 |
|---|---|
| 시대 `GeologicUnitView_Age` | 20 초 뒤 200 에 XML 예외 — `PSQLException … Connection reset`. 그대로다 |
| 암상 `GeologicUnitView_Lithology` | 2–3 초에 GeoJSON. 살아났다 |

## 2. 두 레이어 모두 암상 판에 묻는다

예외 문구가 "layer GeologicUnitView" 다. 두 판은 같은 덩이(`GeologicUnitView`)를 다르게 칠한 것이다. 게다가 암상 판의 답에 시대
URI(`representativeAge_uri`, 있으면 `…OlderAge`·`…YoungerAge`)도 들어 있다. 그래서 어느 레이어를 눌러도 암상 판(`egdi.QUERY_LAYER`)에
묻는다. 시대 판이 되살아나도 바꿀 까닭이 없다 — 받는 것이 같다.

버린 것: 시대 레이어만 계속 끄고 암상만 켜는 길. 같은 답을 주는데 레이어에 따라 누르기가 되고 안 되면 사람이 헷갈린다.

## 3. 팝업에 싣는 것

- **암상** — `lithology`. INSPIRE 의 영어 낱말(clay·sandstone …) 그대로다. 속성 값이라 옮기지 않는다
- **지질시대** — 시대 URI 의 끝 낱말을 ICS 꼴로 바꿔(`lowerCretaceous` → `Early Cretaceous`) 한국어판이면 `i18n.age_ko` 로 옮긴다.
  INSPIRE 는 아래·위 통을 lower·upper 로 적고, ICS 가 2020 년에 Chibanian 으로 정한 절을 아직 `ionian` 이라 부른다 — 둘 다 고쳐
  넘긴다. 윗·밑 연대가 다르게 있으면 "older - younger"
- **제공 기관** — 식별자 끝의 `FR-BRGM`·`DE-BGR`·`ES-IGME`. 범유럽 판이라 그 면을 어느 나라가 냈는지가 쓸모 있다

`name`(gu.gsml.1353 따위)·`specification_uri`·OGC nil URI 들은 뺐다. 모양은 꼭짓점이 수만이라(한 번에 90–240 KB) 문에서 버리고 속성만
캐시에 담는다. 누른 둘레(`buffer`)는 1 픽셀로 줄였다 — 기본값이면 이웃 면이 서넛 함께 왔다.

## 4. 확인

서버의 `featureinfo/` 를 거쳐 실제로 물었다 — 파리 한복판은 clay·지바절·FR-BRGM, 헤센은 sandstone·트라이아스기 전기·DE-BGR. 영어판은
Lithology·Chibanian·Provider. 상류가 다시 XML 예외를 주면 문이 오류로 올리고 화면은 "받지 못했다" 를 띄운다(캐시가 있으면 옛 답).
다시 죽어 오래가면 `QUERYABLE` 을 끈다.
