# 001 — 상류 오픈API 를 훑는다

2026-09-23

인증키 심사를 기다리는 동안 상류가 실제로 무엇을 주는지 먼저 봤다.
**문서만 보고 만들었으면 레이어의 4 분의 1 을 못 썼을 것이다.**

## 문서가 말하는 것

`https://data.kigam.re.kr/guide/openapi` 가 주는 것은 넷이다.

| | |
|---|---|
| `GET /openapi/wms?key=` | 지질주제도 WMS. `REQUEST=GetMap` **고정**이라고 적혀 있다 |
| `GET /openapi/data?key=&q=&page=&size=` | 데이터셋 검색 |
| `GET /openapi/data/{dataset_id}?key=` | 데이터셋 상세 |
| `GET /openapi/file/{file_id}?key=` | 파일 내려받기 |

뒤의 셋은 `검색 -> dataset_id -> 상세 -> file_id -> 내려받기` 로 이어지는
한 줄기다. **이 저장소는 첫째만 쓴다** — 지도뷰어이기 때문이다. 나머지 셋은
언젠가 시료 자료를 끌어올 일이 생기면 그때 본다.

## 문서가 말하지 않은 것 셋

### 1. `GetFeatureInfo` 가 된다

문서의 요청변수 표는 `REQUEST` 를 `GetMap` 고정이라고만 적었다. 그런데 같은
사이트의 OpenLayers 예제(`/map/openapimanual/openlayersSample.html`)는
지도를 클릭할 때 `getGetFeatureInfoUrl()` 을 부른다. **문서와 예제가 어긋난다.**

`application/json` 으로 25 만 지질도 한 지점을 물었더니 이렇게 왔다.

```
지질시대    신생대 제4기
도폭        대전
지층명      충적층
지질기호    Qa
대표암석    흙,모래,자갈
```

**속성 이름이 이미 한국어다.** 번역표를 둘 필요가 없다. 팝업은 받은 것을
그대로 표로 그리면 된다 — 이 하나로 "클릭 속성 조회" 의 설계가 끝났다.

### 2. 상류는 GeoServer 다

같은 예제 소스에 주석 한 줄이 남아 있었다.

```js
url : 'https://data.kigam.re.kr/openapi/wms',
//url : 'https://data.kigam.re.kr/mgeo/geoserver/wms',
```

`/openapi/wms` 는 GeoServer 앞에 인증키 검사를 씌운 프록시다. 그래서
`GetCapabilities`·`GetLegendGraphic` 처럼 GeoServer 가 본래 주는 것들이
뒤에 있다. 실제로 `/mgeo/geoserver/wms?request=GetCapabilities` 는 키 없이
822 KB 를 돌려준다. 레이어 399 개, 지원 operation 은 셋
(`GetCapabilities`·`GetMap`·`GetFeatureInfo`).

**이 주소를 제품이 타게 하지 않기로 했다.** 문서에 없는 주소는 예고 없이
닫혀도 할 말이 없다. 씨앗을 한 번 뽑는 데만 쓰고, 뽑은 것은 저장소에 넣어
둔다(`data/kigam_layers.json`). 자세한 갈래는 CLAUDE.md 의 "두 개의 상류 주소".

문서화된 `/openapi/wms` 쪽은 `GetCapabilities` 를 막아놨다(400 Bad Request).
**그래서 제품이 스스로 카탈로그를 새로 고칠 길이 지금은 없다.** 상류에
레이어가 늘면 사람이 `seed_catalog --from-upstream` 을 불러야 한다.
불편하지만, 닫힐 주소에 제품을 매다는 것보다 낫다.

### 3. 레이어 목록 페이지가 틀렸다

`GetCapabilities` 의 `geoOpen` 워크스페이스 61 개와, 안내 페이지
(`/map/openapimanual/openapiLayerList.html`)의 목록을 대조했다.

**틀린 것 12 개.** 지화학도가 전부 `L_geochemMP_V`(바나듐)로 적혀 있다.
아연·지르코늄·철·칼륨·칼슘·코발트·크롬·티탄·납·구리가 다 바나듐이 되어 있는데,
실제로는 `L_geochemMP_ZN`·`_ZR`·`_FE2O3`·`_K2O`·`_CAO`·`_CO`·`_CR`·`_TIO2`
·`_PB`·`_CU` 로 다르다. 표를 만들며 한 칸을 끌어 복사한 자국으로 보인다.

**또 틀린 것 2 개.** 변성암 동위원소가 `L_1M_isotope_plutonic`(심성암과 같은
이름)으로, 광상 동위원소도 같은 이름으로 적혀 있다. 실제로는
`L_1M_isotope_metamorphic` 와 `L_1M_isotope_ore` 다.

**아예 빠진 것 15 개.** 좋은물지도 14 종(칼슘·염소·전기전도도·불소·중탄산염
·칼륨·마그네슘·나트륨·질산염·수소이온농도·규소·황산염·총용존고체·경도)과
수원정보(`gw_loct_att`).

그리고 `GetCapabilities` 의 `geoOpen` 레이어에는 **한국어 제목이 이미 붙어
있다** — 61 개 전부다. 사람이 이름을 옮겨 적을 이유가 더 없다.

## 그래서 정한 것

**레이어 카탈로그를 표로 둔다.** 사람이 문서를 보고 코드에 적어 넣지 않는다.
`GetCapabilities` 가 준 것을 씨앗으로 넣고, 사람이 손질하는 것은 레이어군
묶음뿐이다 — 제목은 상류가 61 개 다 주었다.

이 판단은 "레이어가 많아서" 가 아니라 **"상류 문서가 틀리기 때문"** 이다.
상류를 믿고 하드코딩했다면 그 오류가 그대로 이 뷰어의 오류가 됐다.

## 남은 것 — 키가 나와야 한다

- `geoOpen` 61 개가 `/openapi/wms` 로도 **실제로 그려지는지** 대조한다.
  `GetCapabilities` 에 있다고 오픈API 로 열려 있다는 보장은 없다.
  확인한 것만 `Layer.verified_at` 에 날짜를 남긴다
- `GetLegendGraphic` 이 `/openapi/wms` 로도 되는지 본다. 되면 범례를 자동으로 건다
- 호출 제한의 실제 수치. 문서는 "지나치게 잦은 호출" 이라고만 적었다.
  타일 캐시(`GSM_TILE_CACHE_SECONDS`)를 미리 둔 것이 이 때문이다
