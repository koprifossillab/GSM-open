# 알래스카 — DGGS 중요 광산·산지와 광업 지구

2026-10-05 · `feature/alaska-minerals` · wetherilli

TODOs 의 "결정 없이 할 것" 둘째 줄. 미국 탭에 알래스카 지질·지구물리조사소(DGGS)의 광물 자료를 더했다.

| 레이어 | 서비스 | 수 |
|---|---|---|
| 중요 광산·산지 | `Mineral_Occurrences_2020_MIL1` 12 (`AlaskaMinerals`) | 335 곳 — 개발 단계(산지·탐사·개발·광산)로 칠한다 |
| 광업 지구 | `minerals/mineral_districts` 0 | 면 |

## 왜 이렇게

- **문은 미국 주 문(`usstates.py`)에 넣었다** — 네바다·워싱턴·오리건처럼 WMS 가 없고 REST `export`·`identify` 를 같은 꼴로 부르는 주 지질조사소다.
  상류 이름은 `dggs`
- **조건을 읽었다** — DDS 18(Alaska Minerals Database, doi:10.14509/30873)의 메타데이터 Use_Constraints 는 "이 자료를 쓴 출판물은 출처를 밝히고, 고쳤으면
  고쳤다고 적는다" 뿐이다. 서비스의 열 `distribution_policy` 가 335 곳 모두 `public, data visibility` 이고 `confidential_record` 는 비었거나 `n` 이다.
  정적 판에는 아직 싣지 않는다(다른 미국 주와 같이 사람이 고를 때)
- 지질도는 두지 않았다 — USGS SIM 3340(`mrdata:sim3340`)이 덮는다
- **점은 4 픽셀 둘레로 누른다** — 1 픽셀(주 지질도의 면)로는 기호 한가운데를 눌러야 걸렸다(`POINT_LAYERS`)
- 광업 지구는 한 색이라 REST 범례의 칸 이름이 비어 범례를 두지 않았다

## 알아 둘 것

- 이 서버는 **좌표를 옮겨 달라는 질의(`outSR`)에 504**(60 초)를 준다 — `export`·`identify` 는 3978·3857 모두 0.8 초다. 문은 `outSR` 을 쓰지 않는다
- 값 `none reported`(핵심 광물 없음)는 뺀다

## 확인

- 사본 DB: 광산 Kahilt (Cristo)(Cu, Au · Occurrence)·Molly(Cu, Mo), 광업 지구 Redoubt District(Cook Inlet-Susitna Region), 범례 넷(산지·탐사·개발·광산)
