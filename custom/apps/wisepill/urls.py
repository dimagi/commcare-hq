from __future__ import absolute_import
from django.conf.urls import url

from custom.apps.wisepill.views import device_data, export_events

urlpatterns = [
    url(r'^device/?$', device_data, name='wisepill_device_event'),
    url(r'^export/events/', export_events, name='export_wisepill_events'),
]
