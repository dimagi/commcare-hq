from __future__ import absolute_import
from django.conf.urls import include, url

from custom.enikshay.views import (
    EpisodeTaskDebugView,
    EpisodeTaskStatusView,
    ReconciliationTaskView,
)
from custom.enikshay.reports.views import LocationsView, DistrictLocationsView, DuplicateIdsReport

urlpatterns = [
    url(r'^99dots/', include("custom.enikshay.integrations.ninetyninedots.urls")),
    url(r'^bets/', include("custom.enikshay.integrations.bets.urls")),
    url(r'^nikshay/', include("custom.enikshay.integrations.nikshay.urls")),
    url(r'^enikshay_locations$', LocationsView.as_view(), name='enikshay_locations'),
    url(r'^enikshay_district_locations$', DistrictLocationsView.as_view(), name='enikshay_district_locations'),
    url(r'^episode_task_debug/(?P<episode_id>[\w-]+)/$', EpisodeTaskDebugView.as_view(),
        name=EpisodeTaskDebugView.urlname),
    url(r'^episode_task_status/$', EpisodeTaskStatusView.as_view(),
        name=EpisodeTaskStatusView.urlname),
    url(r'^duplicate_ids/voucher/$', DuplicateIdsReport.as_view(),
        {'case_type': 'voucher'}, name='enikshay_duplicate_voucher_ids'),
    url(r'^duplicate_ids/person/$', DuplicateIdsReport.as_view(),
        {'case_type': 'person'}, name='enikshay_duplicate_person_ids'),
    url(r'^reconciliation_tasks/$', ReconciliationTaskView.as_view())
]
