# 아프리카 — 남아공의 광업·석탄·우라늄 지역

2026-10-05 · `feature/africa-resources` · wetherilli

다른 대륙과 같은 꼴로 아프리카의 같은 서버들을 쟀다(1 초 간격). 건진 것은 남아공 하나다.

| 곳 | 잰 것 | 결과 |
|---|---|---|
| 남아공 CGS(DPME 사본) | `Geology/MapServer` 레이어 0–3 | **광업 지역 8·석탄 자원 지역 86·우라늄 지역 19** — 올렸다 |
| 나미비아 GSN(BGS OneGeology) | WMS Capabilities | 1:100만 지질 단위(`BA`·`BLS`)·선(`BLT`)뿐 |
| 부르키나파소 BUMIGEB(BGS) | WMS Capabilities | 지질 단위·단층뿐 |
| 카메룬 IRGM(BRGM mapsref) | WMS Capabilities | 지질 단위·단층뿐. mapsref 는 목록을 주지 않는다(`/carto/wxs/1GG/.map`) |
| BGS ArcGIS | 폴더 목록 | 아프리카는 지하수(`AGA`·`Africa_Groundwater`)뿐, `Ghana`·`Kenya` 폴더는 비었다. `CMIC` 는 세계 광물 가공 시설·영국 하천 퇴적물 |

## 왜 이렇게

- 남아공 셋은 지질도와 **같은 서비스의 다른 레이어**라 문의 표(`cgs.LAYERS`)에 번호만 더했다. 옮기는 셈(REST export·identify)도 그대로다
- 셋 다 **NO_STORE** 를 따른다 — 문 이름(`cgs`)으로 정해지므로 손댈 것이 없다. 정적 판에도 싣지 않는다
- 거친 지역 구분이다 — 광업 지역은 "New mining · Declining mining · Prod mining inf" 같은 이름뿐이고, 석탄 지역은 속성이 번호(`MINREG_`)뿐이라
  누르지 않는다. 우라늄 지역은 층군(`Mozaan group`)이 붙는다
- 한 색(simple renderer)이라 REST 범례의 칸 이름이 비어 범례를 두지 않았다
- 첫 그림 한 장이 33 초 걸렸다(광업 지역, 2026-10-05) — 다시 부르면 1.7 초. 상류가 처음 그릴 때 느린 것으로 본다

## 버린 것

- CMIC 의 세계 광물 가공 시설 — 아프리카 탭의 일이 아니다. 온 지구에 둘지 따로 본다
- 광상 점은 이 서버들에 없다. SIGAfrique(BRGM)나 나라 포털을 찾아야 한다 — TODOs

## 확인

- 사본 DB: 광업 지역 "New mining", 우라늄 지역 "Uranium · Mozaan group" 팝업, 세 레이어 타일 200
