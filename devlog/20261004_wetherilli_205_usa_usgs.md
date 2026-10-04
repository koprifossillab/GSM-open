# 미국 — USGS SGMC(본토)와 알래스카 SIM 3340 으로 미국 탭

2026-10-04 · `feature/usa-mexico` · wetherilli

판 세션이 북미의 미국·멕시코를 맡겼다. 미국을 이 PR 로, 멕시코는 다음 PR(wetherilli 206)로 나눈다. 후보와 첫 실측은
[docs/다른_대륙_지질도.md](../docs/다른_대륙_지질도.md) 의 "미국" 절이다.

## 1. 쟀다 (2026-10-04)

- **SGMC**(`mrdata.usgs.gov/services/sgmc2`) — 3857 512² 가 덴버 둘레 0.9 초, 본토 넓은 줌 1.0 초. 빠르다(MapCache 앞단)
- **SGMC 의 GetFeatureInfo 는 막혀 있다** — 그래서 WFS 1.0(`services/wfs/sgmc2`, `typeName=Lithology`)에 작은 경위도 네모로 묻는다.
  그냥 물으면 기하가 붙어 66 KB, `PROPERTYNAME` 을 붙이면 1.3 KB 다. 열은 주·원래 기호·대분류 암상·단위 설명 쪽·원도 주소뿐이다 —
  **단위 이름·시대 열이 없다.** 단위 설명 쪽을 링크로 붙여 갈음한다
- **알래스카**(`services/sim3340`) — 3857 512² 가 4.5 초(184 KB). GetFeatureInfo 가 된다. GML 은 기하가 붙어 226 KB 지만
  **`text/plain` 이면 395 B** 다(이름·시대 범위·단위 쪽). 알래스카에는 WFS 가 없다(`wfs/sim3340` 은 map 파일이 없다는 오류)
- 둘 다 CORS `*`, 열쇠 없음, AccessConstraints none. USGS 자료라 **공공 도메인**이다

## 2. 문 — `mrdata.py`

지진 목록의 `usgs.py`(FDSN, earthquake.usgs.gov)와 같은 기관이지만 서버도, 하는 일도, 고칠 자리도 다르다. 그래서 서버 이름으로 문을
따로 두었다. 레이어명은 `mrdata:<서비스>:<레이어>` — 본토 단위·구조선, 알래스카 단위·단층 넷이다.

- 화면은 다른 WMS 처럼 `/featureinfo/` 로 묻는다. 문이 레이어를 보고 갈라 묻는다 — 본토는 누른 자리(WMS 의 범위·크기·I·J 에서 경위도로
  셈한다, `click_lonlat`) 둘레 2 픽셀 네모로 WFS, 알래스카는 WMS `text/plain`
- GML 은 정규식으로 `<ms:열>값</ms:열>` 만 읽는다 — 기하를 받지 않았으니 XML 나무를 세울 까닭이 없고, 정적 판의 JS 도 같은 읽기를 쓴다
- **범례는 없다**(`noLegend`) — SGMC 는 단위가 주마다 수천이고 GetLegendGraphic 이 501 이다. 팝업의 "단위 설명" 링크가 그 단위의 쪽을 연다
- 알래스카의 시대(`age_range`)는 ICS 영문이라 한국어판이면 `i18n.age_ko` 로 옮긴다. 본토의 값은 영어 그대로 둔다

## 3. 지역 — 미국 탭, 북미 묶음은 나중에

나라 탭 `usa`(마이그레이션 0027). 3857 이다. **알래스카는 3857 에서 부푼다** — 판 세션은 캐나다(gsm-57)가 고르는 투영에 맞추라고 했는데,
캐나다는 아직 커밋이 없다. 그래서 지금은 3857 그대로 두고, 캐나다가 들어오면 `north_america` 묶음을 세우며 알래스카를 맞춘다(TODOs).
묶음은 품은 지역이 둘 이상이어야 뜻이 있다(188).

빛깔은 모뉴먼트밸리의 붉은 사암을 사막의 밤하늘 바탕에. 3D 허용 목록·prewarm(`PROJECTED`)에도 더했다.

## 4. 정적 판 — 고르면 싣는다

공공 도메인이고 CORS `*` 라 정적 판에 실을 수 있다. 콜롬비아(201)처럼 `static_site.py` 의 `OPTIONAL` 에 `usa` 를 두고 기본값에는 넣지
않았다(이슈 #153 에 한 줄). `static-kinds.js` 의 `KINDS.mrdata` 가 브라우저에서 같은 일을 한다 — 본토는 WFS 를 곧장 불러 GML 을 읽고,
알래스카는 GEUS 와 같은 MapServer `text/plain` 읽기(`parsePlain`)를 쓴다. 손질(`usgsFriendly`)과 GML 읽기(`usgsGml`)는 `test_static_kinds`
의 node 대조에 더했다.

## 5. 확인

- DB 사본으로 미국 탭을 열었다. 본토 타일이 200, 페이지 오류 없음. 덴버를 누르면 "CO · TKda · Sedimentary, clastic" 과 단위 설명·원도
  링크, 앵커리지를 누르면 "Unconsolidated surficial deposits, undivided · Qs · 제4기" 가 뜬다
- 넓은 줌에서 몇몇 타일이 네모나게 옅다 — 상류 MapCache 가 그 줌에 구운 그림이 그렇다. 가까이 가면 사라진다
- `--with usa` 로 정적 판을 구워 띄웠다 — 브라우저가 mrdata 를 곧장 불러 타일과 WFS 속성(캔자스의 단위들)이 뜨고 오류가 없다
- 시험 `test_mrdata` — GML·text/plain 읽기, 손질, 누른 자리의 셈, 본토는 WFS(기하 없이, 작은 네모)·알래스카는 text/plain, 정적 판 고르기
