from django.conf.urls import patterns, url
from corehq.apps.analytics.views import HubspotClickDeployView

urlpatterns = patterns('corehq.apps.analytics.views',
    url(r'^hubspot/click-deploy/$', HubspotClickDeployView.as_view(), name=HubspotClickDeployView.urlname),
)
