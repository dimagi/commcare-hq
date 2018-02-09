from __future__ import absolute_import
from django.utils.deprecation import MiddlewareMixin
from corehq.apps.domain.project_access.models import SuperuserProjectEntryRecord, ENTRY_RECORD_FREQUENCY
from corehq.util.quickcache import quickcache


class ProjectAccessMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(request, 'couch_user', None) and request.couch_user.is_superuser \
                and hasattr(request, 'domain'):
            return self.record_entry(request.domain, request.couch_user.username)

    @quickcache(['domain', 'username'], timeout=ENTRY_RECORD_FREQUENCY.seconds)
    def record_entry(self, domain, username):
        if not SuperuserProjectEntryRecord.entry_recently_recorded(username, domain):
            SuperuserProjectEntryRecord.record_entry(username, domain)
        return None
