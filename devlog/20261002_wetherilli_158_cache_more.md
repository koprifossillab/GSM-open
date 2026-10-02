# 캐시의 빈 곳 — 3D 편 것을 담고, 속성 JSON 에 헤더, prewarm 이 KOPRI·Trek 을

2026-10-02 · `feature/cache-more` · wetherilli

TODOs "캐시·미리 받기" 의 남은 두 줄이다. 151(ETag·immutable) 다음이다.

## 1. 디스크에 담지 않던 길

**phyloserver 스캔 타일은 그대로 둔다.** TODO 는 이것을 빈 곳으로 꼽았지만 026 이 일부러 담지 않았다 — 같은 서버 디스크의 파일이라
우리 캐시에 또 담으면 디스크만 두 번 쓴다. 브라우저 쪽은 이미 `_tile` 의 하루 헤더(와 151 의 ETag)를 받고 있었다. 바꿀 것이 없었다.

**3D 의 `warp/` 는 담는다.** 3D 는 512 칸 타일을 한 화면에 수십 장 부르고, 한 장 펴는 데 0.1 초 남짓이다 — 원본이 우리 디스크라도
CPU 를 같은 일에 되풀이해 쓴다. 담지 않던 까닭(docstring)은 "원본이 우리 디스크라서" 였는데, 그건 원본을 받는 값이지 펴는 값이 아니다.

- 열쇠에 **원본의 판**을 넣는다 — 음영판·IBCSO 는 잘라 둔 폴더의 때(`_dir_version`), GeoMAP 은 자료의 판과 `RENDERER`(`geomap_version`).
  151 에서 만든 것을 그대로 쓴다. 원본을 다시 구우면 열쇠가 바뀌어 새로 편다
- 펴는 법을 고치면 `WARP_RENDERER` 를 올린다
- **스캔판의 편 것은 담지 않는다** — 원본을 하루만 믿는 연구실 자료라(026, `FRESH_SECONDS`) 편 것만 오래 남으면 원본과 어긋난다.
  판을 모르면(파일이 없다) 담지 않는다

## 2. 헤더가 없던 길

- **속성·범례 JSON** 열다섯(KIGAM `featureinfo`, GSJ·대만 범례, 달·화성·수성·온 지구의 속성·범례, IBCSO 속성 …)에 `Cache-Control` 이
  없었다. 데코레이터 하나(`browser_cached`)로 하루를 단다. **`Vary: Cookie, Accept-Language`** 를 함께 단다 — 언어를 쿠키로 고르므로,
  안 가리면 영어로 바꿔도 브라우저가 들고 있던 한국어 팝업을 낸다. 200 만, 뷰가 스스로 적은 헤더는 건드리지 않는다
- **범례의 옛것 길** — 상류가 못 줘 캐시의 옛것을 낼 때 헤더가 없었다. 한 시간으로 — 곧 다시 묻게
- **`dem/` 의 302**(AWS 로 넘기기) — 헤더가 없어 브라우저가 매번 서버에 물었다. 넘기는 자리는 바뀌지 않으니 하루

## 3. prewarm 이 모르던 것

- **KOPRI WMS** — NPI 와 같은 꼴(지역의 투영 3031·3413, 512 px)이라 `WmsPlan` + `PolarGrid` 그대로다. 투영은 화면과 같은 `kopri.wms_projection`
- **달·화성 Trek** — 레이어가 아니라 이름으로 부른다: `moon:units`·`moon:contacts`·`moon:linear`·`moon:dem`·`mars:units`·`mars:dem`.
  `--bbox` 는 그 몸의 경위도다. 격자는 줌 0 이 가로 2 장·세로 1 장(`trek.valid_tile`)이라 새 `TrekPlan` 을 두었다. 원도·크레이터는 우리 파일이라
  받을 것이 없다
- **열쇠는 뷰와 같은 함수다** — `moon_dem_key`·`mars_tile_key`·`mars_dem_key` 를 views 에 빼서 뷰와 prewarm 이 같이 쓴다. 문자열을 두 곳에
  적으면 한쪽만 바뀌는 날 prewarm 이 받은 것이 화면에서 안 맞는다(CLAUDE.md "한 글자까지 같아야")
- 빠르기는 그대로 — 1 초에 한 장, 차단 조짐이면 멈춤(`usage.paused`), 연달아 3 번 실패면 멈춤. `TrekError` 를 실패로 센다

**함정** — 처음엔 `TrekPlan` 에 `trek.mars_dem_tile` 을 넘겨 담아 두었다. 시험이 그 함수를 바꿔 끼워도 붙잡힌 원래 함수가 불려 **시험이 실제
Trek 을 탔다.** 받는 함수를 부를 때 찾게(`lambda`) 고쳤다.

## 4. 남긴 것

이번 판들이 더한 지역 투영 상류(EMODnet·GTK 3413, NGU 3575, 유럽의 3857 들)는 prewarm 이 아직 모른다. `views._layer_extra` 가 주는 투영으로
`WmsPlan` 을 지으면 되지만 3575 는 `PolarGrid` 가 모른다 — TODOs 에 남겼다.
