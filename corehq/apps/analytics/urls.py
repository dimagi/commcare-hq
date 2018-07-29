from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.analytics.views import HubspotClickDeployView, GreenhouseCandidateView

urlpatterns = [
    url(r'^hubspot/click-deploy/$', HubspotClickDeployView.as_view(), name=HubspotClickDeployView.urlname),
    url(r'^greenhouse/candidate/$', GreenhouseCandidateView.as_view(), name=GreenhouseCandidateView.urlname)
]
