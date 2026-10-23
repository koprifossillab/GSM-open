# 북극 지질도 1:500만 — 같은 NRCan 서버를 북극해 탭에, 3413 으로 곧장

2026-10-22 · `feature/arctic-geology-5m` · wetherilli

극지 자료 후보(`docs/극지_자료_후보.md`, 북극 8)의 첫째다. GSC Open File 5816(Harrison 외 2008, 국제 극지의 해에 북극 나라들과
CGMW 가 함께 엮었다)은 60°N 북쪽의 **육상과 해저 기반암을 한 장에** 그린다 — 러시아 북극까지. 북극 탭에는 지금껏 나라마다의
지질도(GEUS·NPI·NGU·SGU·GTK·NÍ)와 EMODnet 해저 지질뿐이라 캐나다 북극제도·시베리아·북극해 한가운데가 비어 있었다.

## 조건

open.canada.ca 의 기록(`9f4aacbb-42eb-be93-f0a0-9a30cf6d658f`, "Geological map of the Arctic, 1:5 000 000")이 `license_id: ca-ogl-lgo`,
Open Government Licence – Canada 다. 그 라이선스의 글:

> You are free to: Copy, modify, publish, translate, adapt, distribute or otherwise use the Information in any medium, mode or format
> for any lawful purpose. You must, where you do any of the above: Acknowledge the source of the Information by including any
> attribution statement specified by the Information Provider(s) and, where possible, provide a link to this licence.

출처 표기는 REST 의 `copyrightText` "Natural Resources Canada" 와 라이선스 링크다(`nrcan.ARCTIC_ATTRIBUTION`). 캐시에 담아도 된다 —
`NO_STORE` 에 넣지 않았다.

## 어떻게 — 문을 새로 내지 않았다

- **캐나다 지질도와 같은 서버다**(`maps-cartes.services.geo.ca/…/NRCan/international_polar_year_en/MapServer`). `nrcan.SERVICES` 에
  한 줄(`nrcan:arctic`)을 더했다 — 상류마다 문 하나
- **레이어는 하나로 묶었다** — 서비스는 넷(0 캐나다·미국, 1 해저, 2 그린란드, 3 북유럽·러시아)인데 따로 켤 까닭이 적다. 한 장의
  지도로 엮은 것이라 경계에서 서로 맞물린다. 해저(1)를 맨 밑에 두려고 `1,0,2,3` 으로 묻는다. 넷으로 가르는 것은 버렸다 — 레이어
  패널에 같은 지도가 네 줄로 서면 고르기만 번거롭다
- **3413 으로 곧장 받는다** — 원본은 3978 이고 Capabilities 도 3978·4326 만 적지만, 3413 으로 물으니 그대로 그려 주었다(그린란드가
  아래, 북극 탭과 같은 꼴). 다른 극지 상류처럼 옮겨 그리지 않아도 된다
- **북극해 탭(`arctic_ocean`)에 레이어군 하나**로 두었다 — 북극 묶음(`REGIONS.arctic.includes`)이 북극해를 모으므로 묶음 탭에도
  선다. 60°N 북쪽 전체라 그린란드·스발바르 같은 나라 탭에 빌려 주는 것(`borrow`)은 하지 않았다 — 그 탭들에는 더 고운 나라 지도가
  있다. 레이어군 차례는 EMODnet(10) 앞인 5 — 바다만이 아니라 땅과 바다를 다 덮는 바탕 지질도라서
- **넓으면 느리다** — 3413 의 256 px 한 장이 1 000 km 칸 3.4 초, 2 000 km 칸 7 초, 4 000 km 칸 31 초, 극 전체 512 px 62 초였다.
  `SLOW_FLOOR` 의 규칙(10 초 안에 온 첫 격자 줌 + 1)대로 처음 줌을 3 으로 두었다. 북극해·북극 탭이 줌 3 으로 열리므로 처음 화면에서
  바로 보인다

## 범례 — 보는 범위의 것

