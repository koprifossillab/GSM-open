# 동남아 — 인도네시아 범례를 보는 범위의 것으로

2026-10-05 · `feature/sea-legends` · wetherilli

wetherilli 228 이 TODOs 에 남긴 "인도네시아 범례 1 403 칸은 보는 범위의 것으로 뜰 만하다" 를 판 세션이 맡겼다. 같은 꼴로 범례가 너무 긴
동남아 나머지 셋이 있으면 함께 보라고 했다. 정할 것은 없었다.

## 1. 쟀다 (2026-10-05, 요청 사이 2 초, 여섯 번)

- ESDM 의 REST(`geoportal.esdm.go.id/gis4/rest/services/BGS_PM/Geologi_Litologi/MapServer/0`)는 WMS 와 **열 이름이 다르다** — WMS 속성은
  `NotasiFormasi`·`NamaFormasi`·`UmurFormasi` 인데 REST 는 `simobj`·`namobj`·`umurobj`, 개수를 셀 열은 `objectid_1` 이다. WMS 의 이름으로
  통계를 물으면 "Unable to complete operation"
- 칠하기 규칙은 `simobj` 하나로 가른 1 402 칸, REST `legend` 는 1 403 칸(470 KB)이다
- 통계 질의 — 반둥 둘레 0.6° 에 61 줄 0.6 초, 자바 서부 6° 에 458 줄 1.0 초
- 나머지 셋은 범례가 길지 않다 — 말레이시아 암상 46 칸(목록), 필리핀 27 칸(그림), 태국 94 칸(목록). 그대로 두었다

## 2. 이렇게 했다

- 사우디(wetherilli 227)·호주(212)와 같은 꼴 — `esdm.extent_legend` 가 범위 안의 단위(기호·이름·시대)와 면 수를 세고, `esdm.colors` 가 칠하기 규칙
  (`arcpoints.renderer_colors`)을 30 일 담아 색을 찾는다. 길은 `esdm/legend/`
- 범례가 뜨는 범위는 6° 까지 — 자바 섬 서쪽 절반이 든다. 칸이 많으면 60 칸에서 끊고 "그 밖 N 칸" 이다. 시대는 속성과 같은 표(`esdm.AGES`)로 옮긴다
- 사우디는 견본 그림(REST `legend`)을 쓰지만 여기서는 색만 쓴다 — 칠하기 규칙이 채움색 하나라 그림을 받을 까닭이 없다(470 KB)

## 3. 확인

- `test_southeast_asia` 의 `IndonesiaLegend` — 통계 열과 개수 열, 색(규칙에 없는 값은 회색), 시대 옮김, 담아 둠, 넓으면 422, 카탈로그 행. 전체 시험 통과
- 문으로 반둥 둘레를 받았다 — 61 칸, 색을 못 찾은 칸이 없다
