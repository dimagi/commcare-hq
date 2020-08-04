from django.conf.urls import url

from corehq.motech.views import ConnectionSettingsListView

urlpatterns = [
    url(r'^conn/$', ConnectionSettingsListView.as_view(), name=ConnectionSettingsListView.urlname),
]
