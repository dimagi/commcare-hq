from corehq.apps.domain.decorators import cls_require_previewer, cls_require_superusers, cls_domain_admin_required
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, ReportDispatcher

class ADMSectionDispatcher(ProjectReportDispatcher):
    prefix = 'adm_section'
    map_name = 'ADM_SECTION_MAP'

    @cls_domain_admin_required
    def dispatch(self, request, *args, **kwargs):
        return super(ADMSectionDispatcher, self).dispatch(request, *args, **kwargs)

    @classmethod
    def pattern(cls):
        base = r'^(?:{renderings}/)?(?P<report_slug>[\w_]+)/(?:(?P<subreport_slug>[\w_]+)/)?$'
        return base.format(renderings=cls._rendering_pattern())

class ADMAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'adm_admin_interface'
    map_name = "ADM_ADMIN_INTERFACE_MAP"

    @cls_require_superusers
    def dispatch(self, request, *args, **kwargs):
        return super(ADMAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)
