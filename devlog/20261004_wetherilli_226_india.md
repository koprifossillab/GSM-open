# 인도 — GSI 1:200만, 그림은 BGS 의 OneGeology WMS·속성은 GSI 피처 서비스

2026-10-04 · `feature/india` · wetherilli

`docs/아시아_오세아니아_지질도.md` 의 추천 순서 다섯째. 판 세션은 "Bhukosh 가 막혔으면 실측만 적고 넘어가라" 했는데, 열린 길이 둘 있어 붙였다.

## 1. 길을 엮은 까닭

- **GSI 의 지도 창(Bhukosh)은 나라 밖에서 닿지 않는다** — 이 서버에서 시간 초과, 바깥에서 연결 거부. NGDR 는 로그인이다. 1:5만은 거기 있다
- **그림은 BGS 가 OneGeology 로 여는 WMS**(`ogc.bgs.ac.uk/cgi-bin/BGS_GSI_Geology/wms`, MapServer)다. 3857 로 그리고, 조건이 Capabilities 에
  "Free viewing" 으로 적혀 있다. 그런데 GetFeatureInfo 는 `Feature 3712:` 만 주고 열이 비었다
- **속성은 GSI 가 ArcGIS Online 에 직접 올린 피처 서비스**(`Geology_2M_WFL1/FeatureServer/7`, 소유 `gisadmin.gsi`, 공개)에 묻는다. 그림이
  없는(피처 서비스) 대신 열(INDEX_·AGE·SUPERGROUP·GROUP_)이 있다. 누른 화소를 3857 점으로 바꿔 `query` 에 묻고 모양은 받지 않는다
- 상류 하나에 문 하나라는 규칙대로, 두 호스트를 `gsiindia.py` 한 문에 두었다 — 자료의 주인은 GSI 하나이고 BGS 는 그 판을 걸어 둔 곳이다
- **버린 것:** 피처 서비스의 면 4 555 개를 통째로 받아 우리가 칠하기(`kind: points`·`render: image`). 하루 품이고, BGS 가 그려 주는 그림이 있다
- **버린 것:** Esri India Living Atlas 의 같은 자료(MapServer, export·identify 가 된다). Esri India 가 다시 내는 판이라 출처가 한 겹 더 붙는다.
  GSI 가 직접 올린 것이 열려 있으니 그쪽을 쓴다

## 2. 범례

두지 않는다. BGS 의 범례 그림은 칸 이름이 1–98 번호뿐이다. 피처 서비스의 칠하기 규칙(`drawingInfo`, 523 칸)으로 목록을 뜰 수 있지만 BGS
그림의 색과 같은지 확인하지 못했다 — 다르면 범례가 지도를 거짓으로 읽게 한다. 누르면 단위가 뜬다.

## 3. 시대

`AGE` 가 영국식 대문자 ICS 다(`LATE CRETACEOUS - PALAEOCENE`, `MESOPROTEROZOIC TO NEOPROTEROZOIC`). `TO` 를 `–` 로 바꾸면 `i18n.age_ko` 가
옮긴다. 상류의 시대 값 71 가지를 한 번에 모아(`returnDistinctValues`) 보니 못 옮기는 것이 오탈자 하나(`NEOPROTEOZOIC`)와 "Unmapped" 둘이었다 —
오탈자는 고쳐 읽고, "Unmapped" 는 시대로 보이지 않는다.

## 4. 탭

- 지역 `india`(3857). 묶음에는 넣지 않았다 — 이웃(동남아·중동)이 아직 없다. 동아시아에 넣기에는 멀다
- 3D 는 BGS WMS 가 3857 로 그려 `MAP3D_WMS` 에 넣었다
- 색은 사프란 — 바탕을 데칸 현무암의 적갈로 두어 아프리카(황토)·몽골(주황)과 가른다
- 마이그레이션은 `0036_region_india` — #209 의 0035 뒤

## 5. 조건

BGS 의 WMS 는 "Free viewing". GSI 피처 서비스는 licenseInfo 가 비어 있고, GSI 의 이용 조건은 Bhukosh 가 열리지 않아 읽지 못했다. 정적 판에
싣지 않았다(둘 다 CORS 는 `*`). 밖에 열기 전에 사람이 읽는다(TODOs).
