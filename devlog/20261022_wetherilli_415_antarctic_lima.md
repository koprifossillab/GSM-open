# 남극 — LIMA/PGC 합성 위성 배경, 브라우저가 곧장

2026-10-22 · `feature/antarctic-lima` · wetherilli

Esri 남극 위성은 조건(Esri MLA)이 막아 공개 판·묶음에서 뺐다(P17). 기지 축척의 남극 위성이 공개 판에 없어졌고, 그 자리를 채운다.
후보는 `docs/극지_자료_후보.md` 의 6 순위(LIMA/PGC 합성 배경).

## 상류

`https://overlord.pgc.umn.edu/arcgis/rest/services/imagery/ant_pgc_composite_mosaic/MapServer` — 서비스 설명 그대로
"The Antarctic Composite Basemap is a tiled map service that includes the 15m Landsat Image Mosaic of Antarctica (LIMA) with a 250m MODIS mosaic
to fill the hole south of 82.5°S. … pre-cached levels down to 15 meter pixel size (approximate scale of 1:32,000)."

- **`_tpbg` 판은 쓰지 않는다** — 같은 영상이지만 `tileInfo` 가 없는 동적 서비스다(`singleFusedMapCache=false`). 구운 쪽이 빠르고 격자가 정해져 있다
- **바다는 투명하다** — 바다 칸은 알파 0 의 PNG(872 바이트)로 온다. 그래서 밑에 Blue Marble(GIBS 3031, 500 m, 서버가 담는 길)을 깐다.
  기지 위성 밑에 REMA 를 까는 것(093)과 같은 수다. 킹조지섬처럼 빙모가 덮은 섬은 흰 얼음으로 보인다
- 영상은 Landsat 7(1999–2003)이라 낡았다 — 빙붕 가장자리·후퇴한 빙하는 지금과 다르다. 배경 설명에 연도를 적었다

### 격자 — 묶음이 쓸 것

서비스의 `tileInfo`(2026-10-22):

| 항목 | 값 |
|---|---|
| 투영 | EPSG:3031 |
| 원점(왼쪽 위) | (−30636100, 30636100) |
| 타일 | 256 px, PNG(`MIXED` — 받아 보니 RGBA PNG) |
| 해상도 | 레벨 0 이 32000 m, 레벨 7(250 m)까지는 반씩. **레벨 8–11 은 120·60·30·15 m** — 2 의 거듭제곱이 아니다. 축척(453542.4·226771.2·…)을 96 dpi 로 셈하면 서비스가 적은 해상도와 맞는다 |
| 레벨 | 0–11 (11 = 15 m, 그 위는 OpenLayers 가 늘린다) |
| 범위 | (−3000000, −3000000, 3000000, 4000005) |
| 주소 | `…/MapServer/tile/{z}/{y}/{x}` (y 는 원점에서 아래로) |

화면(`map.js` 의 `limaLayer`)은 이 해상도 목록을 그대로 쓴다.
P17 의 Esri 극 격자(`ESRI_ANTARCTIC`)와 같은 꼴로 `gsmpack.grid` 에 "원점·해상도 목록" 격자로 넣으면 된다 — 해상도가 2 의 거듭제곱이 아니므로
레벨 7→8 은 0.48 배라 쿼드트리 셈(`deeper`·칸 나누기)이 거기서 맞지 않는다. 묶음에 넣을 때 이것을 먼저 본다.

## 조건 — 원문

