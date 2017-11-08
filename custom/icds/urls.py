from __future__ import absolute_import
from django.conf.urls import url

from custom.icds.views import IndicatorTestPage, user_lookup

urlpatterns = [
    url(r'^icds/sms_indicators$', IndicatorTestPage.as_view(), name=IndicatorTestPage.urlname),
    url(r'^icds/user_lookup$', user_lookup, name='icds_user_lookup'),
]
