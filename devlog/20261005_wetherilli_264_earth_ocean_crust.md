# 온 지구 — 해양 지각 연대와 해저 퇴적층 두께

2026-10-05 · `feature/earth-ocean-crust` · wetherilli

판 세션이 준 일 — 해양 지각 연대(Seton 외 2020)와 해저 퇴적층 두께(GlobSed)를 온 지구 화면의 오늘 레이어로. 지각 두께(`crust.py`,
wetherilli 101)와 같은 꼴로, 격자 파일을 굽는다면 ADMAP-2(wetherilli 262)처럼 numpy 없이 할 수 있는지 먼저 보라는 것이었다.

## 조건

| 자료 | 원본 | 조건 | 근거 |
|---|---|---|---|
| 해양 지각 연대 | EarthByte `agegrid/2020/Grids/age.2020.1.GTS2012.6m.grd` (26 MB) | **CC BY 4.0** | 같은 자리 `agegrid/2020/LICENSE.txt` — NAS 에 함께 둔다(`agegrid2020_LICENSE.txt`) |
| 퇴적층 두께 | NOAA NCEI 기록 0305030 `GlobSed_package3/GlobSed-v3.xyz` (284 MB) | **이용 제약 없음** | NCEI 기록의 "Use Constraints: None · Access Constraints: None". 인용 Straume 외 2019 |

## numpy 없이 — 두 갈래

- **연대: NetCDF-3 고전판.** EarthByte 가 같은 격자를 `.nc`(NetCDF-4)·`.grd`(NetCDF-3)·`.xyz` 로 준다. 고전판은 머리(차원·속성·
  변수마다 자료가 시작하는 자리)가 단순해 `struct` 몇 줄로 읽고, 변수 하나를 big-endian 으로 풀면 된다(`seafloor.read_netcdf3`).
  기록 차원은 다루지 않는다 — 격자에는 없다. 위도 줄이 남→북으로 적혀 있어도 북→남으로 고친다
- **두께: 글 격자.** GlobSed 의 `.nc` 는 NetCDF-4(HDF5) — 읽으려면 h5py 가 든다(지각 두께가 그래서 호스트에서만 구웠다). 같은 판의
  `.xyz`(경도·위도·값 4 321 × 2 161 줄, 북→남)가 있어 그것을 읽는다. 땅은 `NaN`(308 만 칸)

둘 다 `manage.py build_seafloor` 하나로 10 초, 메모리 180 MB — 컨테이너에서 돈다.

- 버린 것: 연대의 6′ `.xyz`(128 MB) — `.grd` 가 4 분의 1 크기에 같은 값이다. 2′·1′ 판 — 온 지구 화면에는 6′ 이 줌 6 까지 넉넉하다
- GTS2012 판을 골랐다 — GeeK2007 판은 옛 지질 연대표다. 화면의 다른 연대(ICS)와 맞추려고

## 담는 꼴 — 지각 두께와 다른 점

지각 두께는 1° 라 저장소의 JSON 이면 되었다. 이것은 6′·5′ 라 칸이 650 만·930 만이다 — 저장소에 두지 않고 `<EARTH_DIR>` 에
**칠한 PNG**(팔레트 255 칸, 0.6·1.4 MB — 타일을 그릴 때 이것을 늘려 자른다)와 **int16 값**(13·19 MB — 누른 자리를 `seek` 으로 한
칸 읽는다), **격자 JSON**(원점·간격·배율) 셋을 둔다. 연대는 0.1 Myr, 두께는 m 로 적는다.

- 격자점 등록(gridline)이라 화소 가운데가 격자점이다 — 타일을 자를 때 반 칸 옮겨 잰다
- 줌 6 까지 그린다(타일 한 화소 0.011°). 원본보다 잘게 볼 때는 가장 가까운 칸으로, 넓게 볼 때는 섞어서
- 구운 것이 없으면 화면에 레이어가 서지 않는다(`then_data.seafloor`) — 화산·지진과 같은 길

## 색

- 연대: 해령의 젊은 빨강 → 노랑·초록 → 늙은 파랑·보라(0–280 Ma). 지중해 동부의 338.7 Ma 가 가장 늙다 — 280 너머는 끝 색이다.
  흔히 보는 연대 지도의 색 차례를 따랐다
- 두께: 얇은 크림 → 두꺼운 고동(0–12 km). 뱅골 선상지 8 km, 해령 둘레는 수백 m 안쪽

확인: 대서양 중앙해령은 빨간 띠로, 서태평양(일본 해구 동쪽 140 Ma)은 보라로 섰다. 땅(서울)은 빈 답이다.

## 운영 메모

- 배포 뒤 한 번: `manage.py build_seafloor --age /nfs/temp-share/GSM/sources/earth/age.2020.1.GTS2012.6m.grd --sediment
  /nfs/temp-share/GSM/sources/earth/GlobSed-v3.xyz` → `/srv/GSM/db/earth/seafloor_*`(컨테이너에서 NAS 가 안 보이면 두 파일을 `db/` 옆으로)
- 오늘의 레이어라 1 Ma 부터는 꺼진다. 옛 연대의 바다 밑(연대 격자를 판 회전으로 돌리기)은 하지 않았다 — 다른 일이다
