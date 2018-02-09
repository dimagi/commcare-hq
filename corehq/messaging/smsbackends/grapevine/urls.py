from __future__ import absolute_import
from django.conf.urls import include, url
from .models import GrapevineResource

gvi_resource = GrapevineResource()

urlpatterns = [
    url(r'^api/', include(gvi_resource.urls)),
]
