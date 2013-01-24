from corehq.apps.crud.dispatcher import BaseCRUDAdminInterfaceDispatcher
from corehq.apps.reports.dispatcher import ProjectReportDispatcher

class ADMSectionDispatcher(ProjectReportDispatcher):
    prefix = 'adm_section'
    map_name = 'ADM_SECTIONS'

    def dispatch(self, request, *args, **kwargs):
        return super(ADMSectionDispatcher, self).dispatch(request, *args, **kwargs)

    @classmethod
    def pattern(cls):
        base = r'^(?:{renderings}/)?(?P<report_slug>[\w_]+)/(?:(?P<subreport_slug>[\w_]+)/)?$'
        return base.format(renderings=cls._rendering_pattern())

class ADMAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'adm_admin_interface'
    map_name = "ADM_ADMIN_INTERFACES"
