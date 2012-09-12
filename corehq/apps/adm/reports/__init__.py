from corehq.apps.adm import utils
from corehq.apps.adm.dispatcher import ADMSectionDispatcher
from corehq.apps.adm.models import REPORT_SECTION_OPTIONS
from corehq.apps.reports.generic import GenericReportView

class ADMSectionView(GenericReportView):
    section_name = "Active Data Management"
    app_slug = "adm"
    dispatcher = ADMSectionDispatcher

    # adm-specific stuff
    adm_slug = None

    def __init__(self, request, base_context=None, *args, **kwargs):
        adm_sections = dict(REPORT_SECTION_OPTIONS)
        if self.adm_slug not in adm_sections:
            raise ValueError("The adm_slug provided, %s, is not in the list of valid ADM report section slugs: %s." %
                (self.adm_slug, ", ".join([key for key, val in adm_sections.items()]))
            )
        self.subreport_slug = kwargs.get("subreport_slug")
        print "SUBREPORT SLUG", self.subreport_slug
        super(ADMSectionView, self).__init__(request, base_context, *args, **kwargs)


    @property
    def show_subsection_navigation(self):
        return utils.show_adm_nav(self.domain, self.request)