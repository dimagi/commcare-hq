from django.utils.decorators import method_decorator
from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher, datespan_default
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions

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
        return super(EditDataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None):
        return request.couch_user.can_edit_data(domain)
