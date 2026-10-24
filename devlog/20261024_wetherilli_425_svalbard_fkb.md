# 스발바르 — NPI 정주지 상세도(FKB)를 지형도 위에 얹은 배경

2026-10-24 · `feature/king-george-kgis` · wetherilli

다산기지(뉘올레순) 둘레를 건물·길까지 보이는 배경이 없었다. 지형도(`npi_topo`)는 줌을 올려도 건물이 없다.
후보는 `docs/극지_자료_후보.md` "2 차 조사" 의 1 순위.

## 상류와 조건

`https://geodata.npolar.no/arcgis/rest/services/Basisdata/FKB_Svalbard_WMTS_3857/MapServer` — 서비스 설명 그대로(2026-10-24 다시 읽었다)
"Detaljkartdata over bosetningene på Svalbard. … Dataene for Longyearbyen-området er deleiet av Longyearbyen lokalstyre, Norsk Polarinstitutt,
Store Norske, Sysselmannen og Telenor. For Ny-Ålesund-området er alle data eiet av Norsk Polarinstitutt. Tjenesten er tilgjengelig under
CC-BY-lisensen. Deleierne skal krediteres ved bruk av kart fra de ulike bosetningsområdene."
그래서 출처 줄에 롱위에아르뷔엔의 공동 소유자를 함께 적었다(Sysselmannen 은 지금 이름 Sysselmesteren 으로). `Basisdata/` 다 — `Basisdata_Intern/` 이 아니다(P01).

**정사사진(`NP_Ortofoto_Svalbard_WMTS_3857`)은 하지 않았다** — 조건 칸이 "Norsk Polarinstitutt" 뿐이고 `exportTilesAllowed=false` 다. REMA 때처럼 사람이 정한다.

## 무엇을 골랐나

- **3857 판을 쓴다.** 같은 자료의 25833 판도 있다 — 기존 NPI 배경과 격자가 같고 줌 17 이 0.17 m 로 훨씬 곱다(3857 은 1.19 m).
  그래도 3857 을 고른 것은 오프라인 묶음이 3857 z/x/y 를 그대로 담기 때문이다(조사 문서의 까닭). 뉘올레순 z15·z17 을 받아 보니 건물 하나하나가
  보였다 — 현장 배경으로 모자라지 않다. 25833 이 아쉬우면 `npiTiles` 를 그대로 쓰면 된다(격자가 같다)
- **배경 하나 = 지형도 + FKB.** FKB 는 정주지 둘레(서비스 `fullExtent`, 3857 로 동서 약 540 km × 남북 510 km 의 네모)에만 그림이 있고 그 안에서도
  그릴 것이 없는 칸은 404 다. 그것만 고르면 거의 빈 지도라, 남극의 "세종·장보고 기지 위성"(REMA 음영 + VWorld)처럼 지형도 위에 얹었다
- **서버 캐시 길**(`basemaps.py`) — CC BY 라 담는다. 문은 같은 NPI 서버라 새로 내지 않았고 주소(`npi/<서비스>/z/y/x`)도 같다.
  다른 것은 둘이다 — 칸이 `fullExtent` 밖이면 묻지 않고(`knows_fkb_tile`), 상류의 404 는 "그릴 것이 없다" 라 투명한 칸을 담는다(`_get(empty_404=True)`).
  404 를 오류로 두면 빈 칸을 볼 때마다 다시 묻고 `upstream_stats` 에 실패로 쌓인다
- 정적 판은 곧장 부른다 — CORS 가 Origin 을 되비춘다(2026-10-24 `koprifossillab.github.io` 로 확인). 2 차 조사 때 "CORS 머리가 없었다" 는 Origin 없이 물은 것이다

## 하지 않은 것

- 오프라인 묶음에 넣는 것 — NPI 배경은 아직 묶음 소스가 아니다(`offlineWrap` 을 타지 않는다). 다산기지 묶음을 구울 때 소스를 더한다
- 북극 묶음 탭에 두는 것 — 지형도·위성처럼 스발바르 탭에만 둔다

## 운영에서 할 일

없다 — 파일을 받지 않는다. 판이 오르면 스발바르 탭 배경에 "스발바르 정주지 상세도 (NPI FKB)" 가 뜬다.
