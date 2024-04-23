from django.urls import include, re_path as url

from corehq.apps.hqwebapp.decorators import waf_allow
from .models import GrapevineResource

gvi_resource = GrapevineResource()

urlpatterns = [
    url(r'^api/', include(gvi_resource.urls)),
]

waf_allow('XSS_BODY', hard_code_pattern=r'^/gvi/api/sms/$')
