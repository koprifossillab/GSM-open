"""템플릿마다 실리는 차림 — 숨길 화면과 형제 화면의 입구 (wetherilli P19·446)."""

from django.conf import settings


def profile(request) -> dict:
    return {"hide": {name: True for name in settings.HIDDEN_SCREENS}, "siblings": settings.SIBLINGS}
