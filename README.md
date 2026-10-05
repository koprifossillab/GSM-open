# GSM — 대돌여지도

한국지질자원연구원 **지오빅데이터 오픈플랫폼** 오픈API 로 지질주제도를 보는 뷰어.

공식 플랫폼과 다른 곳은 넷이다.

- **레이어를 쌓아 본다** — 한 장씩 갈아끼우지 않고, 켜기·순서·투명도를 따로 준다
- **클릭하면 속성이 뜬다** — 그 지점의 지층명·지질시대·대표암석을 바로 읽는다
- **내 좌표를 얹는다** — CSV·GeoJSON 을 올리면 점묶음이 되어 지도 위에 선다
- **좌표가 늘 보인다** — 십진도와 도분초를 오가고, 찍어서 이동하고, 눌러서 복사한다

그리고 한 번 받은 타일은 **우리 디스크에 둔다.** 같은 자리를 다시 볼 때
상류에 묻지 않으니 빠르고, 상류 부담도 그만큼 준다
(`manage.py prune_tiles` 가 나이와 크기로 줄인다).

## 어디서 쓰나

| 자리 | 주소 | 무엇이 되나 |
|---|---|---|
| 연구소 안 | **http://paleolab/GSM/** | 전부 — 모든 지역·온 지구·달·화성·수성·3D, 점묶음 올리기, 서버 캐시 |
| 연구소 밖 | **https://koprifossillab.github.io/GSM-open/** | 정적 판 — 서버 없이 GitHub Pages 에서 돈다. 한국(KIGAM·VWorld, 각자 키)과 극지(그린란드·스발바르·얀마옌·북극해·남극) |

