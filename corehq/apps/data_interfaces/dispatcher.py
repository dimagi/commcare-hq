from corehq.apps.data_interfaces.views import require_can_edit_data
from corehq.apps.domain.decorators import cls_to_view
from corehq.apps.reports.dispatcher import ReportDispatcher, ProjectReportDispatcher
from corehq.apps.reports.views import datespan_default

cls_require_edit_data = cls_to_view(additional_decorator=require_can_edit_data)

class DataInterfaceDispatcher(ReportDispatcher):
    prefix = 'data_interface'
    map_name = 'DATA_INTERFACE_MAP'

    @cls_require_edit_data
    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        return super(DataInterfaceDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, *args, **kwargs):
        domain = kwargs.get('domain')
        if domain is None:
            domain = args[0]
        return request.couch_user.can_edit_data(domain)

    @classmethod
    def args_kwargs_from_context(cls, context):
        return ProjectReportDispatcher.args_kwargs_from_context(context)