- **USGS LIMA** (https://lima.usgs.gov/access.php): "These images are in the 'public domain' and can be used freely and without acknowledgement."
  "However, credit to the Landsat Image Mosaic of Antarctica (LIMA) Project is greatly appreciated."
- **PGC 서비스** — 라이선스 문구가 없다. `copyrightText` "USGS, BAS, NASA, Polar Geospatial Center", 레이어 메타데이터는 `idCredit` "Polar Geospatial Center"
  한 줄뿐, `exportTilesAllowed=false`. REMA 음영 서비스와 같은 처지다(TODOs "판 전에 정한다" 줄)
- **PGC 일반 정책** (https://www.pgc.umn.edu/guides/user-services/acknowledgement-policy/): "users agree to cite PGC and its sponsorship by the NSF",
  "The original source of any third-party data supplied by PGC must also be properly attributed." — 출처 표기에 LIMA(USGS·BAS·NASA)와 PGC(NSF)를 붙였다.
  같은 쪽의 "request approval prior to releasing or displaying any imagery" 는 EOCL 상업 영상(Maxar/Vantor)의 것이다 — LIMA 는 Landsat 이라 걸리지 않는다

영상이 공공 도메인이라 **보여 주는 것은 열려 있다.** 서버에 담는 것은 서비스 쪽 조건이 비었고 `exportTilesAllowed=false` 라 하지 않는다 —
아래 TLS 때문에 어차피 못 한다.

## TLS — 서버는 받지 못한다

`overlord.pgc.umn.edu` 가 **중간 인증서를 빼먹었다.** 바깥(WebFetch)에서도 "unable to verify the first certificate" 이고, 연구소 망의 가로채기 장비는
이 호스트를 "UNTRUSTED CERT ALERT" 로 다시 서명한다 — `extra_ca.pem`(KOPRI SSL)을 더해도 풀리지 않는다. 탄자니아(209)와 같은 꼴이다.
브라우저는 AIA 로 중간 인증서를 메워 연다(CORS 는 Origin 을 되비춘다). 서비스 JSON·메타데이터·타일 몇 장은 확인하려고 `curl -k` 로 한 번씩 읽었다 —
제품 코드는 검증을 끄지 않는다.

사람이 고른 길(2026-10-22):

- **(골랐다) 브라우저가 곧장** — REMA 음영과 같은 길. 서버 문을 짓지 않는다(`basemaps.py` 에 더하지 않았다). 연구소 망 안에서는 장비가 막아 안 보일 수 있다고
  배경 설명에 적었다
- (버렸다) 이 호스트만 `verify=False` 로 서버가 받아 담기 — 검증 끄기는 처음이 되고, 서비스 조건도 비었다
- (버렸다) 중간 인증서를 CA 묶음에 더하기 — 바깥에서는 되지만 운영 서버는 연구소 망 안이라 장비가 여전히 UNTRUSTED 로 바꾼다
- PGC(pgc@umn.edu)에 알릴지는 사람이 정한다 — TODOs (사람)

## 정적 판의 기본 배경

**정적 판의 남극은 LIMA 로 연다**(사람, 2026-10-22). P17 의 고침(`fix/static-no-esri`, 1.2.0)이 REMA 음영으로 바꿔 두었던 것을 LIMA 로 다시 바꿨다.
REMA 음영은 지형은 좋지만 회색이라 처음 보는 사람이 어디가 얼음이고 바위인지 모른다 — 위성이 낫다. 연구소 판은 그대로 Esri 로 연다(P17 이 정한 것).

이 브랜치는 `origin/fix/static-no-esri` 를 합쳐 땄다 — 그 브랜치의 `STATIC` 분기와 정적 판 시험(`test_남극은_Esri_없이_REMA_로`)을 고쳐야 해서다.
시험은 `test_남극은_Esri_없이_LIMA_로` 로 이름을 바꾸고 LIMA·Blue Marble 을 부르는지 본다. TODOs 의 부딪힘(main 의 REMA 줄 ↔ 그 브랜치의 Esri 줄)은
둘을 합쳐 풀었다.

화면은 눈으로 보지 못했다 — 이 서버의 chromium 은 연구소 망이라 overlord 를 받지 못한다. 타일 몇 장(레벨 2·6·8)을 받아 그림·투명한 바다를 봤고,
정적 판 시험이 화면이 짓는 주소를 확인한다.

## 고친 것

처음에 해상도를 `32000/2^z` 로 셌다가 `tileInfo` 를 다시 보고 레벨 8–11 을 서비스의 값(120·60·30·15)으로 바꿨다 — 2^z 로 세면 레벨 8 부터
타일이 엉뚱한 칸을 부르고 4 % 큰 자리에 그려진다.

## 다음

- **오프라인 묶음(P17)에 LIMA 소스** — 이번 일이 아니다. 서버가 받지 못하므로 굽는 쪽도 연구소 망 밖에서 곧장 받아야 하고, 격자는 위 표(레벨 8 의 꺾임)를 따른다.
  `exportTilesAllowed=false` 라 담기 전에 PGC 에 묻는 것이 맞다 — TODOs 의 PGC 줄과 함께 사람이 본다
