from django.conf.urls import url

from corehq.motech.dhis2.views import DataSetMapView, send_dataset_now

urlpatterns = [
    url(r'^map/$', DataSetMapView.as_view(), name=DataSetMapView.urlname),
    url(r'^send/(?P<pk>\w+)/$', send_dataset_now, name='send_dataset_now'),
]
