from django.conf.urls import url

from corehq.motech.dhis2.views import DataSetMapView, send_dhis2_data

urlpatterns = [
    url(r'^map/$', DataSetMapView.as_view(), name=DataSetMapView.urlname),
    url(r'^send/$', send_dhis2_data, name='send_dhis2_data'),
]
