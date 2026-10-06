# 시험이 /tmp 에 흘린 것 — tempfile 의 기본 자리를 러너의 임시 자리로

2026-10-06 · `fix/test-tmp-leak` · koprifossillab

## 무엇을 보았나

서버 루트 디스크가 94% 였다. `/tmp` 가 33 GB 였고 그 가운데 **`gsm-static-test-*` 가 707 벌, 한 벌 24 MB 로 17 GB 남짓**이었다
(10-02 부터 06 까지). `test_static_site.built()` 가 `tempfile.mkdtemp()` 에 정적 판을 굽고 지우지 않았다. `--parallel 8` 이면 일꾼마다
한 벌이라 돌릴 때마다 여덟 벌씩 쌓였다. 다른 시험도 같은 버릇이었다 — `/tmp` 에 `gsm-tiles-`·`gsm-geomap-`·`gsm-fossils-` 따위가
**31 만 개**였다. 하나하나는 작지만 inode 를 먹는다.

(같은 날 루트를 함께 비운 것 — `/var/lib/docker` 52 GB 는 `data-root` 를 `/data3/docker` 로 옮기기 전의 옛 저장소였다. 저장소 밖의 일이라 여기 적기만 한다.)

## 왜 러너에서 막았나

시험 파일 아흔아홉이 `mkdtemp()` 를 179 군데에서 쓴다. 하나씩 `addCleanup(shutil.rmtree, …)` 를 붙이는 길도 있었는데 버렸다 —
고칠 자리가 많고, **새 시험이 또 잊으면 그만**이다. 러너(wetherilli 354)는 이미 실행마다 임시 뿌리(`gsm-test-…`)를 만들고 다 돌면 지운다.
`tempfile.tempdir` 과 `TMPDIR` 을 그 안의 `tmp/` 로 돌리면 시험이 무엇을 흘려도 뿌리와 함께 지워진다.

- `TMPDIR` 도 적는 까닭 — 정적 판 시험은 굽기를 **하위 프로세스**로 부른다. spawn 으로 뜨는 일꾼도 환경변수로 물려받는다
- 다 돌면 둘 다 되돌린다 — 러너를 한 프로세스에서 두 번 부르는 경우(시험 러너 자체의 시험)에 앞 판의 지워진 자리를 가리키지 않게
- 러너가 죽으면(강제 종료) 뿌리 하나가 남는다. 전에는 수백 개였으니 그것은 견딘다

## 시험

`test_testrunner` 에 "`mkdtemp()` 가 러너의 자리 안에 만든다" 를 더했다. 정적 판·neotoma·kigam50k·mercurymap 시험을 `--parallel 4` 로
돌리고 `/tmp` 의 항목 수가 그대로인 것(314 194 → 314 194)을 보았다.

이미 쌓인 것은 소유 계정(대부분 sclee)이나 sudo 가 지운다 — `sudo rm -rf /tmp/gsm-*` (돌고 있는 시험이 없을 때).
