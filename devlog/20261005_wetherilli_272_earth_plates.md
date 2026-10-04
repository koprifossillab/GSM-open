# 온 지구 — 판 경계와 세계 지질구 (Hasterok 2022)

2026-10-05 · `feature/earth-plates` · wetherilli

판 세션이 준 일 — Bird 2003 PB2002 판 경계를 갈래별 선으로, USGS 세계 지질구나 Hasterok 2022 지질구를 면으로, 온 지구 화면의
오늘 레이어로. 판 회전(`paleo.py`)과 섞지 말 것.

## 고른 것 — 둘 다 Hasterok 2022

| 후보 | 조건 | 판단 |
|---|---|---|
| PB2002 (Bird 2003, G³) | **원본이 조건을 적지 않는다.** 흔히 쓰는 GitHub 판(`fraxen/tectonicplates`)은 옮긴 이가 ODC-By 를 붙인 것 | 버림 — 옮긴 이의 조건은 원본의 조건이 아니다 |
| Hasterok 외 2022 GitHub(`dhasterok/global_tectonics`) | GPL-3.0(코드의 조건이 저장소째 붙어 있다) | 버림 — 자료에 GPL 을 따르면 타일까지 무엇을 지켜야 하는지가 흐리다 |
| **Hasterok 외 2022 Zenodo 5093930** | **CC BY 4.0** | **씀** — 경계(갈래 일곱·큰 판 여부)와 지질구(920 면·갈래 열여섯)가 한 모형에서 온다 |
| USGS World Geologic Provinces | 공공 도메인 | 지질구만 있고 갈래가 석유 지질 쪽이다 — Hasterok 이 낫다 |

PB2002 의 경계 갈래(SUB·OSR·CTF…)는 Hasterok 경계의 `type`(확장 중심·확장대·섭입대·충상·좌수향·우수향 변환·추정)이 같은 몫을 한다.
판 나눔도 같은 논문의 것이라 경계와 지질구가 맞물린다.

## 1.2 GB 를 받지 않고

Zenodo 판은 지구물리 격자·QGIS 판이 든 zip 하나(1.17 GB)다. 필요한 것은 `plates&provinces/` 의 셰이프 몇 MB 뿐이라
**zip 끝의 목차(중앙 디렉터리)만 Range 로 받아** 그 파일들의 자리를 찾고, 그 자리 둘레 11 MB 와 QGIS 스타일 70 KB 만 받았다. macOS 가
만든 zip 이라 지역 머리의 크기 칸이 비어 있어(데이터 서술자) 목차의 크기·자리로 풀었다. NAS `sources/earth/hasterok2022/` 에 두었다.

## 담는 꼴

`manage.py build_tectonics` → `data/earth_tectonics.json`(1.3 MB, 저장소). 0.01° 로 반올림하고 0.01° 안쪽의 꺾임은 Douglas–Peucker 로
덜어 냈다(1:1000 만 급이라 보이는 차이가 없다). 빙상 가장자리(`ice_margins.json`, 1.4 MB)와 같은 크기라 저장소에 두었다.

- 지질구 색은 **저자의 QGIS 판**(`gprv_types.qml`)의 갈래색 — 반쯤 비치게(QGIS 판도 alpha 0.5). 겹치면 작은 면이 이긴다(누를 때)
- 경계 색은 흔한 갈래색으로 골랐다(QGIS 판의 경계 규칙은 큰·작은 판으로 다시 갈려 색을 뽑기 어려웠다) — 확장 빨강·섭입 파랑·충상
  보라·변환 초록(좌·우 두 색)·추정 회색 점선. 큰 판의 경계(`level` 1)는 굵게
- 레이어 이름은 `tbound`·`tprov` — `plates` 는 이미 판 회전의 조각 경계다. 두 모형을 섞지 않는다
- 누르면 지질구의 이름·갈래·묶음·마지막 조산 운동·대륙·지각 갈래(서울 → Gyeonggi Massif, 조산대, Indosinian)

## 운영 메모

- 저장소의 파일이라 배포만 하면 선다. 굽는 일이 없다
- #257(지열류·GLiM) 위에 쌓았다 — 같은 자리(온 지구의 then_data·tile_versions·earth.js)를 건드린다
