# 남극 지열류 모형 셋 — 측정 점과 같은 색으로, 셋을 따로

2026-10-29 · `feature/antarctic-heatflow-grids` · wetherilli

극지 자료 3 차 조사의 5 순위. IHFC 측정 점(`heatflow.py`, wetherilli 267)은 남극에 드물다 — 얼음 밑을 잰 곳이 손에 꼽힌다. 그 사이를
메우는 모형 셋을 남극 탭에 올렸다. 431 의 틀(`polargrid.py`)을 그대로 쓰고, 이 브랜치는 431 위에 섰다.

| 판 | 원본 | 꼴 | 조건 |
|---|---|---|---|
| Aq1 | Stål·Reading·Halpin·Whittaker 2021, PANGAEA 924857 `aq1_01_20.csv` | 3031 X·Y, 20 072 m 격자 | CC BY 4.0 |
| 기계 학습 | Lösing & Ebbing 2021, PANGAEA 930237 `HF_Min_Max_MaxAbs-1.csv` | 경위도 점 — 위도 0.5° 고리, 고리마다 경도 간격이 다르다(약 55 km) | CC BY 4.0 |
| 퀴리 깊이 | Martos 외 2017, PANGAEA 882503 `Antarctic_GHF.xyz` | 극 평사도법 X·Y, 15 km 격자 | CC BY 3.0 |

## 셋을 하나로 섞지 않았다

평균이나 "가장 새것" 하나를 내는 길도 있었다. 버렸다 — 셋이 같은 자리에서 수십 mW/m² 씩 어긋나고(세종기지 77·94·없음, 장보고 80·103·없음),
**그 어긋남이 모형의 불확실성을 읽는 가장 쉬운 길**이다. 레이어 셋을 켜고 끄며 견주게 했다. 캡션(설명)마다 "모형이지 측정이 아니다" 를
맨 앞에 적었다. 불확실성 판(Aq1 의 `U`, Lösing 의 최소·최대, Martos 의 `_uncertainty.xyz`)은 내지 않았다 — 레이어가 여섯이 된다.
원하면 `ghfgrid.KINDS` 한 줄씩이다.

- Stål 은 50 km 판도 있다 — 20 km 만 쓴다. GeoTIFF·netCDF 판도 있지만 csv 가 numpy 없이 읽히고 같은 값이다
- Lösing 은 처음 판(`HF_Min_Max_MaxAbs.csv`)과 "자료를 더한 판"(`-1`)이 있다 — 뒤의 것을 쓴다

## 측정 점과 같은 색

`heatflow.CLASSES` 의 갈래 여섯(40·60·80·120·200 mW/m² 경계)을 그대로 칸 번호로 쓴다. 연속 색으로 칠하면 모형 안의 무늬는 더 보이지만,
**점을 격자 위에 얹었을 때 같은 색이면 같은 갈래**라는 것이 이 레이어의 쓸모라 갈래를 골랐다. 범례도 heatflow 의 것이다.

## 꼴이 다른 셋을 한 칸으로

- Aq1·Martos 는 이미 격자다 — 칸 간격을 점의 X 에서 가장 흔한 차로 읽고(20 072·15 000 m), **칸을 점에 맞춘다**(`rasterize` 의 원점이 가장
  왼쪽·아래 점). 431 의 첫 판은 원점을 칸 간격의 배수로 내렸는데, 20 072 m 처럼 끝수가 있는 격자는 점이 칸 가장자리에 걸렸다. 고친 뒤
  Aq1 31 897 점·Martos 59 328 점이 칸 하나씩에 든다
- Martos 의 X·Y 는 "polar stereographic" 이라고만 적혔다 — 3031(표준위도 −71°)로 읽었다. 구운 그림의 대륙 모양·자리가 Aq1 과 겹쳤다
- Lösing 은 경위도 점이라 3031 로 옮겨 **20 km 칸마다 가장 가까운 점**으로 채운다. 반지름 45 km(고리 간격 55 km 의 거의 다 — 점 사이 가장 먼
  칸이 39 km 남짓). 모자이크로 보인다 — 원본이 그만큼 거칠다. 사이를 섞어 매끄럽게 하는 것(IDW)은 버렸다 — 원본에 없는 값을 짓는다

타일은 줌 2(6.5 km)까지. 셋을 굽는 데 2 초, 타일이 판마다 20 장 남짓(0.1 MB)이다.

## 운영에서 할 일

```sh
mkdir -p /nfs/temp-share/GSM/sources/antarctic_ghf && cd /nfs/temp-share/GSM/sources/antarctic_ghf
curl -A 'GSM/0.1' -O https://download.pangaea.de/dataset/924857/files/aq1_01_20.csv; sleep 1
curl -A 'GSM/0.1' -O https://download.pangaea.de/dataset/930237/files/HF_Min_Max_MaxAbs-1.csv; sleep 1
curl -A 'GSM/0.1' -O https://store.pangaea.de/Publications/Martos-etal_2017/Antarctic_GHF.xyz
docker compose exec web python manage.py build_antarctic_ghf /nfs/temp-share/GSM/sources/antarctic_ghf/   # → /srv/GSM/db/antarctic_ghf/
```

컨테이너에서 NAS 가 안 보이면 세 파일(5 MB)을 `db/` 옆으로 잠깐 옮긴다. numpy 가 필요 없다 — 호스트 venv 로 불러도 된다.
