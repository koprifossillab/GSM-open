# 정적 판 굽기 — `manage.py bake_static`

2026-10-02 · `feature/static-bake` · wetherilli

연구소 밖 정적 판(GitHub Pages, 계획 wetherilli P11 · 검토 [docs/정적_밖_경로.md](../docs/정적_밖_경로.md))의 한 몫이다.
뼈대(map.js 의 정적 모드·카탈로그·gh-pages 로 미는 길)는 판 세션(gsm-31)이 짓고, 여기서는 **서버가 우리 파일에서 그때그때
그려 주던 것을 정적 파일로 떠 두는 명령**을 짓는다.

## 출력은 화면이 부르는 주소 꼴 그대로

- `geomap/<레이어>/<z>/<x>/<y>.png`·`ibcso/<bed|ice>/…webp`·`ibcso/tid/…png`·`peninsula/<shaded|plain>/…webp` — 서버의
  주소와 한 글자까지 같다. 정적 판의 map.js 는 `BASE` 만 바꾸면 된다
- **점 레이어만 꼴이 다르다** — 서버는 `points/?layer=grportal:geochron` 처럼 물음으로 받는데, 정적 파일은 물음을 가를 수
  없다. `points/<상류>/<이름>.json` 으로 했다. 콜론을 파일 이름에 넣지 않은 것은 Windows 로 받는 사람이 있어서다
- 얀마옌·극지연구소는 팝업 이름·갈래가 언어마다 다르게 온다(`body(name, lang)`) — 영어판을 `<이름>.en.json` 으로 따로 둔다.
  그린란드 포털·NPI 는 이름표를 한국어로 싣고 화면이 옮기므로 하나만
- GeoMAP 범례는 `legend/geomap/<레이어>.png` — 서버는 `legend/?layer=` 로 그린다
- `manifest.json` — 몫마다의 보고, 폴더마다의 합(`dirs`), 파일 `[경로, 바이트]` 9 만 줄. 들여쓰기 하면 7 MB 라 짧게(4 MB 남짓)

## GeoMAP — 얼마나 깊이 굽나

2026-10-02 에 쟀다(`--measure` 와 같은 셈 + 줌마다 25 장 그려 보기). 3031 격자에서 자료가 걸치는 타일만 센다 — 면 레이어 넷은
줌 6 에 374·7 에 909·8 에 2 374·9 에 6 272·10 에 16 538 장, 한 장 2–5 KB.

| 레이어 | 마지막 줌 | 타일 | 크기 |
|---|---|---|---|
| 간추린 지질도 | 10 | 26 428 | 71.6 MB |
| 암층(무늬) | 9 | 10 182 | 45.3 MB |
| 지질시대 | 9 | 10 181 | 35.2 MB |
| 간추린 암상 | 9 | 10 181 | 30.8 MB |
| 지도 질 | 8 | 6 153 | 12.9 MB |
| 단층 | 9 | 10 228 | 10.7 MB |

- 검토 문서 §7 의 "여섯을 줌 10 까지면 수 GB" 는 어림이 컸다 — 자료가 있는 타일만 구우면 면 레이어 하나가 줌 10 까지 70 MB 다.
  그래도 넷을 다 10 까지 하면 250 MB 를 넘어, 화면이 처음 켜는 간추린 지질도만 10, 나머지는 9 로 두었다. `--geomap-zoom` 으로 바꾼다
- **내려가는 법** — 줌 0 에서 시작해 R*Tree 로 자료가 걸치는 타일만 그리고, 그려 보니 빈 타일(단층은 선의 상자만 걸쳐 7 466 장이
  비었다)은 버리고 그 아래로도 내려가지 않는다. 처음에 이 거르기 없이 줌 9 를 다 훑으면 26 만 장이다
- 굽지 않은 타일은 404 다. 화면은 빈칸으로 둔다. **줌을 더 들어가면 마지막 줌의 타일을 늘려 보이게** 하는 것은 map.js 의
  몫이다 — 레이어마다 마지막 줌을 manifest 의 `parts.geomap.<레이어>.max_zoom` 에 적었다
- 캐시에 같은 타일이 있으면 그것을 읽는다(쓰지는 않는다). 로컬 캐시라 14 장뿐이었다

## 나머지

- IBCSO 셋(해저·빙저·자료 출처)은 이미 잘라 둔 파일을 옮긴다 — 41.7 MB
- 점 레이어 — 그린란드 포털 9·NPI 7·얀마옌 3·극지연구소 37(언어 둘). 27.3 MB. 그린란드 지명(6.2 MB)·NPI 지명도 싣는다 — 정적
  판에서 찾기 칸이 쓸 수 있게. 서버와 같은 길(`views.point_features`)로 받아 상류에 묻는 것은 캐시에 없을 때뿐이다
- **아라온호 항적은 빼낸다** — 매시간 자라고, 연구실 안에서 열 때만 보이는 것이다(koprifossillab 006)
- **극지연구소(KPDC)는 싣는다** — 사용자가 정했다(판 세션이 전해 왔다). `LAB_ONLY` 에서 빼는 것은 뼈대 PR 의 몫
- **한반도 음영판·민판은 `--with peninsula` 일 때만** — 지금 `LAB_ONLY` 에 들어 있고 devlog 027·028 은 "출처를 몰라 밖에 열지
  않는다" 고 적었다. 판 세션은 사용자가 실어도 된다고 했다고 전했지만, 기본으로 굽지 않고 사람이 켜게 두었다. 36.9 MB

## 2026-10-02 에 구워 본 것

`--with peninsula` 로 9 만 3 186 파일·312.5 MB·11 분(가장 큰 파일 6.2 MB — 그린란드 지명). Pages 의 한도(사이트 1 GB·파일
100 MB) 안이다. 운영 `/srv/GSM/db` 를 읽어 세션의 임시 폴더에 구웠다.

```
GSM_GEOMAP_DIR=/srv/GSM/db/geomap GSM_IBCSO_DIR=/srv/GSM/db/ibcso GSM_NPOLAR_DIR=/srv/GSM/db/npolar \
GSM_KOPRI_DIR=/srv/GSM/db/kopri GSM_PENINSULA_DIR=/srv/GSM/db/peninsula \
python manage.py bake_static <outdir> [--with peninsula] [--geomap-zoom geomap_faults=8]
```
