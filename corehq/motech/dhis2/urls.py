from django.conf.urls import url

from corehq.motech.dhis2.view import (
    DataSetMapView,
    Dhis2ConnectionView,
    dhis2_edit_config,
    send_dhis2_data,
)
from corehq.motech.repeaters.views.repeaters import AddDhis2RepeaterView

urlpatterns = [
    url(r'^conn/$', Dhis2ConnectionView.as_view(), name=Dhis2ConnectionView.urlname),
    url(r'^map/$', DataSetMapView.as_view(), name=DataSetMapView.urlname),
    url(r'^send/$', send_dhis2_data, name='send_dhis2_data'),
    url(
        r'^new_dhis2_repeater$',
        AddDhis2RepeaterView.as_view(),
        {'repeater_type': 'Dhis2Repeater'},
        name=AddDhis2RepeaterView.urlname
    ),
    url(
        r'^(?P<repeater_id>\w+)/edit_config/$',
        dhis2_edit_config,
        name='dhis2_edit_config',
    )
]
