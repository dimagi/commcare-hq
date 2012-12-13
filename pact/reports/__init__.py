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
        if len(res) == 0:
            res.append({
                "received_on": "desc"
            })
        return res


    @property
    def total_records(self):
        """
            Override for pagination.
            Returns an integer.
        """
        res = self.es_results
        if res is not None:
            return res['hits'].get('total', 0)
        else:
            return 0

    @property
    def shared_pagination_GET_params(self):
        """
            Override.
            Should return a list of dicts with the name and value of the GET parameters
            that you'd like to pass to the server-side pagination.
            ex: [dict(name='group', value=self.group_name)]
        """
        ret = []
        for k,v in self.request.GET.items():
            ret.append(dict(name=k, value=v))
        return ret


