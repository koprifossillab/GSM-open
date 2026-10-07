"""URL 뿌리.

서브패스(`GSM/`)를 여기 한 곳에서만 붙인다. 앱의 `viewer/urls.py` 는
접두사를 모른다 — nginx 가 어디에 걸든 앱은 그대로 돌아야 한다.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

prefix = settings.URL_PREFIX

urlpatterns = [
    path(prefix, include("viewer.urls")),
]
# admin 은 연구소 안에서만 — 밖에 연 판(`GSM_PUBLIC`)에서는 경로째 뺀다 (#381 검토 3). 데이터소스 명세를 고치는 창구라 staff 계정이
# 오가는데 아직 평문 HTTP 다 — HTTPS 는 나중에(사람, 2026-10-07)
if not settings.PUBLIC:
    urlpatterns.append(path(f"{prefix}admin/", admin.site.urls))
