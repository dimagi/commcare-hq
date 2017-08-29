from django.conf.urls import include, url

from custom.enikshay.views import EpisodeTaskDebugView, EpisodeTaskStatusView
from custom.enikshay.reports.views import LocationsView

urlpatterns = [
    url(r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
    url(r'^bets/', include("custom.enikshay.integrations.bets.urls")),
    url(r'^nikshay/', include("custom.enikshay.integrations.nikshay.urls")),
    url(r'^enikshay_locations$', LocationsView.as_view(), name='enikshay_locations'),
    url(r'^episode_task_debug/(?P<episode_id>[\w-]+)/$', EpisodeTaskDebugView.as_view(),
        name=EpisodeTaskDebugView.urlname),
    url(r'^episode_task_status/$', EpisodeTaskStatusView.as_view(),
        name=EpisodeTaskStatusView.urlname)
]
