from corehq.apps.domain.decorators import cls_to_view, require_previewer
from corehq.apps.reports.dispatcher import ProjectReportDispatcher

cls_require_previewer = cls_to_view(additional_decorator=require_previewer)

class AdmProjectReportDispatcher(ProjectReportDispatcher):
    prefix = 'adm_project_report'
    map_name = 'ADM_PROJECT_REPORT_MAP'

    @cls_require_previewer
    def dispatch(self, request, *args, **kwargs):
        return super(AdmProjectReportDispatcher, self).dispatch(request, *args, **kwargs)