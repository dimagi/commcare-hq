from django.conf.urls import patterns, url
from corehq.apps.analytics.views import HubspotClickDeployView, ABTestSetupView, ABTestListView

urlpatterns = patterns('corehq.apps.analytics.views',
    url(r'^hubspot/click-deploy/$', HubspotClickDeployView.as_view(), name=HubspotClickDeployView.urlname),
    url(r'^ab-test/create$', ABTestSetupView.as_view(), name=ABTestSetupView.urlname),
    url(r'^ab-test/$', ABTestListView.as_view(), name=ABTestListView.urlname)
)
