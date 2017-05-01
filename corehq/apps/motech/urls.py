from django.conf.urls import url
from corehq.apps.motech.views import OpenmrsInstancesMotechView

urlpatterns = [
    url('^openmrs/servers/$',
        OpenmrsInstancesMotechView.as_view(), name=OpenmrsInstancesMotechView.urlname),
]
