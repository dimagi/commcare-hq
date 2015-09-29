
from django.conf.urls import *

urlpatterns = patterns('',
    url(r'^(?P<download_id>[0-9a-fA-Z]{25,32})$', 'soil.views.retrieve_download', name='retrieve_download'),
    url(r'^ajax/(?P<download_id>[0-9a-fA-Z]{25,32})$', 'soil.views.ajax_job_poll', name='ajax_job_poll'),
    url(r'^demo/$', 'soil.views.demo', name='soil_demo'),
    url(r'^heartbeat/$', 'soil.views.heartbeat_status', name='soil_heartbeat'),
)
