# gsmpack — 오프라인 묶음(.gsmpack)

대돌여지도(GSM)의 오프라인 묶음을 굽고 읽는 패키지다. 박스 하나의 타일과 누른 자리의 지층 면을 파일 하나로 잇고,
현장(망 없음·키 없음)에서 폰이 그 파일만으로 지도를 본다. 계획은 `devlog/20261021_wetherilli_P16_gsmpack_package.md`,
꼴은 아래 "꼴" 절.

**Django·GSM 을 타지 않는다** — GSM 없이 노트북에서도 돈다.

```
pip install ./tools/gsmpack
python -m unittest discover -s tools/gsmpack/tests -t tools/gsmpack
```

## 꼴 — `<박스>-<날짜>.gsmpack`

**이 절이 꼴의 명세다.** 쓰는 쪽은 `gsmpack/format.py`, 읽는 쪽은 `js/gsmpack-reader.js` — 꼴을 고치면 셋을 같은 커밋에서 맞추고,
옛 묶음을 읽지 못하게 되면 첫 8 바이트의 판(`GSMPACK1`)을 올린다. 처음 못 박은 판은 wetherilli P13 이다.

```
0      8 B   "GSMPACK1"
8      4 B   머리 길이 N (uint32, little-endian)
12     N B   머리 JSON (UTF-8)
12+N   …     타일 바이트를 잇달아
```

머리 JSON

```json
{"box": "jangseong", "title": "장성 도폭 (태백)", "built": "2026-10-12", "gsm": "0.99.0",
 "bbox": [128.978, 36.983, 129.268, 37.19], "region": "korea",
 "note": "연구실 현장용 — 밖으로 나누지 않는다",
 "dropped": {"vworld:Satellite": 16},
 "layers": {"L_50K_Geology_Map": {"title": "5만 지질도", "grid": "EPSG:3857", "tile_size": 512, "type": "image/png",
                                  "zooms": [7, 15], "attribution": "한국지질자원연구원 지오빅데이터 오픈플랫폼"},
            "vworld:Base": {"title": "VWorld Base", "grid": "EPSG:3857", "tile_size": 256, "type": "image/png",
                            "zooms": [8, 16], "attribution": "VWorld (국토교통부 공간정보 오픈플랫폼)"}},
 "units": {"L_50K_Geology_Map": {"key": "@units/L_50K_Geology_Map", "types": ["geoOpen:l_50k_geology_litho_latest"],
                                 "type": "application/geo+json"}},
 "tiles": {"L_50K_Geology_Map/12/3510/1580": [0, 18234], "@units/L_50K_Geology_Map": [18234, 9120]}}
```

- `tiles` 의 열쇠는 `<레이어>/<z>/<x>/<y>` — **3857 의 타일 격자(OpenLayers 의 tileCoord, 위에서 아래로 y)** 그대로다. 값은
  `[바이트 시작(머리 뒤에서 센다), 길이]`
- `zooms` 는 **격자 줌**이다. 격자는 `tile_size` 가 밝힌다 — 512 px 격자는 화면 줌보다 하나 작다(KIGAM), 256 px 는 화면 줌 그대로다(VWorld)
- `dropped` 는 예산(기본 200 MB)에 맞추려고 덜어 낸 레이어마다 빠진 첫 격자 줌이다
- 빈 타일(투명 한 장, 자료 밖)과 박스 밖의 타일은 넣지 않는다 — 없는 열쇠는 "그 자리에 그릴 것이 없다" 다. 박스에 걸친 타일은 박스 밖을 비웠다
- `units` 는 누른 자리의 속성 — 박스로 자른 지층 면 GeoJSON 한 덩이가 `tiles` 의 `@units/<레이어>` 에 든다. 면마다
  `properties: {props, props_en}`, 좌표는 소수 다섯 자리
- `gsm` 은 구운 GSM 의 판(GSM 이 구웠을 때만)
- **키는 어디에도 넣지 않는다** — 머리에도, 타일 주소에도

## 모듈

| 모듈 | 하는 일 |
|---|---|
| `format` | 꼴 쓰기·읽기·폴더의 묶음 목록 |
| `boxes` | 박스 표(`data/offline_boxes.json` 꼴) 읽기 |
| `grid` | 3857 타일 격자 — 박스를 덮는 칸 |
| `clip` | 타일·지층 면을 박스로 잘라 내기, 빈 타일 가리기 |
| `bake` | 굽는 고리 — 어림(`Plan`)·예산 맞추기·받기·쓰기, 이어 굽기(`Parts`) |
| `js/gsmpack-reader.js` | 브라우저에서 묶음 하나 읽기(`GSMPack`) — 머리·타일 Blob·마지막 줌보다 깊은 자리의 늘릴 칸(`deeper`)·지층 면·누른 자리. 저장·지도는 모른다 |

타일을 어디서 받을지는 패키지가 모른다. 부르는 쪽이 레이어마다 **소스**를 넘긴다(`bake.py` 머리글).
GSM 은 제 문(KIGAM·VWorld)과 서버 캐시를 소스로 꽂는다(`web/viewer/management/commands/build_offline_pack.py`).
GSM 을 거쳐 받는 소스와 제 키로 상류를 곧장 부르는 소스, `gsmpack` 명령은 P16 의 3 단계에서 더한다.

**빠르기는 굽는 고리 하나가 지킨다** — 상류에 1 초에 한 번, 차단 조짐이면 곧장 멈추고, 연달아 3 번 실패해도 멈춘다.
멈추면 받은 것은 `.<박스>.parts.sqlite` 에 남고, 다시 부르면 이어서 받는다.

**묶음은 연구실 안에서만 나눈다.** KIGAM·VWorld 타일을 담은 파일이다. VWorld 이용약관 제19조 ⑥은 "사전 승낙 없이 데이터를
무단으로 저장하지 못합니다" 라고 적는다(`docs/오프라인_묶음_조건.md`).
