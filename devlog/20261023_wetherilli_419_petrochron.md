# 남극 암석 화학·연대 — PetroChron Antarctica 를 받아 구워 점 레이어로

2026-10-23 · `feature/petrochron` · wetherilli

극지 자료 2 차 조사(`docs/극지_자료_후보.md` "## 2 차 조사", 12 번)의 PetroChron Antarctica 를 남극 탭에 붙였다.
남극 암석 시료의 분석 1 만 1 천 559 줄 — 암석·전암/광물 화학·연대·모형 암석 물성을 논문 362 편에서 모은 것이다.

## 이용 조건

Zenodo 레코드 5032026 의 메타데이터(2026-10-23 에 API 로 읽었다):

> PetroChron Antarctica is a relational database containing petrological, geochemical and geochronological datasets along
> with computed rock properties from sampled rocks across Antarctica.

> license: `cc-by-4.0` (Creative Commons Attribution 4.0 International)

만든 이 — Sanchez, Halpin, Gard, Hasterok, Stål, Raimondo, Peters, Burton-Johnson. 판 `0_1`, 2021-06-25. 저장·가공·재배포에
막는 것이 없고 출처만 밝힌다 — 지도 귀퉁이(`ATTRIBUTION`)와 범례 칸의 원본 링크(DOI 10.5281/zenodo.5032026)가 그 자리다.
조건이 생각과 같아 묻지 않고 붙였다.

## 무엇을 받나 — 엮은 표 하나와 참고문헌

레코드에는 파일이 일곱이다 — `_metadata_`·`_petro_`·`_geochem_`·`_geochron_`·`_rock_prop_`·`_db_`·`_refs_.bib`.
**`_db_` 가 앞의 다섯을 한 줄에 엮은 표**(197 열, `*_id` 로 이은 것)라 이것과 `.bib` 만 받는다. 나눠 받아 우리가 다시
엮으면 같은 것을 두 번 짓는 셈이다. 덤으로 `_metadata_` 는 cp1252(`S�r Rondane`)인데 `_db_` 는 UTF-8 이라 읽기도 낫다.

2021 년에 멈춘 판이라 웹서비스(논문이 적은 ESRI WFS)는 찾지 않았다. `fetch_petrochron` 이 Zenodo 파일 주소를 1 초 간격으로
두 번 부르고, 원본은 `rawstore` 가 `<PETROCHRON_DIR>/raw/<날짜>/` 에 gzip 으로 둔다 — 판이 같으면 확인한 때만 보탠다.
굽는 법을 고치면 `--offline` 으로 받지 않고 다시 굽는다. cron 에 두지 않는다(`sources.seed.json` 의 `manual`).

## 점은 분석 한 줄마다

시료 하나에 전암·광물·연대가 여러 줄일 수 있다(같은 시료 번호 1 117 개가 겹친다). 시료로 묶어 한 점에 모으는 것을 견주었다가
**버렸다** — 시료 번호가 논문마다 따로 매겨져 같은 번호가 다른 시료일 수 있고(`Me3/3` 17 줄), 묶는 순간 어느 줄의 연대가
어느 광물의 것인지 팝업에서 흐려진다. 줄마다 점이고, 겹친 점은 팝업이 함께 보인다(4 383 자리).

## 팝업 — 시료 번호·암석·연대(방법)·주성분·참고문헌

- **암석**은 `rock_group · rock_type · rock_name · rock_description` 을 이은 것, **층서 이름**은 층서·기반 지괴
- **연대**는 `age_ma ± age_2sd_ma (2σ)`, **연대 방법**은 계(U-Th-Pb 따위)·광물·기법·셈법·뜻(결정화·변성·냉각·모형)을 잇는다.
  모형 연대(T_DM)도 뜻이 함께 적혀 있어 섞이지 않는다
- **주성분**은 SiO₂·TiO₂·Al₂O₃·Fe₂O₃t·Fe₂O₃·FeO·MgO·CaO·Na₂O·K₂O 가운데 값이 있는 것을 한 줄로. 광물 분석(흑운모·저어콘 따위
  — 전암이 아닌 307 줄, 주성분이 있는 것은 70 남짓)이면 **분석 대상**을 적는다 — 그 주성분은 광물의 것이다
- **좌표 출처** — 2 754 줄은 논문에 좌표가 없어 PetroChron 이 SCAR 지명사전의 지명 자리로 어림했다(`not supplied - defined via SCAR
  Gazetteer`). 그 점은 산 하나의 자리일 뿐이라 그대로 보인다. 값은 옮기지 않는다(CLAUDE.md "옮기지 않는 것")
- **DOI** — 표의 참고문헌은 "저자, 해, 제목" 글이다. `.bib` 의 `title`·`doi` 를 제목(글자·숫자만)으로 이어 7 209 줄에 붙였다.
  BibTeX 의 `S{\o}r` 같은 것은 지우고 견준다. 안 맞는 것은 링크 없이 글만

덩이는 7 MB, gzip 으로 0.55 MB 다(`point_layer` 가 gzip). 참고문헌 글이 줄마다 되풀이되지만 압축이 거의 다 걷어 낸다.

## 색 — 암석 갈래, 마름모

극지연구소 암석 시료(`kopri.ROCK_CLASSES`)와 **같은 색 다섯**(퇴적·화산·심성·변성·그 밖)이고 모양만 마름모다. 둘을 함께 켜면
색의 뜻이 같고 모양으로 출처를 가른다. 레이어군 "암석 화학·연대 (PetroChron)" 은 차례 19 — 극지연구소 시료(20) 바로 위다.
극지연구소 레이어군에 넣지 않은 것은 이름이 "극지연구소 시료" 라서다.

## 하지 않은 것 — 연속값 색 (TODOs 의 "다음")

부탁은 성분·연대로 칠하는 것(`style: value`, 그린란드 지화학 wetherilli 159·163)까지였다. 사용자가 clear-conversation 세션을 거쳐 "크게 번지는 몫은
TODOs 로" 라 해서 이번에는 갈래 색까지만 했다. 해 보며 본 것을 적어 둔다 —
- 값이 있는 열은 SiO₂ 8 228·Rb 8 340·Sr 8 427 줄, 연대 2 560, 모형 물성(밀도 7 365·P파 7 711·열 생산 4 055)
- 전암만 값으로 써야 한다 — 광물 분석의 SiO₂ 71 줄이 섞이면 분위수가 틀어진다
- `thermal_conductivity` 는 4.586–4.599 로 사실상 한 값이라 칠할 뜻이 없다
- ε_Nd 는 음수가 흔하다(265/408) — 우리 틀은 음수를 "검출 한계 밑" 으로 읽으니 넣지 않는다. 미량 원소의 음수(Rb −0.3)는 그 뜻 그대로다
- 동위원소 비·Mg# 는 단위가 없어 범례 이름(`valueLabel` 의 괄호)을 손봐야 한다. 고르개 이름 "칠할 원소" 도 연대에는 맞지 않는다
- 점이 1 만 1 천이고 열이 70 남짓이라 그린란드 전암처럼 `slice` 로 고른 열만 자를 것이다

## 정적 판

싣지 않았다. 조건(CC BY 4.0)은 열려 있지만 정적 판은 구워 둔 덩이를 `static_site.UPSTREAMS` 로 고르고, 이 레이어는 서버가 굽는
파일이라 판 굽기에 한 손이 더 든다. 맡은 일을 넓히지 않으려고 미뤘다 — 실을 때는 `points/petrochron/samples.json` 을 구워 넣으면 된다.
