from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.deprecation import MiddlewareMixin

from corehq import toggles
from corehq.sql_db.routers import force_citus_engine
from corehq.apps.users.models import CouchUser
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.models import ICDSAuditEntryRecord
from custom.icds_reports.urls import urlpatterns

exclude_urls = (
    'have_access_to_location',
    'icds-ng-template',
    'locations'
)

AUDIT_URLS = frozenset(
    [url.name for url in urlpatterns if hasattr(url, 'name') and url.name not in exclude_urls] + [
        'icds_dashboard',
    ]
)


# function to check that path contains correct view to Audit.
# the most important in the path is the value on the 4th place because this is the view name
# example path: /a/domain/icds-dashboard-view-name
# after split we get ['', 'a', 'domain', 'icds-dashboard-view-name']
def is_path_in_audit_urls(request):
    path = getattr(request, 'path', '').split('/')
    return len(path) >= 3 and path[3] in AUDIT_URLS


def is_login_page(request):
    return 'login' in getattr(request, 'path', '')


def is_icds_domain(request):
    return getattr(request, 'domain', None) == DASHBOARD_DOMAIN


def is_icds_dashboard_view(request):
    return (
        getattr(request, 'couch_user', None) and
        is_icds_domain(request) and
        is_path_in_audit_urls(request)
    )


class ICDSAuditMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if is_icds_dashboard_view(request):
            if toggles.LOAD_DASHBOARD_FROM_CITUS.enabled_for_request(request):
                force_citus_engine()
            ICDSAuditEntryRecord.create_entry(request)
            return None

    def process_response(self, request, response):
        if is_login_page(request) and request.user.is_authenticated and is_icds_domain(request):
            couch_user = CouchUser.get_by_username(request.user.username)
            ICDSAuditEntryRecord.create_entry(request, couch_user, is_login_page=True)
        return response
