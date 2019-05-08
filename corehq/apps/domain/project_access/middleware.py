from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta

from django.utils.deprecation import MiddlewareMixin
from corehq.apps.domain.project_access.models import SuperuserProjectEntryRecord, ENTRY_RECORD_FREQUENCY
from corehq.util.quickcache import quickcache
from corehq.apps.users.tasks import update_domain_date


class ProjectAccessMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(request, 'couch_user', None) and request.couch_user.is_superuser \
                and hasattr(request, 'domain'):
            return self.record_entry(request.domain, request.couch_user.username)
        if getattr(request, 'couch_user', None) and request.couch_user.is_web_user() \
                and hasattr(request, 'domain'):
            self.record_web_user_entry(request.couch_user, request.domain)

    @quickcache(['domain', 'username'], timeout=ENTRY_RECORD_FREQUENCY.seconds)
    def record_entry(self, domain, username):
        if not SuperuserProjectEntryRecord.entry_recently_recorded(username, domain):
            SuperuserProjectEntryRecord.record_entry(username, domain)
        return None

    @staticmethod
    def record_web_user_entry(user, domain):
        yesterday = datetime.today() - timedelta(hours=24)
        if domain not in user.domains_accessed or user.domains_accessed[domain] < yesterday:
            update_domain_date.delay(user, domain)
