from django.conf.urls import patterns, url

from custom.apps.wisepill.views import device_data, export_events

urlpatterns = patterns('custom.apps.wisepill.views',
    url(r'^device/?$', device_data, name='wisepill_device_event'),
    url(r'^export/events/', export_events, name='export_wisepill_events'),
)
