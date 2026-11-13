"""템플릿마다 실리는 차림 — 숨길 화면과 형제 화면의 입구(wetherilli P19·446), 덧붙이의 화면 파일(447), 차림의 얼굴(453)."""

from django.conf import settings

from . import addons


def profile(request) -> dict:
    from . import i18n
    return {"hide": {name: True for name in settings.HIDDEN_SCREENS}, "siblings": settings.SIBLINGS,
            "addon_assets": addons.screen_assets(), "brand": addons.brand(i18n.lang_of(request))}