**연구소 밖 판은 각자의 인증키 둘로 본다** — [지오빅데이터 오픈플랫폼](https://data.kigam.re.kr/)의 KIGAM 키(한국 지질도)와
[VWorld](https://www.vworld.kr/) 키(배경지도·주소 찾기, 서비스 URL 에 `https://koprifossillab.github.io`). 처음 열면 둘을 묻는 창이 뜬다. 키는 그 브라우저에만 남고(30 일, "이 PC 에 기억하지 않기" 면 탭 동안만) KIGAM 에만 간다 —
우리 키는 그 판에 없다. 정적 판에서는 점묶음 올리기·3D·달·화성처럼 서버가 있어야 하는 것이 빠지고, KIGAM 지질도를
눌러 속성을 읽는 것도 아직 없다(KIGAM 이 브라우저에 속성을 열어 두지 않았다). 계획은 devlog wetherilli P11,
검토는 [docs/정적_밖_경로.md](docs/정적_밖_경로.md). 굽기·밀기는 `deploy/static_site.py`·`deploy/publish_pages.sh`.

소스는 공개용 저장소 **https://github.com/koprifossillab/GSM-open** 에 판마다 미는 사본이다(아래 "라이선스").

## 세우기

```bash
python -m venv ~/venv/GSM && . ~/venv/GSM/bin/activate
pip install -r requirements.txt

cp .env.template .env      # GSM_KIGAM_KEY 를 채운다
cd web && python manage.py migrate && python manage.py seed_catalog
python manage.py runserver
```

`http://127.0.0.1:8000/GSM/`.

**인증키가 아직 없어도 돈다.** 타일 자리에 안내가 뜰 뿐, 레이어 패널·좌표
표시·점묶음 업로드는 그대로 쓸 수 있다. 키는
[오픈API 신청](https://data.kigam.re.kr/my-openapi/request/)에서 받는다.

## 자료

| | |
|---|---|
| 상류 | `https://data.kigam.re.kr/openapi/wms` (WMS 1.1.1/1.3.0) |
| 열린 레이어 | `geoOpen` 61 종 — 지질도·지화학도·해저지질도·좋은물지도·동위원소 연대지도 |
| 좌표계 | 화면은 `EPSG:3857`, 자료 입출력은 `EPSG:4326` |
| 배경지도 | OpenStreetMap |

레이어 카탈로그는 상류 `GetCapabilities` 에서 뽑아 `data/kigam_layers.json` 에
두었다. **공식 안내 문서의 레이어 목록에는 틀린 것이 있다** — 자세한 것은
[CLAUDE.md](CLAUDE.md) 의 "상류의 함정" 과 [devlog 001](devlog/20260923_001_kigam-openapi-survey.md).

## 문서

- [docs/설치.md](docs/설치.md) — paleo-server 에 세우는 절차 (**root 가 필요하다**)
- [CLAUDE.md](CLAUDE.md) — 이름·낱말·구조의 규약
- [HANDOFF.md](HANDOFF.md) — 지금 어디까지 왔고 다음이 무엇인지
- [CHANGELOG.md](CHANGELOG.md) — 판 이력
- [devlog/](devlog/) — 왜 그렇게 했는지 (색인 [devlog/README.md](devlog/README.md))

각자 자기 계정에서 `feature/<기능 이름>` 브랜치로 작업하고 끝나면 PR 을 만든다. 병합은 사람이 정한다.
판을 올린 PR 이 병합되면 CHANGELOG 로 GitHub 릴리스를 만들고, 릴리스 태그마다 CI 가 Docker Hub
(`koprifossillab/gsm:<태그>`)에 이미지를 올린다. 자세한 규약은 CLAUDE.md "커밋과 PR".

## 라이선스와 자료의 출처

**코드는 GNU Affero General Public License v3.0(AGPL-3.0)을 따른다** — 전문은 [LICENSE](LICENSE).
AGPL 이라 **고친 판을 네트워크로 남에게 쓰게 하면 그 사람에게 소스를 내줄 길을 열어 두어야 한다**(13조).
밖에서 쓰는 사람이 받는 소스는 **공개용 저장소 https://github.com/koprifossillab/GSM-open** 이다 — 판마다 그 판의 소스를
한 커밋으로 민다(`deploy/publish_open.sh`). 소개 화면의 "소스" 링크가 거기를 가리킨다.

### 담아 둔 남의 코드

옮겨 오거나 담아 둔 코드는 제 라이선스를 지닌다. 전문은 그 파일 곁에 둔다.

| 코드 | 라이선스 | 전문 |
|---|---|---|
| EarthThruTime3D 의 옛 위치 셈(`paleo.py`) | MIT | [docs/licenses/EarthThruTime3D-MIT.txt](docs/licenses/EarthThruTime3D-MIT.txt) |
| OpenLayers 9.2.4 | BSD-2-Clause | [vendor/ol.LICENSE.md](web/viewer/static/viewer/vendor/ol.LICENSE.md) |
| proj4js | MIT | [vendor/proj4.LICENSE.md](web/viewer/static/viewer/vendor/proj4.LICENSE.md) |
| CesiumJS 1.145 | Apache-2.0 (딸린 코드는 `ThirdParty/`) | [vendor/cesium/LICENSE.md](web/viewer/static/viewer/vendor/cesium/LICENSE.md) |
| MapLibre GL JS 4.7.1 · 글리프 | BSD-3-Clause · SIL OFL 1.1 | [vendor/maplibre/LICENSE.txt](web/viewer/static/viewer/vendor/maplibre/LICENSE.txt) · [glyphs/LICENSE.txt](web/viewer/static/viewer/vendor/maplibre/glyphs/LICENSE.txt) |

### 지도 자료

**라이선스는 코드에만 걸린다. 지도 자료는 저마다 주인의 조건을 따른다.** 이 뷰어는 상류에서 받아 그릴 뿐이고, 화면마다 그 상류의 출처 표기를
띄운다(지도 오른쪽 아래). `data/` 의 씨앗은 레이어 목록(이름·제목·범위)이다. KIGAM 자료의 저작권은 한국지질자원연구원에 있고
([플랫폼 이용약관](https://data.kigam.re.kr/)) 5만 수치지질도는 CC BY-NC 다.

아래는 상류마다의 기관과 조건이다 — **[docs/상류_조건표.md](docs/상류_조건표.md) 에서 옮겼다**(그 표가 정본이고, CORS·서버 캐시·밖에 열 때 내릴 것·정적 판·근거
devlog 까지 적는다). "(사람) 읽을 것" 은 조건을 아직 읽지 않은 곳, 비상업 칸의 **NC** 는 비상업 조건, **판매** 는 기관이 자료를 파는 곳(보기만 열림),
**내부** 는 재배포 금지다.

#### 한국·동아시아

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `kigam` | 한국지질자원연구원 | **(사람) 읽을 것** — 오픈API 이용 약관(인증키) | — |
| `kigam50k` | 〃 (5만 WFS 를 받아 둔 파일) | CC BY-NC 로 적어 둠(`kigam50k.ATTRIBUTION`) — **(사람) 읽을 것**(근거 문서) | NC |
| `vworld` | 국토교통부 공간정보 오픈플랫폼 | VWorld 열쇠의 이용 약관(도메인 제한) | — |
| `peninsula` | (출처를 모르는 한반도 지질도 그림) | 모름 — 스캔판처럼 밖에 열지 않는다 | — |
| `phyloserver` | 연구실 phyloserver | 연구실 자료 | — |
| `gsj` | 일본 산총연 지질조사종합센터 | 정부표준이용규약 2.0 — 출처 표시 |  |
| `gsitile` | 일본 국토지리원 | 지리원 타일 이용 규약 — 출처 표시 |  |
| `gsjows` | 산총연 GSJ (다른 WMS·Navi 편집도) | 정부표준이용규약 2.0(안내 쪽 Terms of Use) |  |
| `ccop` | CCOP (GSJ 새 호스트) | "개인·교육·연구·비상업 용도로 자유롭게"(AccessConstraints) | **NC** |
| `gsmma` | 대만 경제부 지질조사·광업관리중심 | 정부 자료 개방 선언 — 무상·비독점, 상업 가공까지 허락, 출처 표시 |  |
| `geo3al` | USGS (중국 geo3al 파일) | "내부 용도만, 가공물 포함 제3자 재배포 금지"(메타데이터) | **내부** |
| `mris` | 몽골 국가지질조사소 MonGeoCat | 적힌 것 없음 — **(사람) 읽을 것** |  |

#### 동남아·남아시아·중동

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `esdm` | 인도네시아 지질청 | copyright 만 — **(사람) 읽을 것** |  |
| `jmg` | 말레이시아 광물지구과학국 | 찾지 못함 — **(사람) 읽을 것** |  |
| `mgb` | 필리핀 광산지질국 | copyright 비어 있음 — **(사람) 읽을 것** |  |
| `dmr` | 태국 광물자원국 | copyright 비어 있음 — **(사람) 읽을 것** |  |
| `gsiindia` | 인도 지질조사소 (그림 BGS) | 그림 "Free viewing", 속성 licenseInfo 비어 있음 — **(사람) 읽을 것** |  |
| `sgs` | 사우디 지질조사소 | Fees·AccessConstraints 비어 있음, 내려받기 회원제 — **(사람) 읽을 것** |  |

#### 극지

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `geus` | 덴마크·그린란드 지질조사소 | GEUS 이용 조건(terms 2014-06-20) — **개인 용도**, 다시 펴내려면 허락 | **개인** |
| `geusarc` | GEUS ArcGIS (자력·DTU 부게 중력·지질구) | 〃 | **개인** |
| `grportal` | 그린란드 정부 광물자원 포털 | 항목에 적힌 것 없음 — 다이아몬드 탐사 자료만 CC BY 4.0 |  |
| `npolar` | 노르웨이 극지연구소 | CC BY 4.0 (`Basisdata_Intern/*` 은 부르지 않는다) |  |
| `janmayen` | 〃 (파일) | CC BY 4.0 |  |
| `emodnet` | EMODnet Geology | CC BY 4.0 (EU 소유) |  |
| `ngu` | 노르웨이 지질조사소 — 기반암, 금속·산업·핵심 광물, 지구물리(같은 `geo.ngu.no/mapserver/`) | NLOD 2.0 (NGU 자료 정책. 광물·지구물리 Capabilities 의 Fees "none"·"no conditions apply") |  |
| `gtk` | 핀란드 지질조사소 | GTK 오픈 라이선스(CC BY 4.0 호환) |  |
| `sgu` | 스웨덴 지질조사소 | CC0 1.0 (Fees·AccessConstraints NONE) |  |
| `natt` | 아이슬란드 자연사연구소 | CC BY 4.0 (natt.is, 법 45/2018) |  |
| `pgc` | Polar Geospatial Center (ArcticDEM·REMA) | CC BY 4.0 |  |
| `geomap` | SCAR GeoMAP (파일) | CC BY 4.0 |  |
| `ibcso` | IBCSO v2 (파일) | CC BY 4.0 |  |
| `admap` | ADMAP-2 (파일) | CC BY 3.0 |  |
| `bas` | 영국 남극조사소 Bedmap3 | CC BY 4.0 (타일 서비스 항목) |  |
| `kopri` | 극지연구소 KPDC | **(사람) 읽을 것** — KPDC 공개 정책. 위 "먼저 볼 것" 2 |  |

#### 유럽

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `bgs` | 영국 지질조사소 | Open Government Licence (출처 문구 필수) |  |
| `gsni` | 북아일랜드 지질조사소 (BGS 서버) | OGL |  |
| `bgsgi` | BGS GeoIndex (자력·중력·광산·광물 산지·수리지질·G-BASE 시료) + CMIC 하천 퇴적물 지화학 | OGL(GeoIndex WMS). CMIC 는 REST 만이고 조건 글이 없다 — **(사람) 읽을 것** |  |
| `brgm` | 프랑스 지질광물조사소 (해외 영토 포함) | Licence Ouverte / Etalab 2.0. 광상·광산(`GITES_PT`·`MINES_PT`)도 같은 WMS·같은 조건 |  |
| `egdi` | EuroGeoSurveys | AccessConstraints·Fees NONE |  |
| `bgr` | 독일 연방 지구과학·자원청 | BGR 일반 약관 — 출처 표시로 무료. 원료 KOR250 도 AGB, BSK1000 은 "연방 지리자료 이용 규정"(GeoNutzV, 출처 표시) |  |
| `igme` | 스페인 지질광물연구소 (도미니카 SGN 포함) | "IGME 와 연락 없이 유료 부가가치 서비스 금지" — 무료 뷰어는 걸리지 않음. 도미니카판 조건 문구 없음. 광물 산지 BDMIN 은 AccessConstraints 가 비었다 |  |
| `gsi` | 아일랜드 지질조사소 | CC BY 4.0 (북아일랜드 몫 OGL v3) |  |
| `ispra` | 이탈리아 ISPRA | "보고 열람에 자유, 지적 재산 지켜" — 무료 |  |
| `lneg` | 포르투갈 LNEG | 적힌 것 없음(광상·자력·중력·방사능도 copyright "LNEG" 뿐) — **(사람) 읽을 것** |  |
| `swisstopo` | 스위스 연방 지형청 | 열린 정부 자료(OGD) — 출처 "© swisstopo" |  |
| `geosphere` | GeoSphere Austria | CC BY 4.0 (1:5만 메타데이터, 1:100만은 따로 읽지 않음) |  |
| `pig` | 폴란드 지질연구소 | "접근·이용 조건 없음"(메타데이터) |  |
| `tno` | 네덜란드 TNO | CC0 (AccessConstraints) |  |
| `dov` | 플랑드르 DOV | 무료 재사용 표준 라이선스 — 출처 표시 |  |
| `spw` | 왈로니아 공공서비스 | 자료 CC BY 4.0 (서비스 조건 PDF 는 읽지 않음) |  |

#### 아메리카

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `mrdata` | USGS mrdata (본토·알래스카·하와이·푸에르토리코·광물) | 공공 도메인 |  |
| `usgscarib` | USGS World Energy (카리브·남미) | 공공 도메인 |  |
| `sim3534` | USGS 대앤틸리스 (파일) | 공공 도메인 |  |
| `sgm` | 멕시코 지질조사소 | CC BY 4.0 (datos.gob.mx) |  |
| `nrcan` | 캐나다 천연자원부 | OGL–Canada |  |
| `ogs` | 온타리오 지질조사소 | OGL–Ontario |  |
| `sigeom` | 퀘벡 SIGÉOM | Licence du gouvernement ouvert – Québec (CC BY 4.0) |  |
| `ygs` | 유콘 지질조사소 | OGL–Yukon |  |
| `skgs` | 사스카치원 지질조사소 | Standard Unrestricted Use Data Licence 2.0 |  |
| `nsgs` | 노바스코샤 자연자원부 | DP ME 43 사용 허락 — 출처 표시로 원본·가공물 나눔 |  |
| `ags` | 앨버타 지질조사소 | OGL–Alberta |  |
| `bcgs` | 브리티시컬럼비아 지질조사소 | OGL–British Columbia |  |
| `calgs` | 캘리포니아 지질조사소 | © CGS — **(사람) 읽을 것** |  |
| `nbmg` | 네바다 광산지질국 | © 2019 University of Nevada, Reno. All Rights Reserved — **(사람) 읽을 것** |  |
| `wadnr` | 워싱턴 지질조사소(DNR) | 출판물(Digital Data Series) 인용 — **(사람) 읽을 것** |  |
| `dogami` | 오리건 지질광물산업부 | 적힌 것 없음 — **(사람) 읽을 것** |  |
| `dggs` | 알래스카 지질·지구물리조사소 | 메타데이터 Use_Constraints — 출처를 밝힌다(고쳤으면 고쳤다고). 광산·산지는 `distribution_policy` 가 모두 `public` |  |
| `ineter` | 니카라과 국토연구원 | AccessConstraints NONE, 그 밖 없음 — **(사람) 읽을 것** |  |
| `stri` | 스미스소니언 열대연구소 (파나마) | CC BY-SA 4.0 |  |
| `vmme` | 파라과이 광업·에너지 차관실 | 적힌 것 없음 — **(사람) 읽을 것** |  |
| `sgc` | 콜롬비아 지질조사소 | 콜롬비아 1:50만 CC BY 4.0 · **남미 1:500만은 CGMW 의 지도** | 남미 판 **판매** |
| `sgb` | 브라질 지질조사소 | CC BY-NC 4.0 (GeoSGB) | **NC** |
| `ingemmet` | 페루 INGEMMET | CC BY-NC-SA 4.0 (메타데이터) | **NC** |
| `iige` | 에콰도르 IIGE | 내려받기 허락 — 팔지 못한다 | **NC** |
| `segemar` | 아르헨티나 SEGEMAR | "SEGEMAR 의 재산, CC 아르헨티나로 쓸 때 저작자 표시", 보기는 무료 |  |
| `dinamige` | 우루과이 DINAMIGE | 적힌 것 없음 — **(사람) 읽을 것** |  |

#### 아프리카·오세아니아

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `cgmw` | CGMW–BRGM 아프리카 1:1000만 | "License Not Specified", CGMW 가 인쇄판을 판다 — **(사람) 읽을 것** | **판매** |
| `aga` | BGS 아프리카 지하수 지도책 | CC BY-SA 4.0 |  |
| `cgs` | 남아공 CGS (정부 DPME 사본) | copyrightText 비어 있음, CGS 는 자료를 판다 | **판매** |
| `gsn` | 나미비아 GSN (BGS 서버) | 자료를 판다 | **판매** |
| `bumigeb` | 부르키나파소 BUMIGEB (BGS 서버) | **(사람) 읽을 것** |  |
| `irgm` | 카메룬 IRGM (BRGM 서버) | **(사람) 읽을 것** |  |
| `ga` | Geoscience Australia | CC BY 4.0 |  |
| `gsq` · `gsv` · `gssa` | 퀸즐랜드·빅토리아·남호주 | CC BY 4.0 (주 열린자료·Capabilities) |  |
| `gsnsw` | 뉴사우스웨일스 지질조사소 | CC BY 4.0 (GeoServer AccessConstraints) |  |
| `mrt` | 태즈메이니아 광물자원청 (theLIST) | **(사람) 읽을 것** — theLIST 웹 서비스 약관, 레이어의 저작권 칸이 비었다 |  |
| `gns` | GNS Science (뉴질랜드·남빅토리아랜드) | CC BY 3.0 NZ (AccessConstraints) |  |
| `georep` | 누벨칼레도니 정부 Géorep | Licence Ouverte (내려받기 목록) — 약관의 "허락 없이 배포 금지" 와 갈려 보였다 |  |

#### 상류가 아닌 것

| 상류 | 기관 | 조건 | 비상업 |
|---|---|---|---|
| `earth` | 지역 탭의 지구 자료 점 — PBDB(CC BY 4.0)·GVP(**비상업·인용**)·USGS 지진(공공 도메인)·Neotoma(CC BY 4.0)·IHFC 지열류(CC BY 4.0) | 자료마다 | 파일 |
