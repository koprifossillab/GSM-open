# 온 지구 — 홀로세 화산, 스미스소니언 GVP 1 214 곳

2026-10-02 · `feature/earth-volcanoes` · wetherilli

[docs/새_상류_후보.md](../docs/새_상류_후보.md) §1 의 점 레이어 셋(화산·지진·Neotoma) 가운데 첫째다. Global Volcanism Program 의
Volcanoes of the World 에서 홀로세 화산을 받아 온 지구에 세모로 찍고, 누르면 그 화산을 읽는다.

## 1. 이용 조건 — 인용하면 쓸 수 있다

- GVP 의 이용 조건 쪽(`volcano.si.edu/gvp_termsofuse.cfm`)은 우리 서버에서 열리지 않는다 — 스미스소니언의 브라우저 확인
  화면(403)이 막는다. 검색에 걸린 본문으로 읽었다
  - 스미스소니언은 **개인·교육·비상업 이용**을 허락한다. 인쇄물처럼 지은이와 출처를 밝히고, SI 웹사이트를 출처로 링크한다
  - Volcanoes of the World 는 **미국 정부 직원이 만든 것**이고, 자료마다 근거 문헌을 단다
  - 인용 꼴은 `Global Volcanism Program, 2026. [Database] Volcanoes of the World (v. 5.4.0; 7 Aug 2026). Distributed by
    Smithsonian Institution, compiled by Venzke, E. https://doi.org/10.5479/si.GVP.VOTW5-2026.5.4.`
- 우리는 비상업 연구용 뷰어이고 출처를 카드·팝업에 적는다. **연구실 내부용이 아니다** — `views.LAB_ONLY` 에 넣지 않았다
- **사진은 담지 않는다.** WFS 가 `Primary_Photo_Link`·`Credit` 을 주지만 사진마다 찍은 사람이 따로라(조건이 다르다)
  팝업에 싣지 않고, 화산 쪽(`volcano.cfm?vn=`)으로 가는 링크만 건다
- 밖에 열 때 다시 볼 것: 지금 우리가 읽은 것은 스미스소니언 전체의 조건이다. GVP 쪽이 열리면 다시 읽는다

## 2. 새 문 `gvp.py`, 그리고 모아 두기

- WFS(`webservices.volcano.si.edu/geoserver/GVP-VOTW/ows`)의 `Smithsonian_VOTW_Holocene_Volcanoes` 를 GeoJSON 으로
  **한 번** 받는다(2.4 MB, 1 214 곳, 열쇠 없음). PBDB 처럼 `manage.py fetch_gvp` 가 받아 `<EARTH_DIR>/gvp_volcanoes.json`
  에 줄여 적는다(1.3 MB). 화면이 부를 때 상류를 타지 않는다
- sqlite 로 굽지 않았다. 1 200 곳은 파일을 읽어 메모리에 두고 다 훑어도 타일 한 장에 몇 ms 다. PBDB(27 만)의 R*Tree 틀을
  그대로 옮기면 손만 간다
- 받은 날(`fetched`)이 타일 캐시의 열쇠에 든다 — 다시 받으면 새로 그린다. GVP 는 1 년에 한두 번 판을 올린다
- 그때그때 WFS 에 범위를 묻는 길은 버렸다. 문서에 이용 한도가 없고, 작아서 통째로 두는 편이 상류에 덜 묻는다

## 3. 오늘의 레이어 — `always` 가 아니다

- 판 세션은 PBDB 의 `always` 틀을 따르라 했다. 틀(경위도 타일, 누르면 둘레 다섯, 카드·범례)은 따랐지만 **보이는 연대는
  오늘의 레이어**로 두었다 — 1 Ma 부터는 꺼진다. 홀로세(1 만 1 700 년) 화산을 판을 돌린 옛 지구에 옮겨 찍으면 그때 없던
  화산이 선다. 화석 산지는 산지마다 연대가 있어 옛 지구에 옮길 뜻이 있지만, 화산 목록은 "지금 살아 있는 화산" 이다
- 1 Ma 안쪽(최근 빙기의 ka 연대)에는 그대로 뜬다 — 오늘의 지구에 얹는 다른 레이어와 같다
- **플라이스토세 화산**(`Smithsonian_VOTW_Pleistocene_Volcanoes`)도 WFS 에 있다. 이번에는 넣지 않았다 — 홀로세와 섞으면 세모의
  색(마지막 분화)이 뜻을 잃는다. 넣을 때는 따로 레이어로

## 4. 그리는 법

- 세모, 색은 **마지막 분화**의 다섯 칸 — 1900 년부터(438)·1500–1899(140)·서기 1–1499(100)·기원전(170)·기록 없음(366).
  빨강에서 노랑으로 식어 가고, 기록이 없는 것은 회색이다. 오래된 것을 먼저 찍어 최근 것이 위에 온다
- 범례는 서버가 `then_data` 로 함께 내린다(지각 두께와 같은 꼴) — 따로 묻지 않는다
- 누르면 화산이 먼저다. 둘레(8 칸)에 화산이 없으면 화석 산지, 그다음 그 자리의 지질 단위 — 점이 땅보다 앞이라는 순서는 098 과
  같다
- 레이어를 처음 한 번 켜 두지 않았다(화석·해안선과 다르다). 지질 단위 위에 1 200 개 세모가 처음부터 서면 지질도를 가린다

## 운영

```
docker compose exec web python manage.py fetch_gvp      # 몇 초. 판이 오르면 다시
```

파일이 없으면 레이어가 목록에 서지 않는다.
