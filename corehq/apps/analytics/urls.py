from django.conf.urls import url
from corehq.apps.analytics.views import HubspotClickDeployView, GreenHouseCandidate

urlpatterns = [
    url(r'^hubspot/click-deploy/$', HubspotClickDeployView.as_view(), name=HubspotClickDeployView.urlname),
    url(r'^greenhouse/candidate/$', GreenHouseCandidate.as_view(), name=GreenHouseCandidate.urlname)
]
