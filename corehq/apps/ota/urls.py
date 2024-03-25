from django.urls import re_path as url

from corehq.apps.hqadmin.views.users import DomainAdminRestoreView
from corehq.apps.ota.views import (
    app_aware_search,
    claim,
    get_next_id,
    heartbeat,
    recovery_measures,
    restore,
    search,
    case_fixture,
    case_restore,
)

urlpatterns = [
    url(r'^restore/$', restore, name='ota_restore'),
    url(r'^admin_restore/$', DomainAdminRestoreView.as_view(), name=DomainAdminRestoreView.urlname),
    url(r'^admin_restore/(?P<app_id>[\w-]+)/$', DomainAdminRestoreView.as_view()),
    url(r'^restore/(?P<app_id>[\w-]+)/$', restore, name='app_aware_restore'),
    url(r'^search/$', search, name='remote_search'),
    url(r'^search/(?P<app_id>[\w-]+)/$', app_aware_search, name='app_aware_remote_search'),
    url(r'^claim-case/$', claim, name='claim_case'),
    url(r'^heartbeat/(?P<app_build_id>[\w-]+)/$', heartbeat, name='phone_heartbeat'),
    url(r'^get_next_id/$', get_next_id, name='get_next_id'),
    url(r'^recovery_measures/(?P<build_id>[\w-]+)/$', recovery_measures, name='recovery_measures'),
    url(r'^registry_case/(?P<app_id>[\w-]+)/$', case_fixture),
    url(r'^case_fixture/(?P<app_id>[\w-]+)/$', case_fixture, name='case_fixture'),
    url(r'^case_restore/(?P<case_id>[\w\-]+)/$', case_restore, name='case_restore'),
]
