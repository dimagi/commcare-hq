from django.conf.urls import *

urlpatterns = patterns('custom.apps.wisepill.views',
    url(r'^device/?$', 'device_data', name='wisepill_device_event'),
    url(r'^export/events/', 'export_events', name='export_wisepill_events'),
)
