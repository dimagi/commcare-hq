from corehq.apps.domain.decorators import cls_require_previewer, cls_require_superusers
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, ReportDispatcher

class ADMProjectReportDispatcher(ProjectReportDispatcher):
    prefix = 'adm_project_report'
    map_name = 'ADM_PROJECT_REPORT_MAP'

    @cls_require_previewer
    def dispatch(self, request, *args, **kwargs):
        return super(ADMProjectReportDispatcher, self).dispatch(request, *args, **kwargs)

class ADMAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'adm_admin_interface'
    map_name = "ADM_ADMIN_INTERFACE_MAP"

    @cls_require_superusers
    def dispatch(self, request, *args, **kwargs):
        return super(ADMAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)