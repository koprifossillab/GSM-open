# 퀘벡 광물 산지(gîte) — 같은 WMS 의 무리 레이어 아래에 있었다

2026-10-05 · `feature/quebec-gites` · wetherilli

판 세션이 맡긴 일이다 — TODOs "캐나다 주 광물" 의 퀘벡: wetherilli 288 이 "광물 산지(gîte)는 WMS 에 없다, SIGÉOM 의 다른 서비스를 찾을 것" 으로 남겼다.
다른 서비스를 찾기 전에 쓰고 있는 WMS(`servicesvectoriels.atlas.gouv.qc.ca/IDS_SGM_WMS`)의 Capabilities(580 KB)를 다시 훑었더니 무리 레이어
**`Indices_gites_mines_carrieres`(Indices, gîtes, mines et carrières)** 아래에 있었다. 288 은 이름에 `gite` 가 든 레이어를 찾았는데, 레이어 이름은
`SGM:Substances_metalliques` 꼴이고 `gîte` 는 무리의 제목에만 있었다.

## 붙인 것

무리 아래는 갈래 셋 — 금속(원소 서른다섯)·비금속(광물 서른)·석재(암석 스물 남짓) — 이고, 갈래마다 "모두" 레이어가 있다. 그 셋을 붙였다.

| 레이어 | 상류 | 누르면 |
|---|---|---|
| 금속 광물 산지 | `SGM:Substances_metalliques` | 이름·주 광종·상태·발견 연도·모암·발견 내력, SIGÉOM 상세 링크 |
| 비금속 광물 산지 | `SGM:Substances_non_metalliques` | 이름·광물·상태 |
| 석재·골재 산지 | `SGM:Pierre_architecturale_industrielle` | 이름·산물·암석·상태·쓰임 |

- 문은 그대로 `sigeom.py` — 표에 줄 셋, 열 이름 표(`FRIENDLY`)에 갈래마다 다른 열을 더했다. 금속의 상세는 `<a href="…">` 로 오는 열에서 주소만 뽑아 링크로 낸다(https 만)
- 원소·광물마다 레이어를 두지 않았다 — 예순 남짓이 패널을 덮는다. 색은 상류가 상태마다 칠한다(범례 없음, 퀘벡의 다른 레이어처럼)
- 줌 7 부터 — 넓게 보면 금속 산지가 아비티비를 덮는다. Capabilities 에 축척 끝은 없다
- 조건은 다른 SIGÉOM 레이어와 같다 — Licence du gouvernement ouvert – Québec(CC BY 4.0)

## 확인

`verify_layers` 의 길로 셋 모두 그림. 발도르 둘레를 누르면 "New Harricana · Or · Indice travaillé · 1920" 과 SIGÉOM 상세 링크가 온다.
