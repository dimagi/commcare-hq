from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from custom.icds.views import CCZDownloadView

urlpatterns = [
    url(r'^cas_files/(?P<identifier>[\w-]+)/', CCZDownloadView.as_view(), name='cas_ccz_download'),
]
