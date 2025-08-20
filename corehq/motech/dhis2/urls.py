from django.urls import re_path as url
from corehq.apps.hqwebapp.decorators import waf_allow

from corehq.motech.dhis2.views import (
    DataSetMapCreateView,
    DataSetMapListView,
    DataSetMapUpdateView,
    DataSetMapJsonCreateView,
    DataSetMapJsonEditView,
    send_dataset_now,
)

urlpatterns = [
    url(r'^map/$', DataSetMapListView.as_view(),
        name=DataSetMapListView.urlname),
    url(r'^map/json/add/$', DataSetMapJsonCreateView.as_view(),
        name=DataSetMapJsonCreateView.urlname),
    url(r'^map/json/(?P<pk>\w+)/$', DataSetMapJsonEditView.as_view(),
        name=DataSetMapJsonEditView.urlname),
    url(r'^map/add/$', DataSetMapCreateView.as_view(),
        name=DataSetMapCreateView.urlname),
    url(r'^map/(?P<pk>\w+)/$', waf_allow('XSS_BODY')(DataSetMapUpdateView.as_view()),
        name=DataSetMapUpdateView.urlname),
    url(r'^send/(?P<pk>[\w-]+)/$', send_dataset_now, name='send_dataset_now'),
]
