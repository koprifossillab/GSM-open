# 극지 배경 — PGC 음영의 다른 그리는 법 둘

2026-09-30 · `feature/pgc-hillshade-variants` · wetherilli

TODOs "노는 자료" 의 한 줄이다. ArcticDEM·REMA 음영은 PGC 의 ImageServer 에서 `Hillshade Gray` 하나만 받았다. 같은
서비스가 그리는 법(raster function)을 열한 가지 준다. 2026-09-30 에 둘 다 목록을 보고 한 장씩 그려 받았다 — 한 장에
1–1.5 초, `Hillshade Gray` 와 같다.

| 넣은 것 | 까닭 |
|---|---|
| `Hillshade Multidirectional` — "음영 (여러 방향)" | 한 방향(북서) 빛은 그 방향으로 뻗은 선구조를 지운다. 여러 방향에서 비추면 그늘에 묻힌 사면이 산다 |
| `Hillshade Elevation Tinted` — "높이 색 음영" | 빙상·산지·해안 평지를 색으로 가른다. 지질도를 반쯤 비치게 겹칠 때 높이를 함께 읽는다 |

북극 넷(그린란드·얀마옌·스발바르·북극해)과 남극에 둘씩, 배경이 넷 는다. `pgcHillshade` 에 그리는 법 이름을 넘기는
인자를 하나 더했을 뿐이다.

**넣지 않은 것.** `Slope Map`·`Aspect Map`·`Contour 25` 도 그려진다. 이것들은 배경보다 **지질도 위에 겹치는 레이어**로
쓸 것이다. 배경은 늘 맨 밑에 깔려 지질도를 덮으면 보이지 않는다. 레이어로 겹치려면 브라우저가 곧장 부르는 배경 길을
못 쓰고 `elevation.py` 에 문을 내야 한다. TODOs 의 "PGC 경사·등고선 레이어 — 하루" 가 그 일이다.

브라우저로 그려 보지는 않았다. 부르는 주소와 인자는 기존 `Hillshade Gray` 와 이름 하나만 다르다.
