# 북유럽 — 핀란드 지구물리, 북유럽 광상 FODD, 스웨덴 산지·자력

2026-10-05 · `feature/nordic-resources` · wetherilli

| 곳 | 서비스 | 올린 것 | 조건 |
|---|---|---|---|
| 핀란드 GTK | `GTK_Geofysiikka_WMS` | 항공 자력 이상·방사능 3색(누르지 않는다) | GTK 오픈 라이선스(CC BY 4.0) |
| GTK 가 내는 FODD | `kokoavaWMS` 의 `fennoscandia_mineral_deposit` | 노르웨이·스웨덴·핀란드·러시아 북서부 광상 한 표 | 같다 |
| 스웨덴 SGU | `berg:…MALM.MINERALRESURSER_VY`·`fysik:SE.GOV.SGU.MAGNET` | 광물·암석 산지(줌 6 부터), 자력 이상(누르면 nT 값) | CC0 |

## 왜 이렇게

- **노르웨이는 FODD 로 덮었다.** NGU 의 광물·지구물리 서비스 주소를 찾지 못했다 — 이름을 짐작해 부르면 404 이거나 `map` 이 없는 MapServer 다. FODD 가
  NGU 와 함께 만든 표라 노르웨이 광상이 든다(뢰로스 둘레 확인). 지구물리는 TODOs
- **SGU 를 뿌리 주소로 옮겼다.** 기반암(`berg`)과 지구물리(`fysik`)가 워크스페이스가 달라, 주소를 둘로 가르는 대신 `/geoserver/ows` 에 워크스페이스를 붙인
  이름으로 묻는다. 기존 기반암 타일은 두 주소가 바이트까지 같았다. 캐시 열쇠는 우리 이름이라 그대로다. 정적 판도 같은 표를 읽어 따라온다
- GTK 는 레이어마다 주소를 고른다(`gtk.SERVICES`) — 범례·속성도 같은 주소로
- 스웨덴 중력(`METAFLYG.GRAVIMETRI`)은 측정 범위의 면뿐이라, GTK 중력도 측정 범위뿐이라 뺐다

## 확인

- 사본 DB: FODD Outokumpu(Cu,Co · Closed mine · 29 Mt), SGU 산지 N. Gussjögruvan 1(Fe · 고원생대), 자력 −297 nT, 기반암 팝업 그대로. 타일·범례 200
- `manage.py test viewer` 1717 개 통과
