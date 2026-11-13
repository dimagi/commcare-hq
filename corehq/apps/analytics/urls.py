from django.urls import re_path as url

from corehq.apps.analytics.views import (
    GreenhouseCandidateView,
    submit_hubspot_cta_form,
)

urlpatterns = [
    url(r'^greenhouse/candidate/$', GreenhouseCandidateView.as_view(), name=GreenhouseCandidateView.urlname),
    url(r'^hubspot/submit-cta/$', submit_hubspot_cta_form, name="submit_hubspot_cta_form"),
]
