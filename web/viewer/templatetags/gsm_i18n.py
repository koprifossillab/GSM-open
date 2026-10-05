"""템플릿의 `{% t "한국어 문장" %}`.

번역표는 `viewer/i18n.py` 하나다. 템플릿·JS·서버 메시지가 같은 표를 쓴다.
문장 안에 `<code>`·`<b>` 가 섞일 수 있어 결과를 안전한 것으로 친다 —
표는 우리가 적은 것이고 사람이 넣은 값은 이 태그를 타지 않는다.
"""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from viewer import i18n

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, text, **params):
    """`{% t "… {n} …" n=값 %}` — 자리표의 값은 이스케이프한다(값은 표 밖에서 온다, wetherilli 314)"""
    return mark_safe(i18n.t(text, context.get("lang", "ko"), **{k: escape(v) for k, v in params.items()}))
