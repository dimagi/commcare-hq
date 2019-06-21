from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf.urls import url

from corehq.apps.reports.v2.views import (
    endpoint_data,
    endpoint_options,
)


urlpatterns = [
    url(r'^endpoint/(?P<report_slug>[\w_]+)/data/(?P<endpoint_slug>[\w_-]+)/',
        endpoint_data, name="endpoint_data"),
    url(r'^endpoint/(?P<report_slug>[\w_]+)/config/(?P<endpoint_slug>[\w_-]+)/',
        endpoint_options, name="endpoint_options"),
]
