from corehq.apps.appstore.views import fill_mapping_with_facets
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import ElasticTabularReport, GenericTabularReport


class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher
    base_template = "hqadmin/stats_report.html"

class AdminFacetedReport(AdminReport, ElasticTabularReport):
    default_sort = None
    es_prefix = "es_" # facet keywords in the url will be prefixed with this
    asynchronous = False
    ajax_pagination = True
    exportable = True
    es_queried = False
    es_facet_list = []
    es_facet_mapping = []

    @property
    def template_context(self):
        ctxt = super(AdminFacetedReport, self).template_context

        self.run_query() # this runs the es query and populates the necessary attributes

        ctxt.update({
            'layout_flush_content': True,
            'facet_map': self.es_facet_map,
            'query_str': self.request.META['QUERY_STRING'],
            'facet_prefix': self.es_prefix,
            'grouped_facets': True,
        })
        return ctxt

    @property
    def total_records(self):
        return int(self.es_results['hits']['total'])

    def is_custom_param(self, param):
        return param.startswith(self.es_prefix)

    @property
    def shared_pagination_GET_params(self):
        ret = super(AdminFacetedReport, self).shared_pagination_GET_params
        for param in self.request.GET.iterlists():
            if self.is_custom_param(param[0]):
                for val in param[1]:
                    ret.append(dict(name=param[0], value=val))
        return ret

    def es_query(self, params=None):
        raise NotImplementedError

    @property
    def es_results(self):
        if not self.es_queried:
            self.run_query()
        return self.es_response

    def run_query(self):
        from corehq.apps.appstore.views import parse_args_for_es
        self.es_params, _ = parse_args_for_es(self.request, prefix=self.es_prefix)
        results = self.es_query(self.es_params)
        self.es_facet_map = fill_mapping_with_facets(self.es_facet_mapping, results, self.es_params)
        self.es_response = results
        self.es_queried = True
        return self.es_response

    @property
    def export_table(self):
        self.pagination.count = 1000000 # terrible hack to get the export to return all rows
        self.show_name = True
        return super(AdminFacetedReport, self).export_table
