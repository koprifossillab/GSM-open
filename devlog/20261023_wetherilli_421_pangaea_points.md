# PANGAEA 극지 현장 자료 — 현장 다섯의 둘레를 모아 두고 주제마다 점 레이어로

2026-10-23 · `feature/pangaea-points` · wetherilli

극지 자료 후보 2 차(`docs/극지_자료_후보.md` "2 차 조사" 의 7·15). 세종 기지 둘레만 보아도 PANGAEA 에 자료가 582 건인데
지도 위에서는 하나도 보이지 않았다. KPDC 자료 레이어(055·056)처럼 **자료마다 한 점**을 두고 누르면 DOI 로 잇는다.

## 상류와 조건

- `https://ws.pangaea.de/es/pangaea/panmd/_search` — PANGAEA 검색 화면이 쓰는 Elasticsearch. 열쇠가 없고 `meanPosition` 에
  `geo_bounding_box` 가 먹는다. **CORS 머리가 없다** — 서버의 문(`pangaea.py`)으로 가고, KPDC 처럼 모아 둔다(`fetch_pangaea`).
  화면이 부를 때 상류를 타지 않는다. 옛 판이라 `track_total_hits` 를 받지 않고 `total` 이 수 하나다(새 판의 `{"value": n}` 도 읽는다)
- 이용 약관(`https://www.pangaea.de/about/terms.php`, 2026-10-23 에 읽었다):
  > 3.1.1 … Metadata is always freely accessible.
  >
  > 6.2 By submitting research content and metadata to the PANGAEA platform the content will be published under the
  > Creative Commons license CC0 for metadata and CC-BY for data. Exceptions have to be negotiated on an individual basis with PANGAEA.
- 그래서 **메타데이터만 싣는다** — 제목·저자·연도·사업·주제·자료의 조건·DOI. 자료 본문은 싣지 않고 DOI 로 잇는다.
  받은 5 622 건의 조건은 CC-BY-4.0 2 338 · BSRN-1.0 1 712 · CC-BY-3.0 1 414 · UNKNOWN 102 · 비상업(NC) 48 · CC-BY-SA 5.
  비상업 자료도 목록(메타데이터)은 CC0 라 뺄 까닭이 없다 — 팝업에 조건을 그대로 적는다
- **정적 판에 싣는다**(사용자, 2026-10-23) — CC0 이고 구운 점(`bake_static`)이라 상류를 타지 않는다. 현장 이름이 말마다 달라
  KPDC 처럼 두 벌(`.en.json`)을 굽는다

## 모을 범위 — 사용자가 정했다

건수를 hits 만으로 세어(본문 없이) clear-conversation 에 물었다.

| 범위 | 건수 |
|---|---|
| 남위 60° 남쪽 | 32 633 |
| 북위 60° 북쪽 | 66 923 |
| 킹조지섬 전체 (세종) / 바턴반도만 | 765 / 582 |
| 테라노바만 (장보고) | 74 |
| 콩스피오르 (다산) | 4 590 — BSRN 1 730·AC3 1 028·AWI 기상 569 |
| 디스코만 / 자켄베르그 | 136 / 79 |
| 남위 60° 남쪽의 Lithosphere | 4 233 |
| 북위 60° 북쪽의 Lithosphere | 9 387 |

답: 현장 둘레는 주제를 가리지 않고 다(그린란드는 디스코만·자켄베르그 둘 다), 그 밖의 극지는 Lithosphere 만. 그리고
"규모가 크면 이번에 다 하지 말고 TODOs 에". **극지 전체의 Lithosphere 는 이번에 받지 않았다** — 13 620 건이고 조건이 든 XML 이
지질 자료는 건당 36 KB 남짓(100 건에 3.7 MB)이라 한 번에 500 MB 를 받는다. 1 초에 한 번 70 쪽이면 시간은 짧지만 받는 양이
크고, 한 탭에 수천 점이 서면 그리기도 따로 봐야 한다(그린란드 전암 화학처럼 `slice` 를 쓸지). TODOs 에 "다음" 으로 두었다.
`AREAS` 에 네모와 주제 거르개를 더하면 같은 명령이 받는다.

## 판단

- **자료의 조건이 큰 XML 에만 있다** — `agg-license` 같은 열이 비어 있고 `techKeyword` 는 묶어 셀 수 없다. 받을 때 `xml` 을 받아
  `<md:license><md:label>` 만 뽑고 버린다. 제목은 작은 `xml-thumb` 에서. 현장 다섯은 서른 쪽 남짓, 받은 파일은 1.9 MB 다
- **자리는 가운데 한 점**(`meanPosition`). KPDC 처럼 범위를 면으로 그리지 않는다 — PANGAEA 의 범위는 항해 자료면 대양을 덮고,
  현장 둘레만 모으니 점으로 충분하다. 다산 기지 옆 두 점에 3 500 건이 겹친다(BSRN·AWI 기상의 달마다 자료) — 누르면 겹친 것이 다 나온다
- **주제는 PANGAEA 의 주제 꼬리표(`agg-topic`)로 가른다**, 위에서부터 먼저 맞는 것 — 지질·퇴적물(Lithosphere·Paleontology)·빙권·생물·
  해양·대기·화학·그 밖. 퇴적물 지화학은 Chemistry 와 Lithosphere 를 함께 달아 지질로 간다. 처음엔 "그 밖" 이 스발바르에서 3 155 였다 —
  **꼬리표가 없는 자료가 3 600 건**(대부분 관측소의 연속물)이라. 사업(BSRN·AC3·AWI_Meteo → 대기, 바이엘바 영구동토 → 빙권)과
  제목 낱말(sediment·core → 지질, CTD·oceanography → 해양, snowfall·radiosonde·photometer → 대기)로 갈라 스발바르 "그 밖" 을 64 로 줄였다
- 레이어는 **탭 × 주제**(KPDC 와 같다) — 남극 7·스발바르 7·그린란드 6. 그린란드 빙권은 한 건이라 씨앗에 넣지 않았다(문은 안다).
  세종과 장보고는 한 남극 레이어에 든다 — 팝업의 "현장" 이 가른다
- 현장 이름은 팝업의 **값**이라 화면의 `T()` 가 옮기지 못한다 — 서버가 말마다 옮겨 낸다(`file_body(name, lang)`)
- 저자는 셋까지, 넘으면 "et al." — 사람 이름 줄이라 옮기지 않는다
- 다시 받기는 통째로다(서른 쪽, 몇 분) — 바뀐 것만 받는 길(`sp-lastModified`)은 극지 전체를 받게 되면 그때 둔다. cron 에 두지 않는다

## 버린 것

- 브라우저가 곧장 부르기 — CORS 가 없다
- 그때그때 서버가 받아 캐시에 담기(점 레이어의 문 `_POINT_DOORS`) — 한 레이어를 열 때마다 쪽 수십 장을 묻게 되고 XML 이 무겁다
- 범위를 면으로 그리기 — 위의 까닭

## 로컬에서 받을 때

이 서버의 파이썬 3.14 는 X509 엄격 검사(`VERIFY_X509_STRICT`)가 켜져 있어, 연구소 망이 다시 서명한 `ws.pangaea.de` 인증서
(Authority Key Identifier 가 없다)를 거부한다. 운영 컨테이너(파이썬 3.12)는 같은 꾸러미로 200 을 받았다. 검증을 끄지 않았고,
로컬 측정은 엄격 깃발만 끈 감싸개로 한 번 돌렸다. 컨테이너의 파이썬이 3.13 을 넘으면 이 문에서 같은 일이 난다 — 다른 문도 같다.
