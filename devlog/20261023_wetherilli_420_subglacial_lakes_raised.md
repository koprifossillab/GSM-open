# 빙저호 목록·RAISED 접지선 — 남극·그린란드 탭에

2026-10-23 · `feature/subglacial-raised` · wetherilli

극지 자료 2 차 조사(docs/극지_자료_후보.md, 순위 6)의 둘이다. 남극 탭에 빙저 수문이 없었고, 최근 빙기의 빙상 가장자리는
북미·유라시아(NADI-1·DATED-1, 104)뿐이었다.

## 무엇을 붙였나

- **빙저호** — `orda:lakes_antarctica`(675 곳)·`orda:lakes_greenland`(64 곳), 레이어군 "빙저호". 점의 색은 종류(활성·안정·적지 않음),
  누르면 이름·종류·찾은 법·넓이·얼음 두께·문헌, 그리고 ORDA 항목 링크. `manage.py fetch_subglacial_lakes` 가 받는다
- **RAISED 접지선** — `raised:20ka`·`15ka`·`10ka`·`5ka`, 남극 탭의 레이어군 "빙상 후퇴 (RAISED)". 연대마다 색 하나, 신뢰도가
  선의 굵기·끊김(측정 굵은 실선·추정 끊긴 선·짐작 점선). 누르면 연대·신뢰도·시나리오(A·B)·논문. `manage.py build_raised` 가 굽는다

둘 다 `<DB 옆>/glacio/` 의 파일만 읽는다(`GSM_GLACIO_DIR`). 화면이 부를 때 상류를 타지 않는다. 운영에서 한 번씩 불러야 레이어가 찬다 —
없으면 레이어 패널에 "아직 받지 않았다 (명령 이름)" 이 뜬다.

## 이용 조건 — 원문

**빙저호** — figshare API(`/v2/articles/18094037`)의 `license`: `{"name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}`.
항목 설명: "Cite these data: Livingstone, S.J., Li, Y., Rutishauser, A. et al. Subglacial lakes and their changing role in a warming climate.
Nat Rev Earth Environ 3, 106–124 (2022)". 출처 줄(`orda.CREDIT`)과 링크(DOI 10.15131/shef.data.18094037.v1)로 지킨다.

