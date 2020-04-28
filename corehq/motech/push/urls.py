from django.conf.urls import url

from corehq.motech.views import ConnectionSettingsView

urlpatterns = [
    url(r'^conn/$', ConnectionSettingsView.as_view(), name=ConnectionSettingsView.urlname),
]
