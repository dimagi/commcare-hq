from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from soil.views import (
    ajax_job_poll,
    demo,
    heartbeat_status,
    retrieve_download,
)

urlpatterns = [
    url(r'^(?P<download_id>[0-9a-fA-Z]{25,32})$', retrieve_download, name='retrieve_download'),
    url(r'^ajax/(?P<download_id>[0-9a-fA-Z]{25,32})$', ajax_job_poll, name='ajax_job_poll'),
    url(r'^demo/$', demo, name='soil_demo'),
    url(r'^heartbeat/$', heartbeat_status, name='soil_heartbeat'),
]