**RAISED** — 조건이 흐리다. 확인한 것:
- 논문(Bentley 외 2014, QSR 100, 1–9, DOI 10.1016/j.quascirev.2014.06.025) — White Rose 사본: "This is an open access article under the CC BY
  license (http://creativecommons.org/licenses/by/3.0/)". 그 사본에도 저널 쪽에도 GIS 파일·부록이 없다
- 셰이프는 Quantarctica3 의 `Glaciology/RAISED Paleo Ice Extents/` 뿐이다. 거기 `RAISED_PaleoIceExtents.txt` 는 설명·논문·"Download: 11 May 2017"·
  저자(Bentley) 연락처만 적고 **조건 칸이 없다**. `.qmd` 에도 없다. PANGAEA·UK PDC 에서 원 자료를 찾지 못했다

그래서 붙이기 전에 물었다(clear-conversation 을 거쳐 사람). 답은 **(A) 논문의 CC BY 를 자료에도 걸린다고 보고 붙인다. 출처에 논문(DOI)과
Quantarctica 사본을 밝히고, 정적 판에는 싣지 않는다** 였다. 그래서 출처 줄이 "RAISED Consortium, Bentley et al. 2014 (QSR, CC BY) · Quantarctica"
이고 원본 자료 칸이 "논문 CC BY, Quantarctica 사본" 이라고 적는다. Bentley 에게 물어 조건을 확인하는 길(B)은 버렸다 — 답을 기다리는 동안
멈추게 된다.

## 정적 판

둘 다 싣지 않았다. RAISED 는 사람이 그렇게 정했다. 빙저호는 CC BY 4.0 이라 실을 수 있지만, 정적 판은 점 덩이를 구워 싣는 길
(`static_site.py`)을 따로 타야 하고 이번 일의 몫이 아니다 — TODOs 에 남겼다.

## 왜 이렇게

**빙저호는 엑셀을 받는다, 셰이프가 아니라.** 셰이프의 `Lake_Type` 은 773 가운데 181 만 차 있고(그나마 `Active` 179·`Stable` 2) 찾은 법·문헌 열이
없다. 엑셀의 남극·그린란드 시트는 종류가 거의 다 있다(남극 642/675, 그린란드 63/64). 시트마다 열 차례가 달라(그린란드는 `Name / Location` 이고
`Notes` 가 앞에 낀다) 머리줄의 글로 열을 찾는다. openpyxl 은 제품에 없다 — xlsx 는 zip 안의 XML 이라 표준 라이브러리로 읽었다(`orda.read_xlsx`).
만년설·곡빙하 시트(아이슬란드·알프스·알래스카 등 45 곳)는 극지 탭에 들 자리가 없어 받지 않았다.

**새 문 `orda.py`, RAISED 는 NPI 의 문으로.** figshare(ORDA)는 처음 부르는 상류라 문을 하나 냈다. Quantarctica 는 `media.npolar.no` — NPI 의 서버라
`npolar.quantarctica()` 를 더했다(문은 상류마다 하나). 그리는 쪽 `raised.py` 는 문이 아니다(`REGISTRY` 의 `local`).

**RAISED 를 어디에 — 남극 탭의 연대별 선 레이어로.** 받은 일은 "온 지구의 `ka: true` 틀(icemargins)에 얹을지, 남극 탭에 둘지 판단" 이었다.
- 남극 탭을 골랐다 — 연구실이 남극을 보는 자리가 거기다(극지가 주력, 사람 2026-10-21). 지역 탭에는 시간 축이 없으니 연대마다 레이어 하나로
  두고 함께 켜 견주게 했다. 색을 연대마다 달리한 것도 그래서다
- RAISED 는 **선만** 준다 — 얼음 면이 아니라 접지선이다. icemargins 는 면을 칠하고 가장자리를 긋는 틀이라 얹으려면 그리는 손을 갈라야 한다.
  게다가 RAISED 의 시점은 5 ka 간격이라 icemargins 의 "반 조각 간격 안에서만" 규칙으로는 2.5 ka 씩 넓게 걸리고, 시간 축 띠·캡션·판(RENDERER)까지
  고쳐야 한다. 사람이 "크게 번지는 몫은 TODOs 에 다음으로" 라고 정해 이번에는 하지 않았다 — 같은 `raised.json` 을 읽으면 되게 위경도로 적어 두었다
- 시나리오 A·B 는 둘 다 그린다. 동남극의 몇 곳만 갈리고(A: 얼음이 거의 그대로, B: 더 바깥까지), 한쪽만 그리면 다른 쪽을 믿는 사람이 지도를 못 쓴다.
  어느 시나리오의 선인지는 팝업에 적는다
- 3031 → 위경도는 `geomap.xy3031_to_lonlat`(셰이프의 `Standard_Parallel_1 = -71` 이 3031 과 같다). 꼭짓점 간격이 촘촘해(선 158 개, 3 만 8 천 점)
  화면이 3031 로 다시 옮겨 그려도 굽지 않는다. 파일은 750 KB

## 확인한 것

- 받은 원본(엑셀 184 KB·셰이프 615 KB)으로 굽기: 빙저호 남극 675(활성 140·안정 502·적지 않음 33)·그린란드 64, RAISED 20 ka 44·15 ka 31·10 ka 29·5 ka 54 선
- 상류는 figshare 세 번(목록·zip·엑셀)·Quantarctica 열 번 남짓(설명·폴더 목록·셰이프 조각), 1 초 간격
- 시험 `test_glacio` — 엑셀·셰이프를 손으로 지어 읽기, 받기 흉내(목록 → 엑셀만), 점 레이어·범례·영어, 없을 때 503, 씨앗의 영어. 전체 시험 통과
