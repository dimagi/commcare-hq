from django.conf.urls import include, url

from custom.enikshay.reports.views import LocationsView

urlpatterns = [
    url(r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
    url(r'^nikshay/', include("custom.enikshay.integrations.nikshay.urls")),
    url(r'^locations$', LocationsView.as_view(), name='enikshay_locations'),
]
