from corehq.apps.domain.decorators import cls_require_previewer, cls_require_superusers
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, ReportDispatcher

class ADMSectionDispatcher(ProjectReportDispatcher):
    prefix = 'adm_section'
    map_name = 'ADM_SECTION_MAP'

    @cls_require_previewer
    def dispatch(self, request, *args, **kwargs):
        return super(ADMSectionDispatcher, self).dispatch(request, *args, **kwargs)

    @classmethod
    def pattern(cls):
        return r'^((?P<render_as>[(json)|(async)|(filters)|(export)|(static)|(clear_cache)]+)/)?(?P<report_slug>[\w_]+)/((?P<subreport_slug>[\w_]+)/)?$'

class ADMAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'adm_admin_interface'
    map_name = "ADM_ADMIN_INTERFACE_MAP"

    @cls_require_superusers
    def dispatch(self, request, *args, **kwargs):
        return super(ADMAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)