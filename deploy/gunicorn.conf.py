"""gunicorn 설정 — 기록을 붙은 자리에도 남긴다 (wetherilli 351).

화면(`docker logs`)에는 그대로 내고(키처럼 보이는 값은 둘 다 지운다), `GSM_LOG_DIR` 가 있으면 하루 한 장씩 그 자리에도 적는다(`gsmweb.logfiles`) — 판을 다시 띄워도 남게.
접근 기록은 `access-YYYYMMDD.log`, gunicorn 오류는 Django 의 앱 기록과 같은 `app-YYYYMMDD.log` 다. 워커·스레드·시간 한계는
`entrypoint-web.sh` 의 명령줄에 둔다.
"""
import logging
import os
import sys


def on_starting(server):
    """마스터가 워커를 띄우기 전 — 여기서 단 손잡이를 워커가 물려받는다"""
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    if here not in sys.path:
        sys.path.insert(0, here)
    from gsmweb import logfiles

    # 화면으로 가는 접근 기록에도 — 연결 레이어의 주소에 남의 키가 들 수 있다
    for name in ("gunicorn.access", "gunicorn.error"):
        logging.getLogger(name).addFilter(logfiles.RedactFilter())
    access = logfiles.handler("access", "%(message)s")
    if access is None:
        return
    logging.getLogger("gunicorn.access").addHandler(access)
    logging.getLogger("gunicorn.error").addHandler(
        logfiles.handler("app", "%(asctime)s [%(process)d] %(levelname)s gunicorn %(message)s"))
    server.log.info("기록을 %s 에도 남긴다", os.environ["GSM_LOG_DIR"])
