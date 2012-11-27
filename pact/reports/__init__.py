from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from corehq.apps.reports.standard import CustomProjectReport

class PactPatientDispatcher(CustomProjectReportDispatcher):
    prefix = 'pactpatient'
#    map_name = ''

#    prefix = 'adm_section'
#    map_name = 'ADM_SECTION_MAP'

    def dispatch(self, request, *args, **kwargs):
#        print "PactPatientDispatcher"
        ret =  super(PactPatientDispatcher, self).dispatch(request, *args, **kwargs)
        return ret

    def get_reports(self, domain):
#        print "PactPatientDispatcher get_reports"
#        print self.report_map.get(domain, {})
        return self.report_map.get(domain, {})

#    @classmethod
#    def pattern(cls):
##        base = r'^(?:{renderings}/)?(?P<report_slug>[\w_]+)/(?:(?P<pt_case_id>[\w_]+))/(?:(?P<subreport_slug>[\w_]+)/)?$'
##        print "got pattern"
#        return base.format(renderings=cls._rendering_pattern())


class PactPatientReportMixin(object):
    # this is everything that's shared amongst the Bihar supervision reports
    # this class is an amalgamation of random behavior and is just
    # for convenience

    report_template_path = "pact/patient/pactpatient_info.html"

    hide_filters = True
    flush_layout = True
    #    mobile_enabled = True
    fields = []

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as

    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        return False

    @property
    def report_context(self):
        raise NotImplementedError("Todo")


class PatientNavigationReport(PactPatientReportMixin, CustomProjectReport):
#    dispatcher = PactPatientDispatcher

    @property
    def reports(self):
        # override
        raise NotImplementedError("Override this!")

    @property
    def _headers(self):
        return [" "] * len(self.reports)

