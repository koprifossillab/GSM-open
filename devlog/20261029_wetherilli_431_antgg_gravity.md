# 남극 중력 AntGG2021 — ADMAP 의 굽는 틀을 떼어 함께 쓴다

2026-10-29 · `feature/antgg-gravity` · wetherilli

극지 자료 3 차 조사(`docs/극지_자료_후보.md`)의 3 순위. AntGG2021(Scheinert·Zingerle·Schaller·Pail 2024, PANGAEA 971238, CC BY 4.0)을
남극 탭의 지구물리에 ADMAP-2 자력(wetherilli 262)의 짝으로 올렸다. 서비스가 없고 파일뿐이라 ADMAP 처럼 받아 굽는다.

## 무엇을 레이어로 냈나

PANGAEA 에 판이 여덟이다 — 지표의 중력 이상, 그 표준편차, 중력 교란(지표·5 000 m), 부게 이상, 높이 이상(지표·타원체), 교란 퍼텐셜의
2 차 미분. **부게 이상과 지표의 중력 이상(프리에어) 둘만** 냈다.

- 부게는 지각 두께를 읽는 판이다 — 동남극 고원이 −400 아래, 바다 쪽이 양. 지질을 보는 화면에서 가장 쓸모가 크다
- 프리에어는 지형과 구조가 함께 드러난다 — 횡단남극산맥·해안선이 선다. 온 세계 판(gravmag, wetherilli 391)에는 프리에어가 없다
- 버린 것: 중력 교란·높이 이상은 측지(지오이드) 쪽 쓰임이다. 표준편차는 "이 값을 얼마나 믿나" 를 보이지만 레이어 하나를 더 세울 만큼은
  아니라 보았다 — 원하면 판 하나 더하는 일이다(`antgg.KINDS` 한 줄). 2 차 미분은 경계를 날카롭게 보이지만 읽는 사람이 드물다

## 머리를 믿지 않았다 — 값은 (y, x) 차례다

netCDF 머리(PANGAEA 의 `_header.txt` 도)는 변수를 `grav_anom(x, y)` 라 적는다. 그대로 읽어 구우니 대륙 모양은 그럴듯한데 반도가
왼쪽 아래에 섰다. 딸린 표면 고도 `h_ell` 로 대어 보았다 — (x, y) 로 읽으면 돔 A 가 2 822 m·보스토크가 1 561 m, **(y, x) 로 읽으면
4 090 m·3 478 m** 다(최댓값 4 090.5 m 가 돔 A 의 칸에 있다). 그래서 (y, x) 로 읽고 꼴이 (y 수, x 수) 가 아니면 멈춘다. 고친 뒤 세종기지
프리에어 +115·부게 −135, 남극점 부게 −426, 보스토크 −438, 장보고 −287 mGal.

## 왜 굽기만 호스트에서

원본이 **NetCDF-4(HDF5)** 다 — 청크 667×667, 압축은 없다. ADMAP 의 Geosoft 격자나 해양 지각 연대(NetCDF-3, wetherilli 264)처럼 numpy
없이 풀 수 있을까 보았지만 HDF5 는 머리·B-트리·청크 표를 다 읽어야 해 손으로 쓸 만한 것이 아니다. PaleoDEM(wetherilli 375)과 같이
**h5py 로 읽는 일만 호스트에서**(`run.sh build_antgg`) 하고, 칠하고 자르는 일은 numpy 없이 같은 명령 안에서 한다. 제품은 구운 것만
읽는다. 판 하나에 2 초다 — 다시 구울 일은 AntGG 가 새 판을 낼 때뿐이다.

- 버린 것: 원본을 저장소에 두는 것(27 MB × 2), 컨테이너에 h5py 를 까는 것(이미지에 HDF5 라이브러리가 든다 — 한 번 구울 일에 비해 크다)

## 틀을 뗐다 — `polargrid.py`

ADMAP 의 굽기(칸 번호로 칠하기 → Pillow `P` → 미리 곱한 RGBa → GeoMAP 3031 격자로 줄이며 자르기 → `values.i16`·`meta.json`)는 판에
매이지 않는다. 다음 일(432, 남극 지열류 격자 셋)도 같은 꼴이라 **`polargrid.py` 로 뗐다** — `Grid`(위에서 아래로), 판 명세 `Set`
(폴더·배율·칠하기·줌), `bake`·`value_at`, 그리고 흩어진 점을 칸으로 채우는 `rasterize`(432 의 Lösing 모형이 경위도 점이다).
화면 쪽도 하나로 묶었다 — 주소 `polargrid/<상류>/<판>/{z}/{x}/{y}.webp`·`polargrid/info/?layer=`, `views.POLAR_SETS`, map.js 의
`polargridInfoUrl`. 판을 더하면 `POLAR_SETS` 에 그 모듈의 `SETS` 를 펼치고 map.js 에 상류 한 줄이다.

- **ADMAP 은 옮기지 않았다** — 주소(`admap/…`)가 브라우저 캐시·정적 판 굽기·시험에 걸려 있고, 지금 고칠 까닭이 없다. 같은 꼴의
  둘째 판이 생긴 지금이 뗄 때였을 뿐이다
- 정수로 적는 배율 — 중력은 0.1 mGal(×10). int16 이라 ±3 276.7 mGal 까지 든다

## 칠하는 법

온 세계 부게(gravmag)의 파랑–흰–빨강(ColorBrewer RdBu 뒤집음)을 그대로 쓰고 범례 칸(끝에 대한 비)도 같다. **끝만 다르다** — 부게 ±500,
프리에어 ±150 mGal. gravmag 의 ±300 으로 칠해 보니 동남극이 다 −300 아래라 대륙이 짙은 남색 한 덩이였다. 부게의 1–99 % 가
−473 … +177, 프리에어는 −80 … +88 이다. 두 화면의 같은 색이 같은 mGal 이 아니게 되지만, 남극 탭에서 대륙 안의 무늬가 보이는 쪽을
골랐다. 범례에 mGal 이 적혀 있다.

타일은 줌 3(3.3 km)까지 — 원본 한 칸이 5 km 다. 3D 는 ADMAP 처럼 서버가 3857 로 편다(`warp/antgg/…`).

## 운영에서 할 일

```sh
mkdir -p /nfs/temp-share/GSM/sources/antgg2021 && cd /nfs/temp-share/GSM/sources/antgg2021
curl -A 'GSM/0.1' -O https://download.pangaea.de/dataset/971238/files/AntGG2021_Bouguer-anomaly.nc
sleep 1
curl -A 'GSM/0.1' -O https://download.pangaea.de/dataset/971238/files/AntGG2021_Gravity-anomaly.nc
/srv/GSM/scripts/run.sh build_antgg /nfs/temp-share/GSM/sources/antgg2021/     # → /srv/GSM/db/antgg/{bouguer,free_air}/
```

배포 뒤 한 번(`seed_catalog` 가 레이어군 "지구물리 (AntGG2021)" 를 넣는다). 파일이 없으면 안내 타일 — 뷰어는 돈다. 정적 판에는 싣지
않았다(서버 타일). CC BY 4.0 이라 실을 수는 있다.
