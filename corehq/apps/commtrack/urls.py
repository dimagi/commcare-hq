from django.urls import re_path as url

from corehq.apps.commtrack.views import (
    CommTrackSettingsView,
    DefaultConsumptionView,
    SMSSettingsView,
    default,
)

# used in settings urls
settings_urls = [
    url(r'^$', default, name="default_commtrack_setup"),
    url(r'^project_settings/$', CommTrackSettingsView.as_view(), name=CommTrackSettingsView.urlname),
    url(r'^default_consumption/$', DefaultConsumptionView.as_view(), name=DefaultConsumptionView.urlname),
    url(r'^sms/$', SMSSettingsView.as_view(), name=SMSSettingsView.urlname),
]
