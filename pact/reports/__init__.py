import dateutil
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport
from corehq.apps.reports.standard.inspect import ElasticTabularReport


class PactPatientDispatcher(CustomProjectReportDispatcher):
    prefix = 'pactpatient'
    #    map_name = ''

    #    prefix = 'adm_section'
    #    map_name = 'ADM_SECTION_MAP'

    def dispatch(self, request, *args, **kwargs):
        ret =  super(PactPatientDispatcher, self).dispatch(request, *args, **kwargs)
        return ret

    def get_reports(self, domain):
        return self.report_map.get(domain, {})


class PactElasticTabularReportMixin(CustomProjectReport, ElasticTabularReport, ProjectReportParametersMixin):
    def format_date(self, date_string, format="%Y-%m-%d"):
        try:
            date_obj = dateutil.parser.parse(date_string)
            return date_obj.strftime(format)
        except:
            return date_string


class PactDrilldownReportMixin(object):
    # this is everything that's shared amongst the Bihar supervision reports
    # this class is an amalgamation of random behavior and is just
    # for convenience

    report_template_path = ""

    hide_filters = True
    filters = []
    flush_layout = True
    #    mobile_enabled = True
    fields = []
    es_results=None

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as

    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        return False
        #
#    @property
#    def report_context(self):
#        raise NotImplementedError("Todo")




