from django.conf.urls import re_path as url

from .views import MapView

urlpatterns = [
    url(r'^map/$', MapView.as_view(), name=MapView.urlname),
]
