from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.performance_sms.views import (
    ListPerformanceConfigsView,
    AddPerformanceConfigView,
    EditPerformanceConfig,
    EditPerformanceConfigAdvanced,
    delete_performance_config,
    sample_performance_messages,
    send_performance_messages,
)

urlpatterns = [
    url(r'^$', ListPerformanceConfigsView.as_view(),
        name=ListPerformanceConfigsView.urlname),
    url(r'^new/$', AddPerformanceConfigView.as_view(),
        name=AddPerformanceConfigView.urlname),
    url(r'^edit/(?P<config_id>[\w-]+)/$', EditPerformanceConfig.as_view(),
        name=EditPerformanceConfig.urlname),
    url(r'^edit/(?P<config_id>[\w-]+)/advanced/$', EditPerformanceConfigAdvanced.as_view(),
        name=EditPerformanceConfigAdvanced.urlname),
    url(r'^delete/(?P<config_id>[\w-]+)/$', delete_performance_config,
        name='performance_sms.delete_performance_messages'),
    url(r'^sample/(?P<config_id>[\w-]+)/$', sample_performance_messages,
        name='performance_sms.sample_performance_messages'),
    url(r'^send/(?P<config_id>[\w-]+)/$', send_performance_messages,
        name='performance_sms.send_performance_messages'),
]
