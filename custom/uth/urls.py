from django.conf.urls.defaults import *

from custom.uth.views import ImageUploadView

urlpatterns = patterns(
    'custom.uth.views',
    url(r'^vscan_upload', ImageUploadView.as_view(), name='vscan_upload'),
)
