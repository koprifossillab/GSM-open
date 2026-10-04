# 한반도 지질도 민판 — 색↔지층 표는 CorelDRAW 원본에 없다

2026-10-05 · `feature/peninsula-legend`(문서만이라 main 에 올렸다) · wetherilli

TODOs 의 "민판의 색↔지층 표를 CorelDRAW 원본(026 §4)에서 뽑아 클릭으로 속성을 읽는다"(028)를 판 세션이 맡겼다. .cdr 을 열지 못하거나 표를
뽑지 못하면 거기까지 잰 것만 적고 끝내라고 했다. **열었지만 표가 없었다.**

## 1. 열었다

- 파일 — NAS `KimSunho/3차원에 섞을 것.cdr`(31.8 MB). 이름이 옛 한글 부호(CP949)로 적혀 있어 셸에서 깨져 보인다. 읽기만 하고 스크래치에 영어 이름으로
  베껴 다뤘다
- CorelDRAW X4 이후의 꼴(ZIP 안에 `content/root.dat`·`content/data/page1.dat` 따위 RIFF)이다. 이 서버에는 libcdr(라이브러리)과 LibreOffice 가 있다 —
  `soffice --headless --convert-to svg` 가 libcdr 로 읽어 SVG(42 MB)를 냈다. uniconvertor·inkscape 는 없다

## 2. 무엇이 들었나

- 닫힌 곡선 면 1 만 3 천 102 개, 채움색 **90 가지**(LibreOffice 가 CMYK 를 RGB 로 옮긴 것). 그림(비트맵) 여섯
- **글이 없다** — SVG 에 `<text>` 가 하나도 없고, 원본의 날것(`page1.dat`)에서도 지층 이름 같은 글자열이 나오지 않는다
- **면의 이름이 없다** — 메타데이터(`META-INF/textinfo.xml`)의 `ObjectNames` 가 비어 있다. 이름은 레이어에만 있다 — 섬·Intrusion·Layer 1–5·
  Stratigraphy·국계·단층선·지질경계선·해안선
- 미리 보기(`previews/page1.png`)에도 범례가 없다 — 반도의 지도뿐이다

그러니 이 파일에서 뽑을 수 있는 것은 "색 90 가지" 까지다. 색이 어느 지층인지는 이 파일이 말하지 않는다.

## 3. 버린 것

- 색을 KIGAM 1:100만·25만 지질도의 범례 색과 맞대 짐작하는 것 — 원본을 그린 이가 색을 따로 골랐을 수 있고(CMYK 손 색), 틀리게 붙인 이름은
  없는 이름보다 나쁘다. 어느 출판 지도를 따라 그렸는지를 알면 그 범례로 붙인다 — 김선호 님께 묻는 줄(026)과 같은 답이다

## 4. 남긴 것

- TODOs 의 줄을 "(사람)" 으로 바꿨다 — 범례(출판 지도)를 알려 주면 색 90 가지에 이름을 붙여, 누른 자리의 민판 픽셀 색으로 지층을 읽는다
- 코드는 바꾸지 않았다. 민판은 연구실 내부용(`LAB_ONLY`)이라 밖에 열 일도 없다
