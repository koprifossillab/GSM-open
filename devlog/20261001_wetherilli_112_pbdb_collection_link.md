# 온 지구 — PBDB 산지 링크를 displayCollectionDetails 로

2026-10-01 · `fix/pbdb-collection-link` · wetherilli

사람이 "PBDB 로 바로 가는 링크가 안 굴러가네" 라고 했다. 화석 산지(098)를 누르면 뜨는 링크가
`classic/basicCollectionSearch?collection_no=…` 였는데, 2026-10-01 에 이 주소가 **403 Forbidden** 을 준다 —
`GSM/0.1` 로도, 브라우저 User-Agent 로도 같다. 우리 쪽이 막힌 것이 아니라 PBDB 가 그 쪽을 닫은 것이다.

같은 산지 번호로 `classic/displayCollectionDetails?collection_no=…` 는 200 이고 그 산지의 쪽(산지 이름·지층·화석
목록)을 그대로 낸다. 그래서 `pbdb.collection_url()` 한 줄만 바꿨다.

## 버린 것

- **data1.2 의 `colls/single.json`** — 돌기는 하지만 사람이 읽는 쪽이 아니다. 링크는 사람이 누르는 것이다
- **새 PBDB 앱(`/navigator/` 따위)** — 산지 번호로 곧장 여는 길이 문서로 정해져 있지 않다. classic 이 또 닫히면
  그때 본다

`collection_url` 의 꼴을 시험이 지킨다(`test_fossils.Door`). 상류가 주소를 다시 바꾸면 고칠 자리는 이 함수 하나다.
