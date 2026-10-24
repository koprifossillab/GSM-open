# 연구소 망이 다시 서명한 잎 — 파이썬 3.13+ 의 엄격 검사만 푼다

2026-10-24 · `fix/quakes-strict-ssl` · wetherilli

## 무엇이 멈췄나

운영(v1.4.0) healthz 에 `fetch_recent_quakes 가 실패했다: … CERTIFICATE_VERIFY_FAILED … Missing Authority Key Identifier` 가 떴다.

- 이 명령은 컨테이너가 아니라 **호스트 cron 의 `run.sh` venv** 에서 돈다. 그 venv 는 호스트 파이썬 3.14 로 지어진다.
  웹 컨테이너는 `python:3.12-slim` 이라 같은 요청이 된다 — 컨테이너 안에서 견주어 보았다.
- 연구소 망의 검사 장비가 `earthquake.usgs.gov` 를 "KOPRI SSL" 로 다시 서명한다. CA 자체(`deploy/ca/`)는 SKI·AKI·
  `CA:TRUE` 를 다 갖췄는데, **장비가 지어 내는 잎에는 SAN 하나뿐**이고 AKI 가 없다(`openssl s_client -showcerts` 로 확인).
- 파이썬 3.13 부터 `ssl.create_default_context()` 가 `VERIFY_X509_STRICT` 를 켜고, urllib3 2.x 의 `create_urllib3_context` 도
  "3.13+ 면 똑같이" 켠다. RFC 5280 이 요구하는 AKI 가 없으니 OpenSSL 이 거절한다. 같은 venv 에서 그 플래그 하나만 빼면 통과했다.

즉 CA 를 고쳐 끼워서는 풀리지 않는다 — 잎은 장비가 그때그때 짓는다. 장비 설정은 우리 손에 없다.

## 고친 것

`viewer/tls.py` 한 곳.

- **이 기계가 믿는 꾸러미(`CA_BUNDLE`·`EXTRA_CA`)에 가로채는 CA(`INTERCEPT_CAS = ("KOPRI SSL",)`)가 들 때만**
  `VERIFY_X509_STRICT` 를 끈다. 체인 검증·호스트 이름 검사·믿는 꾸러미는 그대로 — 3.12 와 같은 검사다.
- 문 여든다섯이 저마다 `requests.get(..., verify=settings.CA_BUNDLE or True)` 를 부른다. 백 군데를 고치지 않으려고
  `apps.py` 의 `ready()` 가 `tls.install()` 로 urllib3 가 기본 컨텍스트를 짓는 함수(`urllib3.util.ssl_` 와 그것을 제 이름으로
  가져간 `urllib3.connection`)를 감싸고, requests 가 import 때 지어 두는 certifi 컨텍스트에도 같은 것을 건다.
  호스트의 명령도 `manage.py` 를 거치니 같은 자리를 탄다.
- 손으로 컨텍스트를 짓는 문 둘(`kopri._LiveAdapter`·`linked._Pinned`)은 `tls.context()` 를 쓴다.
- `tools/gsmpack/gsmpack/net.py` 는 GSM 을 import 하지 않는 패키지라 같은 규칙을 몇 줄로 따로 적었다(시스템 꾸러미에
  그 CA 가 들 때만). 연구소 노트북에서 3.13+ 로 `--direct` 굽기를 하면 같은 데서 멈췄을 것이다.

시험(`test_tls`)은 openssl 로 "KOPRI SSL" CA 와 AKI 없는 잎을 지어 로컬 https 를 띄운다 — 받아지는지, 이름이 다른
CA 면 3.13+ 의 엄격 검사가 그대로인지, 이름만 같고 키가 다른 CA 로는 멈추는지(검증을 끄지 않았는지)를 본다.

## 버린 것

- **`verify=False`** — 검증을 끄면 가로채는 쪽과 진짜 공격을 가리지 못한다. 처음부터 뺐다.
- **그 CA 가 서명한 체인에만 엄격 검사를 풀기** — 가장 좁지만 파이썬 `ssl` 에는 체인마다 플래그를 바꿀 검증 콜백이 없다.
  엄격하게 맞춘 뒤 실패하면 느슨하게 다시 붙는 길은 결국 모든 호스트에 느슨한 길을 여는 것이라 좁아지지 않고 연결만 두 번이 된다.
  대신 **기계 단위**로 갈랐다 — 가로채는 CA 를 믿는 기계는 어차피 그 장비 뒤에 있고, 장비를 그냥 지나가는 호스트의
  진짜 인증서에는 3.12 의 검사가 걸린다. 망 밖(CI·GitHub Pages 를 굽는 곳·남의 기계)에서는 아무것도 바뀌지 않는다.
- **호스트 venv 를 3.12 로 묶기**(`GSM_SCRIPTS_PYTHON`) — 당장은 풀리지만 웹 이미지가 3.13 으로 오르는 날 모든 상류가
  같은 자리에서 멈춘다. 고칠 자리는 코드 한 곳이 낫다.
- **문마다 `Session` 을 두고 어댑터를 끼우기** — 바른 꼴이지만 여든다섯 문을 다 고쳐야 하고 새 문이 빠뜨리기 쉽다.
  urllib3 함수를 감싸는 것은 urllib3 의 안쪽 이름에 기대는 값이다 — urllib3 가 그 이름을 바꾸면 `test_tls` 가 깨져 알려 준다.
  다만 CI 는 3.12 라 거기서는 엄격 검사가 애초에 없어 그냥 지나간다 — 3.14 인 로컬 venv(`~/venv/GSM`)에서 돌려야 지킨다.
