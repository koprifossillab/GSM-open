# 카리브 — USGS 대앤틸리스 지질도(SIM 3534)를 우리가 굽는다

2026-10-05 · `feature/caribbean-sim3534` · wetherilli

#236(wetherilli 248)이 카리브 탭에 세운 USGS 1:250만은 쿠바 하나를 몇십 개 면으로 그린다. 같은 USGS 의 대앤틸리스·버진아일랜드
지질도(Wilson & Labay 2025, SIM 3534)는 1:30만 급이라 면이 2 만 3 천이다. 웹서비스가 없고 ScienceBase 는 403 이어서
gsm-57 이 TODOs 에 "받아 굽는 꼴, 이틀 남짓" 으로 남겨 둔 일이다.

## 무엇을 받았나 — 옛 판

SIM 3534 의 자료는 ScienceBase 에만 있어 받을 수 없다. 옛 판 **OFR 2019-1036**(Wilson 외 2019)의 셰이프 zip 이
`pubs.usgs.gov` 에 그대로 있다(196 MB, NAS `N:\GSM\sources\caribbean\`). SIM 3534 는 이 판을 다듬어 낸 것이고 단위 기호가 같다.
새 판이 열리면 같은 `build_caribbean` 에 zip 만 바꿔 넣으면 되게 파일 이름(`GAgeol_poly`·`GAgeol_arc`·`GAdescrp.csv`)으로 찾는다.

## 굽는 꼴 — moonmap 을 따르되 3857 미터로 담는다

`caribmap.py` 는 `moonmap.py` 의 틀 그대로다: 셰이프 → sqlite(R*Tree) → Pillow 타일, 꼭짓점은 `moonmap.pack`. 다른 점 둘.

- **좌표를 3857 미터로 담는다.** 셰이프는 "Caribbean_Lambert_Conformal_Conic"(표준위선 17.5°·22.5°)이다. 경위도로 담으면 타일마다
  메르카토르로 옮겨야 하는데, 이 탭은 3857 뿐이고 3D 도 3857 이라 굽을 때 한 번 옮기면 끝난다. float32 라도 서경 85° 에서 0.5 m 다.
  달처럼 극지 판을 따로 그릴 일이 없어 경위도로 둘 까닭이 없었다
- **설명은 표를 갈랐다.** `GAdescrp.csv` 의 설명은 단위마다 몇 천 자다. 처음에 면마다 적었더니 76 MB 가 되었다 — GAclass 마다 한 줄
  (`descr` 표)로 옮기니 24 MB. 팝업에는 앞 600 자만 싣는다

## 색 — USGS 표준 채움을 읽었다

면의 `GA_SYMBOL` 은 978·20 같은 번호뿐이고 zip 에 RGB 표가 없다. 번호는 USGS 지질도 표준 CMYK 채움(`styles/wpgcmykg.style`)의
기호 번호다. `.style` 은 Access(Jet) 파일이라 긁는 데에만 `access_parser` 를 썼고(제품에는 넣지 않았다), 채움 기호 직렬화의
바이트 262–265 가 C·M·Y·K 백분율인 것을 기호끼리 견주어 찾았다(기호 1 과 20 이 그 두 바이트만 다르다). 998 기호를 RGB 로 옮겨
`data/usgs_wpg_colors.json` 에 두었다 — 이 지도가 쓰는 127 기호가 다 든다. 같은 표준을 쓰는 다른 USGS 지도도 이 표로 칠할 수 있다.

버린 것: #236 의 `usgscarib._FALLBACK` 처럼 시대 글자로 색을 고르기 — 원도의 색을 두고 지어낼 까닭이 없었다.

## 선 — 단층만

호가 8 만 1 천인데 반은 접촉선·해안선이다. 접촉선은 면의 테두리(줌 9 부터 가는 선)가 이미 그리므로 단층 4 만만 따로 레이어로 두었다.
`LINE_TYPE` 글귀로 다섯 갈래(드러스트·정단층·주향이동·덮인 단층·변위 모름)를 갈라 색을 달리했다. 드러스트의 톱니는 그리지 않았다 —
1:30만 지도의 톱니 방향은 "선을 그은 쪽 오른쪽" 이라 선의 방향을 지켜야 하는데, 그 품에 견주어 얻는 것이 적다.

## 화면에 잇는 길 — 페루 꼴

타일은 `sim3534/<units|faults>/z/x/y.png`(구운 것을 캐시에 담는다, 열쇠·주소에 파일의 때와 `RENDERER`), 누른 자리는 위경도로
`sim3534/info/`, 범례는 보는 범위의 단위(`sim3534/legend/`, 8° 넘으면 묻지 않는다) — 페루 INGEMMET(wetherilli 195)과 같은 꼴이라
화면은 `gsjSource` 와 새 `sim3534InfoUrl` 하나만 더했다. `/featureinfo/` 의 문(`_Door`)에 끼우지 않았다 — 문은 상류를 부르는 자리이고
이것은 파일이다. 3D 도 같은 z/x/y 를 얹는다(`MAP3D` 목록).

상류는 `sim3534` 로 두었다 — `usgscarib` 와 같은 USGS 지만 길이 전혀 달라(피처 서비스 한 덩이 / 우리가 굽는 타일) 이름을 갈랐다.

## 운영 메모

- 운영 자리 `/srv/GSM/db/caribbean/sim3534.sqlite` 를 한 번 굽는다:
  `manage.py build_caribbean /nfs/temp-share/GSM/sources/caribbean/ofr20191036_spatialdata.zip` (11 초, 24 MB). 컨테이너 안에서 NAS 가
  안 보이면 zip 을 `db/` 옆에 잠깐 옮겨 부른다
- 파일이 없으면 타일 자리에 안내 타일, 누르면 503 — 뷰어는 돈다
- 공공 도메인이라 밖에 열어도 된다. 정적 판에는 서버가 그리는 것이라 싣지 않는다
