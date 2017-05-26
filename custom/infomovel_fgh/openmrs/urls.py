from django.conf.urls import url

from custom.infomovel_fgh.openmrs.views import (
    OpenmrsRepeaterView,
)

urlpatterns = [
    url(
        r'^new_openmrs_repeater$',
        OpenmrsRepeaterView.as_view(),
        {'repeater_type': 'OpenmrsRepeater'},
        name=OpenmrsRepeaterView.urlname
    ),
]
