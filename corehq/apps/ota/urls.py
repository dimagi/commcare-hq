from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.ota.views import (
    restore, search, claim, heartbeat, get_next_id,
)
from corehq.apps.hqadmin.views import DomainAdminRestoreView


urlpatterns = [
    url(r'^restore/$', restore, name='ota_restore'),
    url(r'^admin_restore/$', DomainAdminRestoreView.as_view(), name=DomainAdminRestoreView.urlname),
    url(r'^admin_restore/(?P<app_id>[\w-]+)/$', DomainAdminRestoreView.as_view()),
    url(r'^restore/(?P<app_id>[\w-]+)/$', restore, name='app_aware_restore'),
    url(r'^search/$', search, name='remote_search'),
    url(r'^claim-case/$', claim, name='claim_case'),
    url(r'^heartbeat/(?P<app_build_id>[\w-]+)/$', heartbeat, name='phone_heartbeat'),
    url(r'^get_next_id/$', get_next_id, name='get_next_id'),
]
