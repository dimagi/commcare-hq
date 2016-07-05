from django.utils.decorators import method_decorator
from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher, datespan_default
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from django_prbac.utils import has_privilege


require_can_edit_data = require_permission(Permissions.edit_data)

require_form_management_privilege = requires_privilege_with_fallback(privileges.DATA_CLEANUP)


class DataInterfaceDispatcher(ProjectReportDispatcher):
    prefix = 'data_interface'
    map_name = 'DATA_INTERFACES'

    def dispatch(self, request, *args, **kwargs):
        from corehq.apps.reports.standard.export import DeidExportReport
        if kwargs['report_slug'] in [DeidExportReport.slug]:
            return self.deid_dispatch(request, *args, **kwargs)
        return super(DataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    @method_decorator(requires_privilege_with_fallback(privileges.DEIDENTIFIED_DATA))
    def deid_dispatch(self, request, *args, **kwargs):
        return super(DataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        if is_navigation_check:
            from corehq.apps.reports.standard.export import DeidExportReport
            if report.split('.')[-1] in [DeidExportReport.__name__]:
                if not has_privilege(request, privileges.DEIDENTIFIED_DATA):
                    return False
        return super(DataInterfaceDispatcher, self).permissions_check(report, request, domain)


class EditDataInterfaceDispatcher(ReportDispatcher):
    prefix = 'edit_data_interface'
    map_name = 'EDIT_DATA_INTERFACES'

    @method_decorator(require_can_edit_data)
    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        from corehq.apps.importer.base import ImportCases
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
            from corehq.apps.importer.base import ImportCases
            from corehq.apps.data_interfaces.interfaces import BulkFormManagementInterface
            report_name = report.split('.')[-1]
            if report_name == ImportCases.__name__:
                if not has_privilege(request, privileges.BULK_CASE_MANAGEMENT):
                    return False
            if report_name == BulkFormManagementInterface.__name__:
                if not has_privilege(request, privileges.DATA_CLEANUP):
                    return False
        return request.couch_user.can_edit_data(domain)
