from django.conf.urls import url

from corehq.motech.fhir.views import (
    SmartAuthView,
    SmartTokenView,
    get_view,
    search_view,
    smart_configuration_view,
    smart_metadata_view,
)

urlpatterns = [
    url(r'^fhir/(?P<fhir_version_name>\w+)/(?P<resource_type>\w+)/$', search_view, name="fhir_search"),
    url(r'^fhir/(?P<fhir_version_name>\w+)/(?P<resource_type>\w+)/(?P<resource_id>[\w\-]+)/$', get_view,
        name="fhir_get_view"),
    url(
        r'^fhir/(?P<fhir_version_name>\w+)/.well-known/smart-configuration',
        smart_configuration_view,
        name="smart_configuration_view"
    ),
    url(r'^fhir/(?P<fhir_version_name>\w+)/metadata', smart_metadata_view, name="smart_metadata_view"),


    url(r'^oauth/login', SmartAuthView.as_view(), name=SmartAuthView.urlname),
    url(r'^oauth/token', SmartTokenView.as_view(), name=SmartTokenView.urlname),
]
