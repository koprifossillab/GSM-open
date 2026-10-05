"""판을 다시 띄워도 남는 기록 (wetherilli 351).

컨테이너를 다시 띄우면 `docker logs` 가 사라진다 — 판마다 그렇다. 그래서 접근 기록(gunicorn)과 앱 기록(gunicorn 오류·Django)을
**붙어 있는 자리**(`GSM_LOG_DIR`, 컨테이너는 `<DB 옆>/logs`)에도 하루 한 장씩 적는다. 화면(`docker logs`)에 내던 것은 그대로 낸다.

- 이름은 `<앞머리>-YYYYMMDD.log` 이다. 날이 바뀌면 새 장을 연다 — 돌려 쓰지(rotate) 않는다. 워커 셋이 한 장에 `O_APPEND` 로 한 줄씩 쓰므로
  프로세스끼리 이름을 바꾸다 부딪힐 일이 없다
- **크기 한도** — 한 장이 `max_bytes` 를 넘으면 그날은 더 적지 않고, 넘었다는 줄을 한 번 남긴다
- **지우는 날** — 새 장을 열 때 `keep_days` 보다 오래된 같은 앞머리의 장을 지운다
- **키·주소는 남기지 않는다** — 줄마다 `redact()` 를 거친다. 연결 레이어의 주소(`url=`)에 남의 키가 인코딩돼 들어 있을 수 있어 그것도 지운다

Django 를 import 하지 않는다 — gunicorn 마스터가 앱을 싣기 전에 부른다.
"""
import datetime
import logging
import os
import re
import threading
from pathlib import Path

#: 값을 지울 질의 변수 — 이름에 key·token 이 들거나 비밀인 것. 인코딩된 꼴(`%3D`·`%26`)도 본다
_SECRET_RE = re.compile(
    r"((?:[?&;\s\"]|%3F|%26|^)[A-Za-z_\-]*(?:key|token|secret|password|passwd|whoami|signature|sig|auth)[A-Za-z_\-]*(?:=|%3D))"
    r"(?:(?!%26)[^&\s\"])*",
    re.I)


def redact(text: str) -> str:
    """키처럼 보이는 질의 값을 `…` 로 바꾼다"""
    return _SECRET_RE.sub(r"\1…", text or "")


class RedactFilter(logging.Filter):
    """화면(`docker logs`)으로 가는 줄에도 같은 지우기를 건다 — 줄을 미리 지어 바꿔 넣는다"""

    def filter(self, record):
        try:
            text = record.getMessage()
        except Exception:
            return True
        clean = redact(text)
        if clean != text:
            record.msg, record.args = clean, None
        return True


class DailyFile(logging.Handler):
    """하루 한 장, 크기 한도와 지우는 날이 있는 기록 손잡이. 여러 프로세스가 같은 자리에 써도 된다"""

    def __init__(self, directory, prefix, keep_days=30, max_bytes=50 * 1024 * 1024, today=None):
        super().__init__()
        self.directory = Path(directory)
        self.prefix = prefix
        self.keep_days = int(keep_days)
        self.max_bytes = int(max_bytes)
        self._today = today or datetime.date.today      # 시험이 날을 바꾼다
        self._day = None
        self._fd = None
        self._full = False
        self._guard = threading.Lock()

    def path_for(self, day: datetime.date) -> Path:
        return self.directory / f"{self.prefix}-{day:%Y%m%d}.log"

    def _open(self, day):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
        self._fd, self._day, self._full = None, day, False
        self.directory.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(self.path_for(day), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
        self._prune(day)

    def _prune(self, day):
        """같은 앞머리의 장 가운데 `keep_days` 보다 오래된 것을 지운다 — 다른 워커가 먼저 지웠어도 괜찮다"""
        oldest = day - datetime.timedelta(days=self.keep_days)
        for path in self.directory.glob(f"{self.prefix}-*.log"):
            stamp = path.stem[len(self.prefix) + 1:]
            try:
                if datetime.datetime.strptime(stamp, "%Y%m%d").date() < oldest:
                    path.unlink()
            except (ValueError, OSError):
                continue

    def emit(self, record):
        try:
            line = redact(self.format(record)).replace("\n", "\n  ") + "\n"
            data = line.encode("utf-8", "replace")
            with self._guard:
                day = self._today()
                if day != self._day or self._fd is None:
                    self._open(day)
                size = os.fstat(self._fd).st_size
                if size + len(data) > self.max_bytes:
                    if not self._full:
                        self._full = True
                        os.write(self._fd, f"-- 오늘의 한도 {self.max_bytes // (1024 * 1024)} MB 를 넘어 더 적지 않는다 (pid {os.getpid()})\n".encode())
                    return
                os.write(self._fd, data)
        except Exception:
            self.handleError(record)

    def close(self):
        with self._guard:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
        super().close()


def handler(prefix: str, fmt: str):
    """`GSM_LOG_DIR` 가 있으면 그 자리의 손잡이를, 없으면 None. 한도·지우는 날은 `GSM_LOG_MAX_MB`·`GSM_LOG_KEEP_DAYS`"""
    directory = os.environ.get("GSM_LOG_DIR", "").strip()
    if not directory:
        return None
    h = DailyFile(directory, prefix,
                  keep_days=int(os.environ.get("GSM_LOG_KEEP_DAYS") or 30),
                  max_bytes=int(float(os.environ.get("GSM_LOG_MAX_MB") or 50) * 1024 * 1024))
    h.setFormatter(logging.Formatter(fmt))
    return h
