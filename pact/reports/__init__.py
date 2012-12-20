import dateutil
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from corehq.apps.reports.standard import CustomProjectReport
from pact.utils import case_script_field

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


class ESSortableMixin(object):
    default_sort = None

    def format_date(self, date_string, format="%m/%d/%Y"):
        try:
            date_obj = dateutil.parser.parse(date_string)
            return date_obj.strftime(format)
        except:
            return date_string

    @property
    def es_results(self):
        """
        Main meat - run your ES query and return the raw results here.
        """
        raise NotImplementedError("ES Query not implemented")


    def get_sorting_block(self):
        res = []

        #the NUMBER of cols sorting
        sort_cols = int(self.request.GET['iSortingCols'])
        if sort_cols > 0:
            for x in range(sort_cols):
                col_key = 'iSortCol_%d' % x
                sort_dir = self.request.GET['sSortDir_%d' % x]
                col_id = int(self.request.GET[col_key])
                col = self.headers.header[col_id]
                if col.prop_name is not None:
                    sort_dict = {col.prop_name: sort_dir}
                    res.append(sort_dict)
        if len(res) == 0 and self.default_sort is not None:
            res.append(self.default_sort)
        return res


    @property
    def total_records(self):
        """
            Override for pagination.
            Returns an integer.
        """
        print "getting total records"
        res = self.es_results
        if res is not None:
            return res['hits'].get('total', 0)
        else:
            return 0

    @property
    def shared_pagination_GET_params(self):
        """
        Override the params and applies all the params of the originating view to the GET
        so as to get sorting working correctly with the context of the GET params
        """
        print "shared pagination!"
        ret = []
        for k,v in self.request.GET.items():
            ret.append(dict(name=k, value=v))
        return ret



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


def query_per_case_submissions_facet(domain, username=None, limit=100):
    """
    Xform query to get count facet by case_id
    """
    query = {
        "facets": {
            "case_submissions": {
                "terms": {
#                    "field": "form.case.case_id",
                    "script_field": case_script_field()['script_case_id']['script'],
                    "size": limit
                },
                "facet_filter": {
                    "and": [
                        {
                            "term": {
                                "domain.exact": domain
                            }
                        }
                    ]
                }
            }
        },
        "size": 0
    }

    if username is not None:
        query['facets']['case_submissions']['facet_filter']['and'].append({ "term": { "form.meta.username": username } })
    return query
