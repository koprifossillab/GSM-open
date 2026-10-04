# 온 지구 — 세계 광상 (USGS MRDS·세계 광상 표)

2026-10-05 · `feature/earth-minerals` · wetherilli

판 세션이 준 일 — USGS 세계 광물 자원 자료(세계 광상 평가와 MRDS 세계판)를 온 지구의 오늘 레이어로, 광종별로 갈라서.

## 두 세션이 겹쳤다

이 세션이 사용량 한도로 멈췄다고 알리자 판 세션이 같은 일(276)을 gsm-91 에 넘겼고, 한도가 풀려 이어 가던 중 **같은 worktree 에서 둘이
함께 썼다**. gsm-91 이 `minerals.py` 를 덮어쓰고 브랜치를 #264 위로 fast-forward 했다. 판 세션이 이쪽에 일을 돌려주어 이렇게 정리했다.

- **모듈은 gsm-91 의 것을 바탕으로 했다** — 골재·석재를 빼는 `SKIP`, 무게(세계 광상 표·대규모는 마름모, 생산한 곳은 큰 원, 산지는
  줌 4 부터), 상세 쪽 링크, 포디폼 크로마이트·희토류 표가 이쪽 판(개발 단계를 색으로, 광상 유형을 따로 한 레이어)보다 낫다
- 이쪽에서 받은 **퇴적암 호스트 납·아연 표**(`sedznpb`, MVT·SEDEX 506 곳)를 더했다 — 유형 이름은 `prevtype` 이 읽힌다(`deptype` 은 부호)
- views·urls·earth.js·i18n 은 둘의 고침이 섞여 있어 HEAD 로 되돌리고 새로 이었다
- 브랜치는 #264 없이 #262 위로 다시 세웠다
- NAS 는 `sources/earth/usgs_minerals/` 하나로 모았다(SHA256SUMS 에 sedznpb 한 줄)

교훈: 한도로 멈출 때 "넘겨도 된다" 고 하면 worktree 도 같이 넘어간다. 이어 가기 전에 브랜치·worktree 를 누가 쓰는지 먼저 본다.

## 자료

| 원본 | 무엇 | 곳 |
|---|---|---|
| `mrds-csv.zip` | MRDS — 산지·광산(미국이 9 할) | 30 만 → 골재·석재를 빼 20 만 |
| `porcu`·`sedcu`·`vms`·`podchrome`·`ree`·`sedznpb` | 세계 광상 표(광량·품위·연대) | 4 700 남짓 |

모두 **공공 도메인**(MRDS 메타데이터의 Access·Use_Constraints: none). 7 초, 75 MB 를 `<EARTH_DIR>/minerals.sqlite` 에.

- 칸 여섯 — 구리·금은백금족·납아연·철과 합금·핵심과 에너지·산업 광물. MRDS 는 첫 광종, 표는 표마다(VMS 는 구리와 납+아연 가운데 큰 쪽)
- 누르는 차례는 지열류 → 응력 → **광상** → 고생태 → 화석. 무겁고 가까운 것부터 다섯
- 미국 탭의 MRDS(`mrdata.py`, USGS 의 WMS)와는 따로다 — 그것은 상류의 그림이고 이것은 온 지구에 우리가 찍는 점이다

## 운영 메모

- 배포 뒤 한 번: `manage.py build_minerals /nfs/temp-share/GSM/sources/earth/usgs_minerals` → `/srv/GSM/db/earth/minerals.sqlite`
- #262(응력) 위에 쌓았다
