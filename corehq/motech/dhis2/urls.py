from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.motech.dhis2.view import Dhis2ConnectionView, DataSetMapView, Dhis2LogListView, \
    Dhis2LogDetailView, send_dhis2_data


urlpatterns = [
    url(r'^conn/$', Dhis2ConnectionView.as_view(), name=Dhis2ConnectionView.urlname),
    url(r'^map/$', DataSetMapView.as_view(), name=DataSetMapView.urlname),
    url(r'^logs/$', Dhis2LogListView.as_view(), name=Dhis2LogListView.urlname),
    url(r'^logs/(?P<pk>\d+)/$', Dhis2LogDetailView.as_view(), name=Dhis2LogDetailView.urlname),
    url(r'^send/$', send_dhis2_data, name='send_dhis2_data'),
]
