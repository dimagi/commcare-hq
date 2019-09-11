from django.conf.urls import url

from corehq.apps.analytics.views import (
    GreenhouseCandidateView,
    HubspotClickDeployView,
)

urlpatterns = [
    url(r'^hubspot/click-deploy/$', HubspotClickDeployView.as_view(), name=HubspotClickDeployView.urlname),
    url(r'^greenhouse/candidate/$', GreenhouseCandidateView.as_view(), name=GreenhouseCandidateView.urlname)
]
