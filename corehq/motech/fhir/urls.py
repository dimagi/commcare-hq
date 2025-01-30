from django.urls import re_path as url

from corehq.motech.fhir.views import (
    get_view,
    search_view,
)

urlpatterns = [
    url(r'^fhir/(?P<fhir_version_name>\w+)/$',
        view=search_view,
        name="fhir_search_multiple_types"),
    url(r'^fhir/(?P<fhir_version_name>\w+)/(?P<resource_type>\w+)/$',
        view=search_view,
        name="fhir_search"),
    url(r'^fhir/(?P<fhir_version_name>\w+)/(?P<resource_type>\w+)/(?P<resource_id>[\w\-]+)/$',
        view=get_view,
        name="fhir_get_view"),
]
