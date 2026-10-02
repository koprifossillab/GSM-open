# 사내 CA 인증서

KOPRI 망은 TLS 를 가로채 자체 CA(`issuer=C=KR, O=KOPRI, CN=KOPRI SSL`)로 다시
서명한다. 호스트에는 `/usr/local/share/ca-certificates/` 에 깔려 있지만 컨테이너
이미지에는 없어서, 없으면 **상류 요청이 전부 멈춘다.**

```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: self-signed certificate in certificate chain'))
```

**이 저장소는 ForGIA 보다 더 아프게 걸린다.** 저쪽은 이미지를 구울 때
`download.pytorch.org` 에서만 막혔지만, 여기는 **돌아가는 내내**
`data.kigam.re.kr` 를 타므로 CA 가 없으면 타일 한 장도 못 받는다.
`gsmweb.settings._default_ca_bundle()` 과 `viewer.kigam._verify()` 가 그 짝이다.

**여기 있는 것은 공개 인증서지 비밀이 아니다.** 다만 이 CA 를 신뢰한다는 것은
KOPRI 프록시가 그 이미지 안의 모든 TLS 를 들여다볼 수 있다는 뜻이다. 사내에서는
어차피 그렇지만, **망 밖에서 이 저장소를 쓴다면 이 디렉토리를 비우면 된다** —
`Dockerfile.web` 은 `.crt` 가 없으면 그냥 넘어가고, 그때는 certifi 꾸러미가 쓰인다.

ForGIA `deploy/ca/README.md` 와 같은 인증서다.
