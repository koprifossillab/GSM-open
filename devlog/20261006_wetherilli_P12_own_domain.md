# 고유 주소 — 정적 판에 우리 도메인과 소개·출처 화면을 (계획)

2026-10-06 · `main`(계획) · wetherilli

사용자: "earththrutime.nopeoplestime.info/about 참고해서 우리가 고유의 페이지 주소를 만드는 게 어떨지 생각해보자",
"P 문서만 작성해줘". 지금 밖에 열린 주소는 `https://koprifossillab.github.io/GSM-open/`(P11·162) 하나다.

## 1. ETT 는 어떻게 했나 (2026-10-06 에 읽었다)

EarthThruTime3D(`github.com/jikhanjung/EarthThruTime3D`, `deploy/README.md`·`deploy.toml`·`LICENSE-DATA.md`) —

- **주소**는 `earththrutime.nopeoplestime.info` 다. 사 둔 도메인의 하위 도메인이고 DNS 는 WordPress.com 이 맡는다
- **연구실 밖의 서버**(`dolfinid`)에서 Docker 컨테이너를 `127.0.0.1:8014` 에 띄우고, 호스트 nginx 가
  Let's Encrypt HTTPS 를 붙여 넘긴다. 같은 서버에 다른 서비스도 산다
- **`/about/`** 에 무엇·누가·자료 출처와 인용·코드 라이선스(MIT)와 자료 라이선스(따로 `LICENSE-DATA.md`)·
  문제 신고·개인정보("가입·로그인·업로드 없음, 쿠키는 언어만")·GitHub 링크를 한 쪽에 둔다
- **공개 조건을 코드가 막는다** — `SCOTESE_SOURCE_MAPS_PUBLIC=false` 면 원본 지도 길이 404 이고, 빌드 검사가
  이미지에 원본이 없는지·떠 있는 컨테이너가 내보내지 않는지 재 본다
- ETT 는 **인증키가 걸린 상류가 없다.** 그래서 밖에 서버를 두는 것만으로 끝났다

## 2. 정한 것

**우리는 서버를 밖에 두지 않고, 이미 있는 정적 판에 우리 도메인을 붙인다.** 밖의 서버는 이 계획 밖이다(§6).

까닭 — ETT 를 그대로 따라 밖에 서버를 두면 셋이 한꺼번에 걸린다.

1. **우리 키로 모든 사람에게 내주게 된다.** KIGAM·VWorld 키 하나와 서버 IP 하나에 바깥의 호출이 다 몰리고,
   막히면 연구소 운영판도 같이 멈춘다(devlog 010, `docs/정적_밖_경로.md` §3). 정적 판은 각자 키를 넣어
   이것이 없다(wetherilli 174)
2. **캐시가 재배포가 된다.** CLAUDE.md "우리는 받은 것을 다시 내주지 않는다" 와 부딪힌다. 정적 판은 브라우저가
   상류를 곧장 부르므로 우리가 내주는 것은 우리 코드와 우리가 구운 것뿐이다
3. **공개 스위치가 반쪽이다.** `GSM_PUBLIC=1` 은 연구실 내부용(`views.LAB_ONLY`)만 뺀다. 비상업·판매 조건의
   상류(EOX·Esri·CGMW·SGB·INGEMMET·IIGE·BUMIGEB …)는 남는다. 정적 판은 `static_site.py` 의
   `REGIONS`·`UPSTREAMS`·`OPTIONAL` 이 이미 그 거름을 맡고 있다

ETT 에서 가져오는 것은 **주소와 소개 쪽**이다 — 출처·조건·개인정보·신고 길을 한 화면에 모은다.

## 3. 사람이 정할 것 (작업 전에)

- **도메인 이름.** 후보는 둘이다
  - 새 도메인 — `greatstonemap.org` 따위. 2026-10-06 에 `dig` 로 `greatstonemap.org`·`.com` 의 NS 가 없었다.
    비었다는 확인은 아니다 — 등록처에서 본다
  - 팀 도메인의 하위 — `gsm.paleobytes.info` 따위. 그 도메인의 주인(ETT 쪽)에게 묻는다
- **누가 사고 갱신하나** — 연구실 계정인지 사람 개인인지. 갱신을 놓치면 주소가 남의 손에 간다
- **`github.io/GSM-open/` 을 어떻게 하나** — Pages 는 사용자 도메인을 붙이면 옛 주소를 새 주소로 넘긴다.
  이슈 #129 와 README 의 링크를 새 주소로 고친다

## 4. 단계

`feature/own-domain` 하나에서, 단계마다 커밋·devlog.

