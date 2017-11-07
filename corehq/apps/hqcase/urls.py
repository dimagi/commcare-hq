from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.hqcase.views import explode_cases

urlpatterns = [
    # for load testing
    url(r'explode/', explode_cases, name='hqcase_explode_cases')
]
