from django.apps import AppConfig


class ViewerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "viewer"
    verbose_name = "대돌여지도"

    def ready(self):
        _record_fetch_commands()


def _record_fetch_commands():
    """`fetch_*`·`build_*` 명령이 끝날 때 기록 표에 한 줄을 남기게 한다 (jikhanjung P02 2 단계).

    마흔다섯 명령을 하나하나 고치지 않으려고 `BaseCommand.execute` 를 한 자리에서 감싼다. 데이터소스는 명세(`DataSource`)의
    `commands` 로 찾는다(호스트에서는 컨테이너가 옮겨 적을 때) — 명세에 없는 명령은 명령 이름을 데이터소스로 적는다. 명령의 출력은 그대로 흘려보내며 마지막 줄만 기억한다.
    """
    from django.conf import settings
    from django.core.management.base import BaseCommand

    if getattr(BaseCommand.execute, "_gsm_recorded", False):
        return
    original = BaseCommand.execute

    def execute(self, *args, **options):
        name = self.__module__.rsplit(".", 1)[-1]
        if not settings.FETCH_LOG or not self.__module__.startswith("viewer.management.commands.") \
                or not name.startswith(("fetch_", "build_")):
            return original(self, *args, **options)
        import sys

        from . import fetchlog, sources
        row = None
        # 호스트는 GSM.db 를 열지 않는다(P03) — 명세를 읽지 않고 명령 이름을 적어 두면 컨테이너가 옮겨 적을 때 데이터소스로 바꾼다
        if not fetchlog.on_host():
            try:
                row = next((r for r in sources.load().rows if name in r.get("commands", [])), None)
            except Exception:                          # noqa: BLE001 — 명세가 깨져도 명령은 돈다
                row = None
        source, schedule = (row["id"], row["schedule"]) if row else (name, "manual")
        with fetchlog.record(source, name, schedule) as tail:
            tail.out = options.get("stdout") or sys.stdout
            options["stdout"] = tail
            return original(self, *args, **options)

    execute._gsm_recorded = True
    BaseCommand.execute = execute
