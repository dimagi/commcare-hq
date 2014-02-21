from django.utils.decorators import method_decorator
from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_alert
from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher, datespan_default
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege
import toggle

require_can_edit_data = require_permission(Permissions.edit_data)


class DataInterfaceDispatcher(ProjectReportDispatcher):
    prefix = 'data_interface'
    map_name = 'DATA_INTERFACES'


class EditDataInterfaceDispatcher(ReportDispatcher):
    prefix = 'edit_data_interface'
    map_name = 'EDIT_DATA_INTERFACES'

    @method_decorator(require_can_edit_data)
    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        from corehq.apps.importer.base import ImportCases
        if kwargs.get('report_slug') in [ImportCases.slug]:
            return self.bulk_dispatch(request, *args, **kwargs)
        return super(EditDataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    @method_decorator(requires_privilege_alert(privileges.BULK_CASE_MANAGEMENT))
    def bulk_dispatch(self, request, *args, **kwargs):
        return super(EditDataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None):
        if toggle.shortcuts.toggle_enabled(toggles.ACCOUNTING_PREVIEW, request.user.username):
            from corehq.apps.importer.base import ImportCases
            if report.split('.')[-1] in [ImportCases.__name__]:
                try:
                    ensure_request_has_privilege(request, privileges.BULK_CASE_MANAGEMENT)
                except PermissionDenied:
                    return False
        return request.couch_user.can_edit_data(domain)
