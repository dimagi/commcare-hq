from django.conf.urls import re_path as url

from .dispatchers import CaseManagementMapDispatcher
from .views import geospatial_default

urlpatterns = [
    url(r'^$', geospatial_default, name='geospatial_default'),
    CaseManagementMapDispatcher.url_pattern()
]
