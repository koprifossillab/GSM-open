# 남미 — 브라질 광물 산출·콜롬비아 금속광상도와 지구물리·아르헨티나 광상

2026-10-05 · `feature/south-america-resources` · wetherilli

미국·호주·캐나다·일본·영국·그린란드와 같은 꼴로 남미의 광물·지구물리를 찾았다. 셋은 기존 문의 표에 줄만 더했고, 페루는 미뤘다.

## 실측과 한 것

| 나라 | 서비스 | 올린 것 | 조건 |
|---|---|---|---|
| 브라질 SGB | GeoSGB GeoServer(`geosgb:ocorrencias_recursos_minerais`) | 광물 산출 점(줌 6 부터) — 광종·곳·경제성·광산 상태·모암·광체 형태·광화 지역 | CC BY-NC 4.0 (191) |
| 콜롬비아 SGC | `Mapa_Metalogenico_2022`·`Geofisica/Anomalias_Geofisicas_V2022` ArcGIS WMS | 광상·금속광화대·금속광상 지구, 자력 총강도·감마 3색 | 서비스 저작권 "Servicio Geológico Colombiano" |
| 아르헨티나 SEGEMAR | SIGAM GeoServer `e250K.DepositMetalif`·`DepositMinIndust` | 금속·산업 광물 광상 1:25만(줌 7 부터) | SEGEMAR 의 재산, 저작자 표기 (196) |
| 페루 INGEMMET | `SERV_OCURRENCIA_MINERAL`·`SERV_METALOGENETICO`·`SERV_AEROMAGNETIICO` | **미뤘다** | CC BY-NC-SA 4.0 (195) |

- 콜롬비아는 **WMS 번호가 REST 와 거꾸로다**(광상 REST 1700 = WMS 11, 금속광화대 1701 = 10). 기존 `sgc:<판>:<WMS 번호>` 규칙 그대로 판 둘(`met`·`geof`)을
  더했다. 광상 속성은 "Sin información"·"Desconocida" 로 채운 칸이 많아 `_value` 가 뺀다
- 브라질은 GeoSGB 의 다른 점(노두·연대·화석, 215)과 같은 줄 하나. 아르헨티나는 `PROPERTIES`(속성 열)와 이름표만 더했다. 광상의 `tamaño` 는
  지진의 "규모"(Magnitude)와 겹쳐 "광상 규모" 로 적었다
- **정적 판** — 브라질·페루는 비상업이라 싣지 않는다(기존과 같다). 콜롬비아는 정적 판에 1:50만(`co`)만 싣는 규칙(`STATIC_SHEETS`)이라 새 판은
  저절로 빠진다. 금속광상도·지구물리의 조건은 서비스에 저작권 이름뿐이라 실을지는 사람이 본다

## 뺀 것

- **SEGEMAR 자력 이상 1:25만** — 나라 전체에 작은 면 47 개(한 변 1.5 km 남짓)뿐이라 넓게 보면 보이지 않는다
- **페루** — 페루 문은 지질도를 REST 타일 캐시로, 단층을 export 의 타일 칸(`ingemmet/<판>/z/x/y`, URL 패턴에 판 이름이 박혀 있다)으로 받는다. 광물
  산출·금속광상도는 다른 서비스라 그 기계에 서비스를 얹는 손이 든다. 항공 자력은 ImageServer 다 — TODOs
- 브라질 opendata 의 광업 권역(ANM)·항공 지구물리 조사 범위 — 행정 자료라 미뤘다

## 확인

- 사본 DB: 아르헨티나 "Pampa de Carnota Norte · Ba · SEDEX", 브라질 "Mármore · Fazenda Piabanha, Brumado, BA · Estratiforme · São Francisco",
  콜롬비아 "Cementos El Cairo S.A. · Calizas · Marga · Productor - Cielo abierto". 콜롬비아 자력·감마·금속광화대 타일 200