1. **앞머리를 뿌리로** — 지금 정적 판은 `/GSM-open/` 밑에 구워진다(`static_site.py --prefix`, 기본 `/GSM-open/`).
   사용자 도메인은 뿌리(`/`)다. 기본값을 바꾸고, `publish_pages.sh` 가 도메인을 받아 `--prefix /` 로 굽게 한다.
   화면이 짓는 주소 가운데 `/GSM-open/` 을 박아 둔 곳이 없는지 본다
2. **`CNAME` 파일** — `publish_pages.sh` 가 gh-pages 한 커밋에 `CNAME`(도메인 한 줄)을 함께 싣는다. gh-pages 를
   판마다 통째로 덮으므로 이것을 빼먹으면 Pages 설정의 도메인이 풀린다
3. **DNS·HTTPS** — 사람이 등록처에서 `CNAME koprifossillab.github.io`(하위 도메인) 또는 Pages 의 A 레코드 넷
   (맨 도메인)을 걸고, GSM-open 의 Settings → Pages → Custom domain 에 적고 "Enforce HTTPS" 를 켠다.
   GitHub 의 도메인 확인(TXT)도 걸어 남이 그 도메인을 가로채지 못하게 한다
4. **VWorld 키를 새 도메인에서 잰다** — VWorld 키는 신청 때 적은 도메인에 묶인다. 각자 넣는 키가 새 도메인에서
   도는지 한 번 재고, 안내 글(키 넣는 칸)에 "이 도메인을 적어 신청한다" 를 적는다. KIGAM 키도 같이 잰다
   (`docs/정적_밖_경로.md` §2.2 가 못 잰 것)
5. **소개 화면의 "출처와 조건"** — `intro.html` 의 "출처" 장면을 ETT 의 `/about/` 처럼 키운다
   - 상류마다 기관·조건(CC BY·공공 도메인·OGL·비상업…)·인용. 손으로 적지 않고 정적 판에 실린
     `UPSTREAMS` 에서 뽑는다 — 실린 것과 적힌 것이 어긋나지 않게
   - 코드는 AGPL-3.0, 소스는 GSM-open(`settings.SOURCE_URL`). 자료는 상류마다 제 조건이라는 한 줄
   - **개인정보** — 가입·로그인 없음. 키·개인 레이어·연결 레이어는 그 브라우저(localStorage·IndexedDB)에만 있고
     우리에게 오지 않는다. 상류는 브라우저가 곧장 부르므로 상류가 IP 를 본다
   - **신고 길** — GSM-open 의 이슈
   - 영어도 같은 커밋에 (`i18n.py`)
6. **조건을 시험이 지킨다** — ETT 의 빌드 검사처럼, 정적 판에 실린 상류 가운데 조건 칸이 비었거나 비상업·판매인
   것이 있으면 `static_site.py` 가 멈추게 한다(`OPTIONAL` 로 사람이 고른 것은 그 조건을 소개 화면에 적고 통과).
   기본 배경이 EOX(비상업)·Esri 인 지역(그린란드·얀마옌·북극·남극)은 정적 판에서 조건이 열린 배경
   (GIBS·PGC 음영)으로 기본값을 바꾼다
7. **판 세션의 절차** — CLAUDE.md "라이선스"·"인증키" 절과 HANDOFF 의 주소를 새 도메인으로 고친다

## 5. 걸리는 것

- Pages 의 사용자 도메인은 **저장소 하나에 하나**다. GSM-open 이 곧 그 도메인이 된다
- 앞머리를 바꾸면 이미 퍼진 `github.io/GSM-open/#r=…` 공유 링크는 Pages 가 넘겨주는 동안만 산다 — 해시는
  넘김에 실려 간다
- 도메인 값(해마다 1–2 만 원 남짓)은 사람이 낸다

## 6. 하지 않는 것 — 밖의 서버

ETT 처럼 밖에 서버를 두고 Docker Hub 이미지(`koprifossillab/gsm`)를 띄우는 것은 **이번에 하지 않는다.**
할 때가 오면 같은 도메인을 그쪽으로 돌리면 된다. 그 전에 풀 것 — 공개용 KIGAM·VWorld 키를 따로 받기,
`GSM_PUBLIC` 이 조건이 닫힌 상류까지 빼게 키우기, 캐시를 공개 판에서 끄거나 조건이 열린 상류만 담기,
`<DB 옆>` 파일(GeoMAP·온 지구 따위)을 밖으로 옮길 묶음과 해시(ETT 의 `pack_data.py`·`manifest.json`).
그때 따로 P 문서를 쓴다.
