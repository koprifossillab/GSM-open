# 페루 — INGEMMET 지화학 지도첩·산업 광물

2026-10-05 · `feature/peru-more` · wetherilli

#267(wetherilli 277)에서 TODOs 로 남긴 둘을 같은 길(`ingemmet.RESOURCES` — 다른 서비스의 `export` 를 타일 칸으로)에 얹었다.

| 레이어 | 서비스 | 누르면 |
|---|---|---|
| 지화학 분산·이상 — 금·은·구리·몰리브데넘·납·아연·비소·수은·코발트·니켈·크로뮴 | `SERV_ATLAS_GEOQUIMICO` (원소마다 분산도 래스터 + 주요 이상점) | 이상점(이름·광종·함량·광화대) |
| 산업 광물·암석 산지 | `SERV_ROCAS_MINERALES_INDUSTRIALES` 0 | 광종·갈래·곳·보고서 링크 |
| 리튬 산지 | 같은 서비스 1 | 광종·리튬 함량(ppm) |

## 왜 이렇게

- **원소마다 레이어 하나** — 분산도와 이상점을 한 장에 함께 그린다(`show: 분산,이상`). 누르면 이상점 레이어에 묻는다 — 그래서 `RESOURCES` 에
  그리는 레이어와 따로 `layer`(묻는 레이어)를 둘 수 있게 했다. 분산도는 래스터라 묻지 않는다
- 원소 결합 분산도(Sb-Bi-Cu-W 따위 넷)는 원소별 열하나와 겹쳐 뺐다
- 광업 권리(같은 서비스의 면, `SERV_CATASTRO_MINERO`)는 지질과 멀어 싣지 않는다 — 판 세션이 정했다
- 지도첩 서비스는 원본이 32718(UTM 18S)이지만 `bboxSR`·`imageSR` 3857 로 물으면 상류가 옮겨 그린다(페루 전체 2.1–2.4 초)
- 비상업(CC BY-NC-SA 4.0)이라 정적 판에 싣지 않는다 — 페루 상류 전체가 그렇다

## 확인

- 사본 DB: 구리 이상점 Pupahuay(Cu 518 · XVII · Junín / Yauli), 산업 광물 Feldespato(Arequipa · 보고서 링크), 리튬 Fundición(219 ppm). 타일 200
