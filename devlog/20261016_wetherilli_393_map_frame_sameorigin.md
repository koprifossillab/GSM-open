# 지도 화면만 같은 출처의 iframe 에 연다

2026-10-16 · `fix/map-frame-sameorigin` · wetherilli

형제 앱 Cropobite(같은 서버 `http://paleolab/Cropobite/`)가 장소 화면에 GSM 지도를 iframe 으로 띄우고 싶어 했다 — 넘김은 392 의
`#ext=` 그대로다. GSM 은 Django 기본값 `X-Frame-Options: DENY` 라 막혔고, Cropobite 는 자체 Leaflet 지도로 대신 보였다.

사람이 셋 가운데 **지도 화면 하나만 `SAMEORIGIN`** 을 골랐다(2026-10-16). `map_view` 에 `@xframe_options_sameorigin` 하나.

- 버린 것 — 사이트 전체 `X_FRAME_OPTIONS = "SAMEORIGIN"`. paleolab 에는 다른 앱(phyloserver 따위)도 같은 출처로 서 있어, 그 어느 것이든
  GSM 의 관리 화면·admin 까지 감쌀 수 있게 된다. 클릭재킹의 문을 지도 하나로 좁혔다
- 다른 사이트에서 감싸는 것은 여전히 막힌다 — 같은 출처뿐이다
- 넘겨받은 점의 팝업 "Cropobite에서 열기" 는 iframe 안이면 `_top` 으로 연다 — 감싼 화면 안에 Cropobite 가 또 열리지 않게.
  홀로 연 GSM 에서는 전처럼 새 탭(`_blank`)
