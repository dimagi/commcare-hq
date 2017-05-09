from django.conf.urls import url, include
from corehq.apps.motech.views import OpenmrsInstancesMotechView, \
    OpenmrsConceptMotechView

urlpatterns = [
    url('^openmrs/servers/$',
        OpenmrsInstancesMotechView.as_view(), name=OpenmrsInstancesMotechView.urlname),
    url('^openmrs/concepts/$',
        OpenmrsConceptMotechView.as_view(), name=OpenmrsConceptMotechView.urlname),
    url('^openmrs/', include('corehq.apps.motech.openmrs.urls')),
]
