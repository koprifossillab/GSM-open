# 동남아 — 인도네시아·말레이시아·필리핀·태국 탭과 묶음

2026-10-04 · `feature/southeast-asia` · wetherilli

`docs/아시아_오세아니아_지질도.md` 의 추천 순서 일곱째. 판 세션이 정했다 — 열린 나라마다 탭, 남미·유럽과 같은 꼴의 묶음 `southeast_asia`(3857),
마이그레이션은 한 번에(0038).

## 1. 넷의 꼴

| 나라 | 문 | 길 | 속성 | 범례 |
|---|---|---|---|---|
| 인도네시아 | `esdm.py` | ArcGIS WMS(3857 은 Capabilities 에 없지만 그린다) | ESRI XML 만, 시대가 인도네시아어 | 두지 않는다(1 403 칸) |
| 말레이시아 | `jmg.py` | **WMS 가 꺼져 있다** — REST export·identify(멕시코 꼴) | identify JSON | REST 범례 목록(암상 46 칸) |
| 필리핀 | `mgb.py` | ArcGIS WMS(원본 3857) | ESRI XML 만 | WMS 그림(27 칸) |
| 태국 | `dmr.py` | ArcGIS WMS(원본 32647, 3857 을 그린다) | geojson 인데 기호·연도뿐 | REST 범례 목록(93 칸) |

## 2. 틀 하나 — `arcwms.py`

ArcGIS WMS 를 중계하는 문이 셋이라 같은 몸통(변수 고치기·그림 확인·속성 읽기)을 `arcwms.Door` 로 뺐다. **문이 아니다** — `requests` 를 쓰지
않고, 문이 제 `_get` 을 넘긴다. "상류마다 문이 하나, `requests` 는 문에만" 을 지키려고 그렇게 갈랐다. 속성은 판에 따라 geojson 을 주기도 하고
ESRI XML(`<FIELDS a="…"/>`)만 주기도 해서 둘 다 읽는다(`fields_xml`). 포르투갈(`lneg.py`)의 ESRI XML 은 `<Field><FieldName>` 꼴이라 다르다 —
옮겨 오지 않았다.

- **버린 것:** 넷을 한 문(`sea.py`)으로. 호스트도 기관도 달라 상류마다 문 하나라는 규칙에 어긋나고, 하나가 닫히면 고칠 자리가 넷에 섞인다

## 3. 나라마다

- **인도네시아는 줌 10 너머를 그리지 않는다** — 서비스의 maxScale 이 1:57만 7 790 이다. `lastZoom`(그 위에서 숨김)을 쓰면 확대할 때 지도가
  사라진다. 그래서 카탈로그에 `maxZoom` 을 주고 `map.js` 의 `npolarSource` 가 격자를 거기서 멈추게 했다 — 그 위는 OpenLayers 가 줌 10 타일을
  늘린다. 줌 14 에서 이어져 보이는 것을 확인했다(뭉툭하다). 격자 칸이 512 라 격자의 줌은 화면 줌보다 하나 작다
- **인도네시아 시대는 인도네시아어**(`Kuarter`·`Kapur`·`Permo Karbon`) — 값 28 가지를 한 번에 모아(`returnDistinctValues`) 표로 옮겼다.
  `Pra Tersier`·`Pre-Permia` 처럼 ICS 에 없는 것은 원문을 보인다
- **말레이시아는 주마다 레이어가 따로**다(암상 짝수·연대 홀수, 열다섯씩). 우리 레이어 둘이 각각 열다섯을 한 번에 export 한다. 주 경계에서 끊긴다.
  반도는 `AGE`(오탈자 `Caroboniferous`)를, 보르네오는 `GLN`·`GAM`/`GAX` 를 준다 — 둘 다 있으면 `GAM`/`GAX` 에서 시대를 짓는다
- **태국 속성은 기호와 편집 연도뿐**이다(열 이름도 태국어). 단위 이름은 REST 범례(`Qa ตะกอน…`)에 있어 한 번 받아 두고 기호로 찾아 붙인다.
  시대는 기호의 앞 대문자(태국 지질도의 관례 — `Tr`·`T`·`K`·`PE` 따위)를 이어 읽는다. 이름은 태국어 그대로다(값은 옮기지 않는다)
- **영어 시대 다듬기**(`i18n.age_tidy`) — 필리핀 `Quaternary [Holocene]`·`Pliestocene`·`Upper Miocene`, 말레이시아 `CRETACEOUS, JURASSIC`(젊은, 오랜)을
  `age_ko` 가 읽는 꼴로 고친다. 인도(wetherilli 226)의 다듬기와 겹치는데, 이번에는 문 밖(i18n)에 두었다

## 4. 목록 범례 길 하나 — `list/legend/`

우루과이(`dinamige/legend/`)·몽골(`mris/legend/`)처럼 문마다 길을 내면 동남아만 둘이 는다. REST 범례를 목록으로 내는 문(`legend_rows`·`LEGEND_LAYERS`)을
`views.LIST_LEGENDS` 에 적고 한 길로 받는다. 견본은 문이 받아 30 일 담아 둔다. 앞의 둘은 그대로 두었다 — 옮기면 화면의 주소가 바뀐다.

## 5. 묶음

`southeast_asia` — 태국·말레이시아·인도네시아·필리핀(2D·3D). 베트남·라오스·캄보디아·미얀마는 공개 서비스가 없다(docs) — 동아시아 탭의 CCOP
200만이 덮는다. 동아시아 묶음과 겹치지 않게 CCOP 은 빌리지 않았다.

## 6. 조건

넷 다 이용 조건 문서를 찾지 못했다(copyright 비었거나 기관 이름뿐). 정적 판에 싣지 않았다. 밖에 열기 전에 사람이 읽는다(TODOs).
