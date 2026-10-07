# 판을 띄운 뒤 옛 이미지를 정리한다

2026-10-07 · `feature/prune-old-images` · koprifossillab

## 왜

판이 하루 두세 번(많은 날은 여섯 번) 오르고 이미지는 판마다 쌓인다 — 10-07 `koprifossillab/gsm` 이 11개였다. 개발·운영이 한 서버라 루트 SSD 를 같이 쓴다(koprifossillab 021 에서 94% 를 60% 로 비웠다). 사람이 정했다: 정규 배포 과정에 넣고 최근 2~3개만 남긴다.

## 무엇을

`deploy/release.sh deploy` — healthz 가 새 판을 말한 뒤에만 `prune_old_images koprifossillab/gsm <새 판> <앞 판>`.

- 앞 판은 갈아 띄우기 전에 돌던 컨테이너의 이미지 태그에서 읽는다(되돌리기에 쓴다).
- 만든 시각으로 최근 3개 + 그 둘 + 컨테이너가 쓰는 이미지는 남긴다. 못 지운 것은 경고만, 정리 실패가 판 내기를 실패로 만들지 않는다.
- `PRUNE_DRY_RUN=1` 이면 목록만, `PRUNE_KEEP=0` 이면 건너뛴다.
- 규약은 kopri-devdocs `guides/web/deployment.md §5.1`.

## 확인

`bash -n` 통과. dry-run: 11개 중 v0.74.0(운영) 외 최근 것을 남기고 8개가 대상. 지우지는 않았다.
