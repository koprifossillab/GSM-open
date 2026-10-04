# 유럽 — 프랑스·스페인·독일·포르투갈의 광물

2026-10-05 · `feature/europe-minerals` · wetherilli

나라 탭마다 광물 자료를 더했다. 넷 다 이미 있는 문의 서버라 문을 넓혔다.

| 나라 | 올린 것 | 길 | 조건 |
|---|---|---|---|
| 프랑스 BRGM | 광상·광화 지점(BD Gîtes)·광산(주 광종) | 같은 `geologie` WMS 의 `GITES_PT`·`MINES_PT` | Licence Ouverte |
| 스페인 IGME | 광물 산지·산업 광물·암석 채굴지(BDMIN) | `BasesDatos/IGME_BDMIN_*` WMS | AccessConstraints 비었다 |
| 독일 BGR | 광상·채굴지·산출 지역(KOR250 1:25만)·지하자원(BSK1000 1:100만) | `wms/rohstoffe/<판>/` | AGB · GeoNutzV(출처 표시) |
| 포르투갈 LNEG | 광상 1:20만·자력·중력(남부 일부)·방사능 | 같은 서버의 서비스 넷 | copyright "LNEG" 뿐 |

## 왜 이렇게

- **ArcGIS `text/plain` 을 읽게 했다**(`arcwms.fields_plain`) — 독일 원료·포르투갈 광상은 XML·JSON 을 물으면 `InvalidXslTemplate` 이고 text/plain 만
  준다. 한 줄에 `@<레이어 이름> 열;…;열; 값;…` 으로 오고 레이어 이름에 빈칸이 있어, 첫 열은 마지막 낱말만, 머리는 빈칸으로 시작하는 첫 칸
  앞까지로 자른다
- **포르투갈 문을 판으로 갈랐다** — 1:50만 하나에 묶여 있던 문을 `SERVICES`(판 → 서비스)로 넓혔다. 이름은 `lneg:<판>:<번호>` 그대로 쓰고
  판이 주소를 고른다. 지구물리 셋은 누르면 화소 값(`Stretch.PixelValue`)을 단위 붙여 보인다
- **스페인은 상류 레이어 여럿을 `+` 로** — BDMIN 은 레이어가 둘(I·II)로 갈려 있다. `igme.split` 이 `+` 를 쉼표로 바꾸게 했다(BGR 과 같다).
  처음엔 이것을 빠뜨려 상류가 `0+1` 이라는 레이어를 몰라 예외 XML 을 줬다
- 독일은 `geologie` 가 아닌 `rohstoffe` 폴더라 판마다 폴더를 고르게 했다(`bgr.FOLDERS`)
- 프랑스 BD Gîtes 의 갈래·형태·규모는 번호(`c_type`·`c_morpho`)뿐이라 싣지 않았다 — 이름·광종·생산량·잠재량만
- 스페인의 시대(`DEVONICO SUPERIOR`)는 악센트가 빠진 대문자라 `i18n.age_es` 가 잡지 못해 "지질시대 (원문)" 으로 둔다

## 확인

- 사본 DB: 프랑스 Margnac(U · 4300 t), Le Couret(Brt), 스페인 Los Cuchillares(Pirita, Cobre · Lentejonar), Sanlúcar(Grava · Activa continua),
  독일 KOR250 Kiese und Sande(Lagerstätte), BSK1000 Sandstein und Grauwacke, 포르투갈 Ceiroco(Zn, Pb · Filoniano), 자력 −43.1 nT, 중력 37.1 mGal, 방사능 56.4
