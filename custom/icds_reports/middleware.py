from django.utils.deprecation import MiddlewareMixin

from corehq import toggles
from corehq.sql_db.routers import use_citus_for_request
from corehq.apps.users.models import CouchUser
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.models import ICDSAuditEntryRecord
from custom.icds_reports.urls import DASHBOARD_URL_GROUPS

exclude_urls = (
    'have_access_to_location',
    'icds-ng-template',
    'locations'
)

AUDIT_URLS = frozenset(
    [url.name for url in DASHBOARD_URL_GROUPS if hasattr(url, 'name') and url.name not in exclude_urls] + [
        'icds_dashboard',
    ]
)


# function to check that path contains correct view to Audit.
# the most important in the path is the value on the 4th or 5th place because this is the view name or sub-view
# example path: /a/domain/icds-dashboard-view-name/sub-view
# after split we get ['', 'a', 'domain', 'icds-dashboard-view-name', 'sub-view']
def is_path_in_audit_urls(request):
    path = getattr(request, 'path', '').split('/')
    return len(path) > 3 and (path[3] in AUDIT_URLS or (len(path) > 4 and path[4] in AUDIT_URLS))


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
                use_citus_for_request()

    def process_response(self, request, response):
        if is_icds_dashboard_view(request):
            ICDSAuditEntryRecord.create_entry(request, response)
        elif is_login_page(request) and request.user.is_authenticated and is_icds_domain(request):
            couch_user = CouchUser.get_by_username(request.user.username)
            ICDSAuditEntryRecord.create_entry(request, response, couch_user, is_login_page=True)
        return response
