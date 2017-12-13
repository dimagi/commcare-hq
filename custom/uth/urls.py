from __future__ import absolute_import
from django.conf.urls import url

from custom.uth.views import vscan_upload, sonosite_upload, pending_exams

urlpatterns = [
    url(r'^vscan_upload', vscan_upload, name='vscan_upload'),
    url(r'^sonosite_upload', sonosite_upload, name='sonosite_upload'),
    url(r'^pending_exams/(?P<scanner_serial>[\w-]+)/$', pending_exams, name='pending_exams'),
]
