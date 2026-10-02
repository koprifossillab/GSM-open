# 유럽 2단계 — 독일 BGR·스페인 IGME·아일랜드 GSI·북아일랜드 GSNI

2026-10-02 · `feature/europe-more` · wetherilli

143 에서 TODOs 에 남긴 줄이다. 영국·프랑스 다음으로 독일·스페인·아일랜드를 유럽 묶음에 더했다. #116(143) 위에 쌓았다.

## 1. 상류와 조건

| | BGR (독일) | IGME (스페인) | GSI (아일랜드) | GSNI (북아일랜드) |
|---|---|---|---|---|
| 서버 | `services.bgr.de/wms/geologie/{gk1000,guek250}/` | `mapas.igme.es/…/{IGME_Geologico_1M,IGME_MAGNA_50}/MapServer/WMSServer` | `gsi.geodata.gov.ie/server/services/Bedrock/…` | BGS 서버의 `GeoIndex_GSNI/GSNI_Geology_Landsat_WMS` |
| 조건 | BGR 일반 약관 — 출처를 밝히면 무료 ("Datenquelle: GÜK250 (WMS), (c) BGR") | 유료 부가가치 서비스면 IGME 와 연락하라 — 무료 뷰어는 걸리지 않는다 | **CC BY 4.0** (1:100만의 북아일랜드 몫은 OGL v3) | **OGL** ("Contains GSNI materials © Crown Copyright") |
| 3857 | 된다 | MAGNA 는 된다, **1:100만은 안 된다** | 된다 | 된다 |
| 속성 | `geo+json` (독일어 표제) | MAGNA `geo+json`, 1:100만 ArcGIS XML | `application/geojson` | ArcGIS XML |

넷 다 ArcGIS 다. 넷 다 열쇠가 없다.

## 2. 사용자와 정한 것

- **새 탭 셋(독일·스페인·아일랜드) + 유럽 묶음.** 아일랜드 탭은 섬 전체다 — GSI 의 1:100만이 이미 공화국과 북아일랜드를 이은 한 판이고,
  북아일랜드 1:25만(GSNI)을 같은 레이어군에 둔다. 북아일랜드를 나라대로 영국 탭에 두는 길도 있었지만 그러면 아일랜드 탭의 북쪽이 빈다
- **레이어 열하나** — 독일 넷(GK1000, GÜK250 층서·암상·구조선), 스페인 셋(1:100만 암상, MAGNA 암상·접촉면과 단층), 아일랜드 넷(섬 1:100만
  기반암·단층, 공화국 1:10만, 북아일랜드 1:25만)
- 이주 0021 (143 의 0020 뒤). 셋 다 EGDI 1:100만을 `borrow` 로 빌린다 — 넓게 볼 때 밑을 채운다

## 3. 이름 — `<상류>:<판>:<번호>`

ArcGIS WMS 의 레이어 이름이 번호(`0`·`7`)다. 한 상류가 서비스(판)를 둘씩 내므로 이름에 판을 넣었다 — `bgr:guek250:7`·`igme:magna50:0`·
`gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM`. 문이 판으로 주소를 고르고 번호를 상류에 넘긴다(`split`). 판이 다른 레이어를 한 번에
묻는 것은 막는다 — 화면은 레이어마다 따로 부르므로 그럴 일이 없다.

GSNI 는 BGS 서버가 대신 낸다. 문은 서버마다 하나라 `bgs.py` 의 `GSNI` 로 두었다 — CCOP 가 `gsj.py` 에 든 것과 같다. 상류 이름은 `gsni` 로
따로 둬 출처 문구를 GSNI 의 것으로 단다.

## 4. 줌

143 처럼 줌마다 한 장씩 받아 쟀다(카셀·마드리드·아일랜드 가운데·벨파스트 서쪽).

| 판 | 그리는 화면 줌 |
|---|---|
| BGR GK1000 | 9–10 |
| BGR GÜK250 (셋 다) | 10–14 |
| IGME 1:100만 | 제한 없음 |
| IGME MAGNA | 11– |
| GSI 1:100만 | 제한 없음 |
| GSI 1:10만 | 6–14 |
| GSNI 1:25만 | 제한 없음 |

**독일은 줌 9 전에 BGR 판이 없다** — GK1000 이 1:47만–189만이라고 적혀 있는데 줌 5–8 에서 비어 온다. 그 자리는 EGDI 가 채운다.

## 5. 함정 — 1.3.0 의 4326

스페인 1:100만은 3857 을 거절해 4326 으로 받는다. 첫 화면에서 **그려지지 않았다.** 화면(OpenLayers)은 WMS 1.3.0 으로 묻고, 1.3.0 의
4326 은 범위를 **위도 먼저** 적는다. 문은 상류에 1.1.1 로 옮겨 적는데(경도 먼저) 범위를 그대로 넘겨 엉뚱한 바다를 물었다. 문이 1.3.0 의
4326 범위를 뒤집게 고쳤다(`igme._wms`, 시험). 대만(136)은 화면이 처음부터 4326 격자를 1.1.1 로 부르게 해서 이 일이 없었다.
다른 문에도 같은 구멍이 있다 — 3857 만 받는 문은 상관없지만, 4326 을 받는 문이 생기면 같은 것을 넣는다.

## 6. 속성

- BGR — 열 이름이 독일어 표제(`Legendentext`·`Stratigraphie - gesamt`)다. 지질시대 값도 독일어(`Holozän`)라 `age_ko` 가 읽지 못해 원문이다
- IGME 1:100만 — `text/plain` 은 값 안의 쌍반점(`Conglomerados; gravas; …`)이 칸을 깨서 못 쓴다. GeoJSON 은 주지 않는다. ArcGIS 의
  `featureinfo_xml` 로 읽었다. 열 이름의 띄어쓰기가 빠져 온다(`Litologíagenérica`·`Eon-Era`). 시대 값은 스페인어 대문자(`CUATERNARIO`)
- GSI·GSNI — 영어. GSNI 는 GeoJSON 을 청해도 ArcGIS XML 을 줘서 처음부터 XML 로 묻는다. 열은 BGS 와 같은 꼴(`LEX_D`)이라 `bgs.friendly` 를 쓴다

값을 옮기지 않는 규칙대로 독일어·스페인어 시대 값은 원문이다. 낱말표(Holozän→홀로세, CUATERNARIO→제4기)를 둘지는 쓰는 사람이 생기면 본다.
