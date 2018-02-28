from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from custom.up_nrhm.views import asha_af_report

urlpatterns = [
    url(r'^asha_af_report/$', asha_af_report, name='asha_af_report'),
]
