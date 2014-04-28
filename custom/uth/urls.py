from django.conf.urls.defaults import *

from custom.uth.views import vscan_upload

urlpatterns = patterns(
    'custom.uth.views',
    url(r'^vscan_upload', vscan_upload, name='vscan_upload'),
)
