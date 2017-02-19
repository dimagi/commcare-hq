from django.conf.urls import url

from custom.icds.views import IndicatorTestPage

urlpatterns = [
    url(r'^icds/sms_indicators$', IndicatorTestPage.as_view(), name=IndicatorTestPage.urlname),
]
