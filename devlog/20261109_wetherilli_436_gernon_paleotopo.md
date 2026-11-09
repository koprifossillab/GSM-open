# 동남극 고지형 Gernon 2026 — 열 연대를 고도 단계로 칠한 남극 탭 레이어

2026-11-09 · `feature/gernon-paleotopo` · wetherilli

발표에서 Gernon 외 2026(Science 392:eadz6758)의 Fig. 3A 를 남극 탭에서 보이려 한다. 배경은 `docs/남극_논문_세편_검토.md` 3 절의
갈림길 1 — 개인 레이어는 벡터뿐이라 색칠한 고지형은 서버 레이어여야 한다. 등고선은 wetherilli 435 가 따로 낸다.

## 틀은 polargrid 그대로

자료가 5 km 3031 격자(601×601 float32 GeoTIFF)라 AntGG2021·지열류 모형(431·432)과 꼴이 같다. 새로 짠 것은 GeoTIFF 를 `Grid` 로
옮기는 `gernontopo.read_tif` 하나다. **Pillow 가 float32 LZW TIFF 를 그대로 연다** — numpy·GDAL 없이 컨테이너에서 굽는다(열 연대 5 초).
원점은 GeoTIFF 꼬리표(33922·33550)에서 읽고 반 칸 옮긴다 — 모서리 원점이고 polargrid 는 칸의 가운데를 받는다.

`polargrid.Set` 에 `extra`(누른 자리에 함께 낼 고정 속성) 하나를 더했다. 누르면 고도와 함께 **연대**가 떠야 하는데, 레이어 이름만으로는
팝업에서 몇 Ma 인지 한눈에 안 들어온다. 판마다 속성 이름을 바꾸는 길(`고도 70 Ma (m)`)은 영어 표가 열 줄 늘고 열이 갈려 버렸다.

## 연대 열 개, 레이어 열 개

34 장(2 Myr) 다 내면 패널이 34 줄이다. 등고선 쪽(435)과 같은 100·90·80·70·60·50·44·40·36·34 Ma 만 낸다 — 두 쪽을 겹칠 때 짝이 맞는다.
44 Ma 부터 촘촘한 것은 본문이 빙모가 서는 시점을 그 언저리로 보기 때문이다. 한 레이어에 시간 축을 다는 길(온 지구의 `?age=`)은
남극 탭에 그런 틀이 없어 버렸다 — 켜고 끄며 넘기면 된다.

## 칠하기

PaleoDEM(`paleodem.py`)의 SEA·LAND 빛을 **단계로** 끊었다 — 연속으로 칠하면 1 500 m 문턱이 안 보인다. 1 000–1 500 m 는 연한 황토,
**1 500 m 부터는 녹슨 빛으로 건너뛴다** — 본문이 빙모가 앉을 수 있다고 보는 높이라 Fig. 3A 를 읽는 열쇠다. 3 000 m 위는 흰빛(만년설 느낌,

## 적어 둔 조건

설명·출처에 "FastScape 모형 재구성이지 관측이 아니다", "좌표는 오늘의 자리(판을 돌리지 않았다)", 5 km, 34 Ma 바탕 Paxman 외 2019,
doi 둘(10.1126/science.adz6758·10.5281/zenodo.19205651), CC BY 4.0. 그림(AAAS)이 아니라 Zenodo 의 자료를 쓰므로 CC BY 로 충분하다.

## 운영에서 굽기

```
docker compose exec web python manage.py build_gernon_paleotopo /nfs/temp-share/GSM/sources/antarctic_papers/gernon2026_zenodo_19205651_GIS_files.zip
```
컨테이너에서 NAS 가 안 보이면 zip 을 `/srv/GSM/db/` 아래에 두고 그 경로로 부른다. 결과는 `/srv/GSM/db/gernon_paleotopo/<연대>/`(연대마다 0.1 MB).
