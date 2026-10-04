# 브라질 — SGB 의 노두·연대측정·화석 산지 점

2026-10-04 · `feature/brazil-points` · wetherilli

판 세션이 맡겼다. 근거는 TODOs 남미의 "브라질 SGB 의 점 레이어" 줄이다(wetherilli 191 에서 남겨 둔 것). 정할 것은 없었다.

## 1. 쟀다 (2026-10-04, 요청 사이 2 초, 열다섯 번 남짓)

같은 GeoServer(`geoservicos.sgb.gov.br/geoserver/ows`)의 세 레이어다. 모두 4326 점이고 WFS·WMS 가 다 열려 있다.

| 레이어 | 점 | 나라 전체 512 칸 한 장 | 가까이(80 km) |
|---|---|---|---|
| `geosgb:afloramentos` 노두 | 359 014 | 12.5 초, 새카맣다 | 2.2 초 |
| `geosgb:geocronologia` 연대측정 | 3 158 | 2.1 초 | 1.1 초 |
| `geosgb:ocorrencias_fossiliferas` 화석 산지 | 9 512 | 2.9 초 | 1.1 초 |

- GetFeatureInfo 는 1:100만처럼 `propertyName` 을 받는다. 없는 열을 하나라도 적으면 예외("PropertyDescriptor is null")라 레이어마다 열을 따로 적었다
- **연대측정 레이어에 연대 값이 없다.** 시료 이름·암석·측정법(`Sm-Nd - Idade modelo` 가 절반)·분석 재료·공개 단계뿐이다. 공개 단계는
  "Acesso livre" 2 870, "Acesso restrito" 73 — 제한된 것도 WMS 에는 자리가 나온다. SGB 가 열어 둔 것을 그대로 보인다
- 화석의 시대 칸(`unidade_cronoestratigrafica`)은 손으로 적은 글이다 — 814 가지이고 "IDADE QUATERNARIO", "Era Paleozóica, Período
  Devoniano Inferior", "SEM REGISTRO", 줄바꿈이 든 "ERA CENOZOICO\r\nPERIODO TERCIARIO\r\nEPOCA PLIOCENO" 가 섞여 있다

## 2. WMS 로 — 한 덩이(`kind: points`)는 버렸다

판 세션이 "점이 많으면 한 덩이로 받을지 WMS 로 받을지 재 보고 고르라" 했다.

- 노두는 35 만 점이라 한 덩이로 받을 수 없다(그린란드 전암 화학 3 만 점도 `slice` 로 잘라 줬다, wetherilli 163). WMS 뿐이다
- 연대측정·화석은 한 덩이로도 받을 수 있는 수다. 그래도 WMS 로 두었다. 한 덩이로 받으면 우리가 점을 칠하고 누른 자리를 찾는 셈을
  새로 짜야 하는데, 이 둘은 갈래로 칠할 열도 마땅치 않다(화석의 `sistematica` 는 82 % 가 비었다). 같은 문·같은 길(`npolarSource`·
  `wmsInfoUrl`)에 레이어 세 줄을 더하는 것으로 끝난다
- 노두는 **줌 8 부터**(`minZoom`) 그린다 — 1:100만(6)·1:25만(9) 사이다. 줌 8 은 타일 한 장이 150 km 남짓이라 점이 갈려 보인다

## 3. 손질

- 값은 포르투갈어 그대로 둔다(이름·설명·암석은 옮기지 않는 규칙). 손으로 적은 글이라 줄바꿈·겹친 빈칸만 하나로 편다
- **화석의 시대 칸은 옮기지 않았다.** 1:100만의 `sistema_max` 처럼 낱말 하나면 `age_en` → `age_ko` 로 옮기지만, 이것은 문장이라
  낱말을 골라 내다 틀리기 쉽다("NAO DETERMINADA DEVIDO A AUSENCIA …"). 이름도 "지질시대" 가 아니라 "층서 시대" 로 해서 옮긴 값과 갈랐다
- 사람 이름 열(노두의 `geologo`, 화석의 `coletor`·`analista`)은 싣지 않았다 — 팝업에 쓸 까닭이 없다. 문헌 칸에 든 저자 이름은 문헌이라 둔다
- 점 레이어는 범례가 없다(`noLegend`) — 한 색 기호 하나다

## 4. 조건

SGB 의 다른 레이어와 같은 **CC BY-NC 4.0** 이다. 정적 판에 싣지 않는다 — `static_site.py` 는 손대지 않았다(브라질은 거기에 없다).

## 5. 확인

- `test_sgb` — 셋의 손질, 노두만 줌 8, 범례 없음, 화석 GetFeatureInfo 의 `propertyName`. 전체 시험 통과
- 문으로 상류를 한 번 불러 봤다 — 브로두스키 둘레의 화석 산지 한 장(1.9 KB)과 누른 자리의 "CPDG000009 · Icnofóssil · Formação Botucatu"
