from django.conf.urls import url

from corehq.motech.fhir.views import get_view

urlpatterns = [
    url(r'^fhir/R4/(?P<resource_type>\w+)/(?P<resource_id>\w+)$', get_view, name="fhir_get_view"),
]
