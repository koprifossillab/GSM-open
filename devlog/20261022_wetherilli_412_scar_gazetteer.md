# 남극 지명 — SCAR 통합 지명사전을 받아 두고 남극 탭의 찾기·이름표에

2026-10-22 · `feature/scar-gazetteer` · wetherilli

극지 자료 후보(`docs/극지_자료_후보.md`)의 셋째. 남극 탭의 지명 찾기는 드로닝모드랜드(NPI 4 074, wetherilli 096)뿐이라
세종·장보고 둘레도, 로스해도 이름으로 갈 수 없었다. 이름표 레이어도 없었다.

## 상류와 조건

- AADC GeoServer WFS `https://data.aad.gov.au/geoserver/aadc/ows`, `aadc:SCAR_CGA_PLACE_NAMES`(설명·내력·축척 열 60 개 남짓)와
  `_SIMPLIFIED`(열 열둘). GeoJSON, CORS `*`, 열쇠 없음 — 2026-10-22 에 다시 확인했다. 이름 39 185, `scar_common_id` 로 묶으면 지형 20 157
- 정보 페이지(`data.aad.gov.au/aadc/gaz/scar/information.cfm`)는 지금 `placenames.aq` 로 넘어가고, 그 앱의 "Citation information"·
  "Data services" 쪽에 적힌 것은 인용 꼴 하나다:
  > When citing this dataset, use the following example as a guide.
  > Secretariat SCAR (1992, updated 2025). Composite Gazetteer of Antarctica, Scientific Committee on Antarctic Research. (http://placenames.aq/)
- 라이선스 문구는 AADC 가 만든 rOpenSci `antanym` 의 README 에 있다:
  > The SCAR Composite Gazetteer of Antarctica is made available under a CC-BY license. If you use it, please cite it
- AADC 메타데이터 API 에서 `SCAR_Gazetteer` 레코드는 찾지 못했다(`No DIF found`). 검색에 걸린 `gaz` 레코드(CC BY 4.0)는
  **호주 남극 지명사전**이라 CGA 의 근거로 쓰지 않았다
- 생각(CC BY, 인용)과 같아서 묻지 않고 붙였다. 저장·가공 금지나 비상업 조건은 어디에도 없다

## 갈래 — 온 지구 찾기에 얹지 않고 지역의 `placenames/` 에

`earth/places/`(geonames)는 "주소·지명 찾기가 없는 지역 탭" 이 빌리는 길이고, 남극은 이미 지역 지명 찾기(`PLACE_SOURCES`)가 있는
탭이다. 그 길은 `arcpoints.name_index`·`match_index` 로 **이름 여럿 → 괄호로 곁들임** 을 이미 하고 있어서, 나라마다의 이름
(부스섬 = `Booth, isla`·`Boothinsel`·`Wandel, Ile` …)을 살리기에 꼭 맞다. 그래서 `PLACE_SOURCES["antarctica"]` 에 SCAR 를 앞에
더했다. sqlite 로 굽지 않은 것은 2 만 지형이라 메모리 색인(파일 고친 때가 열쇠)으로 넉넉해서다 — GeoNames 는 17 만이라 sqlite 였다.

이름표는 중국 1:400만의 지명(wetherilli 389)과 같은 `style: label` 점 레이어(`scar:place_names`)다. 화면은 손대지 않았다 —
`placeLabelStyle` 이 `rank`·`kind` 를 그대로 읽는다.

## 받기

- `fetch_scar_gazetteer` — `_SIMPLIFIED` 에서 여섯 열(이름·지명사전·갈래·묶음 번호·위경도)만 골라 1 만 건씩, 쪽 사이 1 초. 네 쪽, 14 초.
  `narrative`(설명)를 담으면 파일이 열 배가 되는데 찾기·이름표에 쓰지 않아 뺐다. 누르는 속성 레이어는 만들지 않았다(일을 넓히지 않는다)
- 지형마다 `[번호, 경도, 위도, 갈래, [[지명사전, 이름], …]]` 로 묶어 `<SCAR_DIR>/cga_place_names.json`(1.7 MB, gzip 430 KB)
- **보이는 이름은 KOR → USA → GBR → AUS → NZL** 차례로 고른다. 자리도 그 이름의 줄의 것이다 — 나라마다 자리가 조금씩 다르다
- cron 에 두지 않았다. 지명사전은 나라들이 이름을 더할 때 자라는 것이라 판 전이나 몇 달에 한 번 사람이 부른다

## 이름표의 크기

CGA 에는 크기·중요도 열이 없다(`aus_display_scale_*` 는 호주 것뿐). **이름 붙인 나라의 수**를 크기로 썼다 — 로스 빙붕·남극반도
같은 큰 지형은 대여섯 나라가, 이름 없는 바위는 한 나라가 붙인다. 큰 갈래(빙붕·해안·땅·산맥·고원 …)이고 셋 이상이면 줌 3 부터,
기지는 줌 5 부터(점을 찍는다), 그 밖은 나라 수가 적을수록 가까이서. 물(만·해협·만입…)은 파랗게. 줌 9 부터 다 뜬다.

## 버린 것·남은 것

- **한글 이름은 없다.** 한국 지명사전(KOR) 27 개도 로마자(`Sejong Cape`)다. "세종" 으로 찾으려면 사람이 한글 표를 따로 둬야
  해서 이번에는 하지 않았다
- **장보고 기지가 CGA 에 없다.** "King Sejong Station" 은 미국 지명사전에 있다. 상류의 일이라 손대지 않았다
- 드로닝모드랜드는 NPI 의 것이 더 촘촘해(4 074 대 CGA 의 노르웨이 1 706) 함께 뒤진다. 이름이 같고 0.05° 안이면 하나만 남긴다
  (`views._distinct_places`)
- **정적 판에는 싣지 않았다.** 조건은 열렸지만 정적 판의 지명 색인은 `PLACE_FIELDS`(구운 점 덩이) 길이라 따로 굽는 손이 든다.
  조건이 "CC-BY" 라는 근거도 지명사전 쪽이 아니라 antanym README 다 — 밖에 열기 전에 사람이 placenames.aq 에 물어 확인하면 좋다