칠하기가 `COLOUR` 의 고유값 210 칸(해저 171 칸)이고 이름표가 `MAP_LABEL` 기호(`KQ2`·`m15`)뿐이라 GetLegendGraphic 은 읽을 수 없는
기호 목록이다. 사우디·호주처럼 **보는 범위에 든 단위를 REST 통계로 센다**(`nrcan.arctic_legend`, `nrcan/legend/`) — 네 레이어에
`MAP_LABEL,COLOUR,AGE_DESCRI,LITHOLOGY` 로 묶어 `Shape_Area` 를 더하고 넓은 것부터. 넓이는 범위로 자르지 않은 면 전체의 것이라
차례를 정하는 데만 쓴다. 색은 레이어의 칠하기 규칙(`drawingInfo`)에서 찾는다 — 네 레이어의 같은 값은 같은 색이었다(0·1 이 겹치는
104 값 모두). 규칙은 한 번 받아 30 일.

- **범위는 촘촘한 고리로 보낸다** — 위경도 네모를 모서리 넷만 주면 상류가 3978 로 옮길 때 극 둘레에서 찌그러진다. 변마다 24 점을
  찍은 고리라 주소가 길어 **GET 은 404** 였다 — 통계 질의만 POST 로 보낸다(`_rest_get(post=True)`)
- **극이 화면 안이면** 화면(`map.js` 의 범위 범례)이 가장자리만 옮긴 네모가 극 둘레를 빠뜨렸다 — 극 평사도법(3413·3575·3031)에서
  극이 화면 안이면 온 경도와 극까지로 넓혀 묻는다. 3857 의 끝인 85° 로 자르던 것도 극 평사도법에서는 90° 까지로 — 북극 전체(80–85° 와 80–90°)를 견주니 단위 177 과 179 였다(pan 리뷰). 지금 범위 범례를 쓰는 극지 레이어는 이것 하나다
- 넓다고 막지 않았다 — 1:500만이라 북극 전체도 단위가 수백이고 60 칸만 적고 "그 밖 n칸" 이다. 넓은 범위는 레이어 넷을 차례로 물어
  (80°N 북쪽 전체가 6–8 초) 느릴 수 있다 — 실패는 캐시에 담지 않는다

## 속성

GetFeatureInfo(`application/geojson`)가 영어 열을 준다. 기호·지질시대·암석·환경·변성 정도·지구조 구역(DOMAIN_R_1–3 을 이어)·
출처 지역·편집을 적고, 시대만 옮긴다. `AGE_DESCRI` 가 "middle and late Paleoproterozoic (Orosirian and Statherian) (2050 - 1600 Ma)"
꼴이라 `i18n.age_ko` 가 통째로는 못 옮긴다 — 끝의 연대 괄호와 절 이름 괄호를 떼어 따로 옮기고 다시 붙인다(`nrcan.arctic_age` →
"고원생대 중기 및 후기 (오로세이라기 및 스타테로스기) (2050–1600 Ma)"). "… and younger" 는 "… 이후" 다. 못 옮기는 조각은 원문이다.
"Not known" 인 변성 정도는 적지 않는다.

## 하지 않은 것

- **정적 판에 싣지 않았다** — 조건은 열렸고 CORS 도 되비추지만, 범례가 서버의 통계 길이고 넓게 보면 느려 정적 판의 첫 화면(넓은
  북극해)에 맞지 않는다. NRCan 은 정적 판 기본값에 없다(#153). `static_site.UPSTREAMS` 에 nrcan 이 없어 따로 막을 것은 없다
- **타일에 그려진 기호 글자**(상류가 단위마다 `MAP_LABEL` 을 찍는다)는 끄지 않았다 — 원도의 꼴이고 `dynamicLayers` 로
  끄려면 WMS 를 버리고 REST export 로 옮겨야 한다
- FGDB 를 받아 우리가 굽는 것 — 서비스가 돌고 조건이 열렸으니 지금은 중계로 족하다
