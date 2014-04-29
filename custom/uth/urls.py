from django.conf.urls.defaults import *

from custom.uth.views import vscan_upload, sonosite_upload

urlpatterns = patterns(
    'custom.uth.views',
    url(r'^vscan_upload', vscan_upload, name='vscan_upload'),
    url(r'^sonosite_upload', sonosite_upload, name='sonosite_upload'),
)
