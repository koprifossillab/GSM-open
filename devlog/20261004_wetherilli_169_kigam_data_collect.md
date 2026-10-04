# KIGAM `/openapi/data` 모으기 — 문과 받기 명령, 지도는 아직

2026-10-02~04 · `feature/kigam-data` · wetherilli

지오빅데이터 오픈플랫폼의 자료 API(`/openapi/data`)를 모은다. 시료·분석(GEO2) 2 501·지질자원주제도(GEO3) 856·조사·탐사(GEO1) 93,
모두 3 450 건(2026-10-02). **무엇을 지도에 올릴지는 이번 PR 에 넣지 않았다** — 이슈 #153 에 유보로 올라 있다. 이번 몫은 결정
없이 되는 것: 문(`kigam.py`)·받기 명령·모아 두는 꼴·시험.

## 쟀다 (2026-10-02)

- 목록 `GET /openapi/data?key=&page=&size=` — `page` 는 0 부터, `size` 는 100 까지(200 은 500), `collection=` 거르기는 먹지 않는다
  (TODOs 의 [실측] 그대로). 목록에는 좌표가 없다
- 상세 `GET /openapi/data/<id>?key=` — `metadata.위치정보.좌표` 에 WKT. **`POINT (경도 위도)`** — 축은 경도 먼저(표본 열여덟이
  한국 안에 든다). 주제도는 `POLYGON`. 좌표 없이 `국가·도,광역시·시군구·동,면` 만 적힌 옛 소장 표본이 있고, 나라가 미국인 것도 있다.
  "남한전체" 처럼 `지역명` 만 있는 주제도도 있다
- 이용 조건은 자료마다 — CC BY-NC 2 421·CC BY-NC-ND 1 021·CC BY-ND 7·CC BY-NC-SA 1. DOI 가 2 180 건에 있다
- 사람이 읽는 쪽은 `data.kigam.re.kr/data/<id>` — DOI 도 그리로 넘긴다
- 상세 한 건에 0.3 초 남짓. 1 초 쉬고 하나씩이라 한 건에 1.3 초, 처음 다 받는 데 한 시간 20 분 남짓

## 문 — `kigam.py` 를 넓혔다

- 인증키가 필요한 길이라 KIGAM 의 문에 둔다(`data_list`·`data_detail`). 키는 `params` 로 붙이고 로그는 `redact` 를 탄다 —
  시험이 로그에 키가 없는 것을 본다. 차단 조짐이면(`usage.paused`) 묻지 않는다
- 자료 번호는 UUID 꼴만 받는다 — 주소에 그대로 들어가서다

## 모으기 — `kigamdata.py` · `manage.py fetch_kigam_data`

- `<KIGAM_DATA_DIR>/data.json`(기본 `<DB 옆>/kigam_data/`)에 자료마다 줄인 상세(제목·모음·이용 조건·DOI·`lastModified`·메타데이터·
  파일 수). 판 이력(`series`)과 파일 목록은 덜어 낸다
- 다음부터는 목록의 `lastModified` 가 바뀐 것과 새 것만 상세를 받는다. 목록에서 빠진 것은 지운다
- **50 건마다 적는다** — 멈추거나 차단 조짐으로 그쳐도 받은 것은 남고, 다시 부르면 이어 간다. 1 초보다 잦게는 묻지 않는다
  (`--pause` 가 1 밑이면 거절) — 호출 제한을 재려고 두드리지 않는다(CLAUDE.md "받아온 것의 순위")
- `--places` 는 따로 부른다 — 행정구역만 적힌 자료의 가운데를 VWorld 로 찾아 `places.json` 에 담는다(끝 마디를 떼며 다시,
  못 찾은 것도 담아 두 번 묻지 않는다). 지도에 올릴 때나 쓸모라 기본으로는 부르지 않는다

## 지도 — 유보

- 이 세션에서 사용자가 한 번 고른 것이 있다(10-02): 좌표 있는 시료·분석 점, 주제도의 범위 면, 행정구역만 있는 표본까지, 모음마다
  레이어. 그것으로 지어 본 것(`kigamdata.features`·`body`, 뷰·씨앗·영어판·시험)은 **`feature/kigam-data-layers` 가지**에 커밋해
  두었다. 그 뒤 판 세션이 이 갈림을 #153 에 유보로 올렸고, 사용자 지시로 이번 PR 에서는 뺐다. #153 에서 정해지면 그 가지를 PR 로
- 2026-10-02 에 로컬에서 받다가(상세 451 건째) "모두 정지" 로 멈췄다. 운영에서는 아직 부르지 않았다

## 운영

```
tmux new -s kigam-data 'docker compose exec -T web python manage.py fetch_kigam_data'   # 한 시간 20 분 남짓
```
