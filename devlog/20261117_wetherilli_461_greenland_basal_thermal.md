# 그린란드 — 빙상 바닥의 열 상태 (GBaTS v2)

2026-11-17 · `feature/greenland-basal-thermal` · wetherilli

`docs/Earthdata_반입_후보.md` 의 가-3. BedMachine(459)이 "얼음 밑이 몇 m 인가" 라면 이것은 "얼음 밑이 언 땅인가 녹은 땅인가" 다.
MacGregor 외 2022 의 GBaTS v2(NSIDC `RDBTS4` v2, 17 MB, 5 km, 3413)에서 `likely_basal_thermal_state`(−1 언 바닥·0 갈린다·1 녹은 바닥)를 쓴다.

- **BedMachine 레이어군에 판 하나로** 넣었다(`bedmachine:thermal`) — 같은 3413 격자·같은 틀(`polargrid`)이고, 누르면 바닥 고도·두께가
  함께 나온다(`Set.along`). 명령도 `build_bedmachine` 하나 — 같은 폴더에 파일이 있으면 같이 굽는다
- **누르면 글로 낸다** — `polargrid.Set` 에 `words`(값 → 글)를 더했다. −1·0·1 이 숫자로 뜨면 읽는 사람이 범례를 다시 봐야 한다. 기본값이
  빈 표라 덧붙이와의 약속은 그대로다
- 5 km 라 줌 1(4 km)까지만 굽고 더 가까이는 OpenLayers 가 늘린다
- 설명에 **종합 판단이지 측정이 아니다**를 적었다 — 레이더 층의 감쇠·시추공 바닥 온도·모형 여럿·표면 유속을 견준 "가능성" 이다

## 버린 것

- 바닥 녹음 속도(`basal_melt`, m/년)·견준 갈래의 수(`agreement_*`) — 칸이 절반 남짓만 차고, 지질을 읽는 화면에서 먼저 묻는 것은 언가 녹았나다
