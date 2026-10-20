# 자체 러너로 가는 손잡이 — 변수 하나로 고르고, 이미지는 GitHub 에 남긴다

2026-10-20 · `feature/self-hosted-runner` · wetherilli

P15 의 4 단계. 서버 쪽(1–3 단계)은 관리자 세션이 `deploy/host/runner.md` 를 따라 세운다.

## 왜 이렇게

- **`runs-on` 을 저장소 변수로 골랐다**(`vars.GSM_RUNNER && fromJSON(vars.GSM_RUNNER) || 'ubuntu-latest'`). 러너를 세우기 전에
  병합해도 지금과 똑같이 돌고, 서버가 내려가면 변수를 지우면 된다. 딱지를 박아 두면 러너가 없을 때 실행이 하루 동안 줄만 선다
- **`--with-deps` 는 GitHub 러너에서만**(`runner.environment`). 자체 러너는 sudo 가 없다. 시스템 꾸러미는 관리자가 한 번 깐다
- **`--parallel auto` 를 4 로 박았다.** GitHub 러너는 4 코어라 같고, 자체 러너는 systemd 가 4 코어로 묶지만 `auto` 는
  `os.cpu_count()` 로 12 를 본다 — 열두 갈래가 네 코어를 다투면 브라우저 시험이 시간을 넘긴다
- **이미지 굽기는 `ubuntu-latest` 그대로.** docker 무리는 서버의 root 와 같다

## 지켜볼 것

같은 날 GitHub 러너에서 GlobeScreens(지구·달·화성·수성)가 `Page.goto`·`tap` 30 초를 넘겨 깨졌다 — main 의 문서 커밋에서도.
이 서버에서는 47 초에 통과한다. 러너 이미지 판(20261012·20261018)이 섞여 걸렸다. 자체 러너로 옮긴 뒤에도 깨지는지 본다
