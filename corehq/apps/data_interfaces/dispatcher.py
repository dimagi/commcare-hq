from django.utils.decorators import method_decorator

from django_prbac.utils import has_privilege

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.reports.dispatcher import ReportDispatcher, datespan_default
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from custom.icds.view_utils import check_data_interfaces_blocked_for_domain

require_can_edit_data = require_permission(Permissions.edit_data)

require_form_management_privilege = requires_privilege_with_fallback(privileges.DATA_CLEANUP)


class EditDataInterfaceDispatcher(ReportDispatcher):
    prefix = 'edit_data_interface'
    map_name = 'EDIT_DATA_INTERFACES'

    @method_decorator(require_can_edit_data)
    @method_decorator(check_data_interfaces_blocked_for_domain)
    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        from corehq.apps.case_importer.base import ImportCases
        from .interfaces import BulkFormManagementInterface

        if kwargs['report_slug'] == ImportCases.slug:
            return self.bulk_import_case_dispatch(request, *args, **kwargs)
        elif (kwargs['report_slug'] == BulkFormManagementInterface.slug and
              not kwargs.get('skip_permissions_check')):
            return self.bulk_form_management_dispatch(request, *args, **kwargs)

        return super(EditDataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    @method_decorator(requires_privilege_with_fallback(privileges.BULK_CASE_MANAGEMENT))
    def bulk_import_case_dispatch(self, request, *args, **kwargs):
        return super(EditDataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    @method_decorator(require_form_management_privilege)
    def bulk_form_management_dispatch(self, request, *args, **kwargs):
        return super(EditDataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        if is_navigation_check:
            from corehq.apps.case_importer.base import ImportCases
            from corehq.apps.data_interfaces.interfaces import BulkFormManagementInterface
            report_name = report.split('.')[-1]
            if report_name == ImportCases.__name__:
                if not has_privilege(request, privileges.BULK_CASE_MANAGEMENT):
                    return False
            if report_name == BulkFormManagementInterface.__name__:
                if not has_privilege(request, privileges.DATA_CLEANUP):
                    return False
        return request.couch_user.can_edit_data(domain)
