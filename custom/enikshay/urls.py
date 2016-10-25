from django.conf.urls import patterns, include, url

from custom.enikshay.reports.views import LocationsView

urlpatterns = patterns(
    '',
    (r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
    url(r'^locations$', LocationsView.as_view(), name='enikshay_locations'),
)
