from django.urls import re_path as url

from corehq.apps.analytics.views import (
    GreenhouseCandidateView,
    HubspotClickDeployView,
    submit_hubspot_cta_form,
    webpack_testing_view,
)

urlpatterns = [
    url(r'^hubspot/click-deploy/$', HubspotClickDeployView.as_view(), name=HubspotClickDeployView.urlname),
    url(r'^greenhouse/candidate/$', GreenhouseCandidateView.as_view(), name=GreenhouseCandidateView.urlname),
    url(r'^hubspot/submit-cta/$', submit_hubspot_cta_form, name="submit_hubspot_cta_form"),
    url(r'^webpack/$', webpack_testing_view, name="analytix_webpack_testing_view"),
]
