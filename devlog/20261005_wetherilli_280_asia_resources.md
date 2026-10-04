# 아시아 — 인도네시아·필리핀·태국·사우디·몽골의 광물

2026-10-05 · `feature/asia-resources` · wetherilli

미국·호주·남미·북유럽·페루와 같은 꼴로 아시아의 같은 서버들을 쟀다(서비스 목록을 1 초 간격으로 훑고 후보만 그려 보았다).

| 나라 | 올린 것 | 길 |
|---|---|---|
| 인도네시아 ESDM | 금속 3 214·비금속 6 738 광물 잠재력 | `BGD_TU` 폴더 — **WMS 가 없어(400)** REST export·identify |
| 필리핀 MGB | 금속 655·비금속 52 광물 자원 | 공개 폴더의 다른 서비스 둘, WMS |
| 태국 DMR | 광물 산지 5 597·핵심 광물 249 | `MINERAL` 폴더, WMS(원본 32647) |
| 사우디 SGS | 광물 산지 MODS 5 751·광화대 16 | `Geosciences/MODS`·`Geology/Mineralization_Belts`, WMS |
| 몽골 MRIS | 희토류 광상 6·광화 지점 280·산지 85 | `Atlas/12_REE` — WMS 가 없어 REST |

## 왜 이렇게

- **문을 새로 내지 않았다.** 모두 이미 있는 문의 서버다. WMS 가 있는 서비스는 `arcwms.Door` 를 서비스마다 하나씩 두고 이름으로 고른다
  (필리핀·태국은 그 문이 원래 `arcwms` 이고, 사우디는 제 WMS 길 옆에 둔다)
- **WMS 가 없는 서비스**(인도네시아·몽골)를 위해 `arcwms` 에 WMS 꼴 변수 → REST `export`·`identify` 변수 옮기기를 더했다. 호주 퀸즐랜드
  (`austates.gsq_*`)가 문 안에 따로 가진 셈과 같다 — 둘이 되어 공용으로 뺐다. `arcwms` 는 여전히 `requests` 를 쓰지 않는다
- 태국 산지의 속성은 geojson 에서 열 이름이 태국어 별칭(`ชื่อทางการค้า(ภาษาอังกฤษ)`)으로 오고, 핵심 광물은 필드 이름(`COMNAME_E`)으로 온다 — 둘 다 읽는다
- 범례: WMS 가 있는 것은 상류 그림 그대로, 인도네시아는 광종이 수십 가지라 두지 않고 누르면 뜬다

## 버린 것

- 말레이시아 — MyGEMS 의 `rest/services` 가 허브 쪽으로 넘어가 목록을 볼 수 없다. 아는 폴더(`Demarcation`)엔 암상뿐이다
- 인도 — Bhukosh 가 나라 밖에서 닿지 않는다(226 과 같다)
- 몽골 `Atlas/AtlasPoints` 의 광상 레이어 넷(금속·비금속·연료·전략)은 **모두 같은 우물 자료**를 돌려준다(3 559 곳, `Anion_content`) — 상류의 잘못이라 뺐다
- 태국 지구물리 탐사 지점·사우디 지구물리 사업 범위·몽골 항공 지구물리(조사 구역 면) — 값이 아니라 범위뿐이다

조건은 다섯 곳 모두 적혀 있지 않다 — 정적 판에 싣지 않고 TODOs 에 남겼다.

## 확인

- 사본 DB: 인도네시아 "Besi Laterit Mengandung Sari"(광종·갈래·조사 단계), 태국 산지 Limestone·핵심 광물 Gold, 사우디 JABAL SAYID(Copper · Very high),
  광화대 Al Maraysia(Gold Belt), 몽골 Mushugai(Carbonatite), 필리핀 Cu,Au · Prospect. 타일·범례 200
