from django.urls import re_path as url

from custom.up_nrhm.views import asha_af_report

urlpatterns = [
    url(r'^asha_af_report/$', asha_af_report, name='asha_af_report'),
]
