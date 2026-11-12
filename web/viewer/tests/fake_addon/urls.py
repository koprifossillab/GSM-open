from django.http import JsonResponse
from django.urls import path


def ping(request):
    return JsonResponse({"addon": "fake_addon"})


urlpatterns = [path("ping/", ping, name="fake-addon-ping")]
