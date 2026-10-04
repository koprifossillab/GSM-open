# 정적 판에 콜롬비아 1:50만을 실을 수 있게 — 싣는 것은 사람이 고른다

2026-10-04 · `feature/static-colombia` · wetherilli

남미에서 조건이 분명히 열린 것은 콜롬비아 1:50만(SGC 열린자료, CC BY 4.0) 하나다. 브라질(CC BY-NC)·페루(CC BY-NC-SA)·에콰도르(판매 금지)는
비상업이고, 남미 1:500만은 CGMW 의 지도다. 판 세션이 "정적 판에 실을 수 있게 길만, 기본값에는 넣지 말 것" 을 맡겼다. 실을지는 사용자가
정한다 — 이슈 #153 에 한 줄을 남겼다.

## 1. 고르면 싣는다 — `--with colombia`

`deploy/static_site.py` 에 `OPTIONAL`(이름 → 지역·상류)과 `--with` 를 두었다. `--with colombia` 면 지역 `colombia` 와 상류 `sgc` 가 더해진다.
기본(`REGIONS`·`UPSTREAMS`)은 그대로다.

- `--regions`·`--upstreams` 로 손수 적어도 같은 판이 나온다. 그래도 이름을 둔 것은 **무엇이 "고를 수 있는 것" 인지**를 한 표에 적어 두려는
  것이다 — 다음 사람이 기본값에 슬쩍 더하지 않게
- **같은 지역의 남미 1:500만은 레이어 단위로 뺀다**(`views._static_catalog` 의 `sgc.static_ok`). 정적 판은 지금까지 지역·상류 단위로만
  골랐다. 그런데 콜롬비아 지역의 SGC 에는 열린 판(콜롬비아 1:50만)과 아닌 판(CGMW 1:500만)이 섞여 있다. 열린 판의 목록은 문(`sgc.STATIC_SHEETS`)이 안다
- 정적 판의 출처 표기도 열린 판의 것만 적는다(`sgc.STATIC_ATTRIBUTION`) — 서버 판의 표기는 CGMW 를 함께 적는다

## 2. 브라우저가 SGC 를 곧장 부른다

SGC 의 ArcGIS WMS 는 Origin 을 되돌려 준다(`Access-Control-Allow-Origin: https://koprifossillab.github.io`). 2026-10-04 에 그 Origin 으로
GetMap(1.3.0·3857, 1.7 초)과 GetFeatureInfo(`application/geo+json`, 기하 없음)를 한 번씩 받아 봤다.

- `static-kinds.js` 의 `wmsKind` 가 이미 극지 WMS(EMODnet·KPDC)를 곧장 부른다. 거기에 둘을 넓혔다 — 주소를 레이어마다 고르는 함수로도
  받고(SGC 는 판마다 서비스 주소가 다르다), 속성의 꼴을 넘길 수 있게(ArcGIS 는 `application/geo+json`). `KINDS.sgc` 는 그 위의 몇 줄이다
- 주소·판·열 이름은 서버의 문에서 떠 싣는다(`static_tables.tables()["sgc"]`) — 표를 JS 에 또 적지 않는다(161 의 원칙). 표에는 열린 판만
  실린다
- 속성 손질(`sgcFriendly`)은 `sgc.friendly` 의 콜롬비아 갈래다 — 값은 에스파냐어 그대로, `Null` 은 뺀다. 남미 판의 시대 옮기기는 정적
  판에 그 판이 없어 옮기지 않았다. 두 벌이 갈라지지 않게 `test_static_kinds` 의 node 대조에 더했다

## 3. 확인

- `--with colombia` 로 구운 판의 카탈로그에 `sgc:co:` 다섯(연대층서 단위·단층·습곡·화산·진흙 화산)만 서고 `sgc:sa:` 는 없다.
  기본으로 구우면 SGC 는 하나도 없다
- 구운 판을 띄워 콜롬비아 탭을 열고 보고타 둘레를 눌렀다 — 브라우저가 SGC 를 곧장 불러 타일과 속성이 200 이었고, 팝업에 기호·암석·
  지질시대(`Ordovícico Inferior` 따위)가 뜬다. 페이지 오류는 없었다
- 시험 `test_static_colombia` — 레이어 단위 거르기, 기본값에 없음, 표에는 열린 판만. `test_static_kinds` — `KINDS.sgc`, 주소를 박지 않음,
  JS·파이썬 손질 대조
