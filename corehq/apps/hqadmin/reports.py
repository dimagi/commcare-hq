from datetime import datetime
from corehq.apps.appstore.views import fill_mapping_with_facets
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import ElasticTabularReport, GenericTabularReport
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.pillows.mappings.user_mapping import USER_INDEX


class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher
    base_template = "hqadmin/faceted_report.html"

class AdminFacetedReport(AdminReport, ElasticTabularReport):
    default_sort = None
    es_prefix = "es_" # facet keywords in the url will be prefixed with this
    asynchronous = False
    ajax_pagination = True
    exportable = True
    es_queried = False
    es_facet_list = []
    es_facet_mapping = []
    section_name = ugettext_noop("ADMINREPORT")

    @property
    def template_context(self):
        ctxt = super(AdminFacetedReport, self).template_context

        self.run_query() # this runs the es query and populates the necessary attributes

        ctxt.update({
            'layout_flush_content': True,
            'facet_map': self.es_facet_map,
            'query_str': self.request.META['QUERY_STRING'],
            'facet_prefix': self.es_prefix,
            'facet_report': self,
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

class AdminUserReport(AdminFacetedReport):
    slug = "user_list"
    name = ugettext_noop('User List')
    facet_title = ugettext_noop("User Facets")
    search_for = ugettext_noop("users...")

    es_facet_list = [
        "is_active",
        "is_staff",
        "is_superuser",
        "domain",
        "doc_type",
    ]

    es_facet_mapping = [
        ("", True, [
            {"facet": "is_active", "name": "Active?", "expanded": True },
            {"facet": "is_superuser", "name": "SuperUser?", "expanded": True },
            {"facet": "is_staff", "name": "Staff?", "expanded": True },
            {"facet": "domain", "name": "Domain", "expanded": True },
            {"facet": "doc_type", "name": "User Type", "expanded": True },
        ]),
    ]

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Username"), prop_name="username.exact"),
            DataTablesColumn(_("Project Spaces")),
            DataTablesColumn(_("Date Joined"), prop_name="date_joined"),
            DataTablesColumn(_("Last Login"), prop_name="last_login"),
            DataTablesColumn(_("Type"), prop_name="doc_type"),
            DataTablesColumn(_("SuperUser?"), prop_name="is_superuser"),
        )
        return headers

    def es_query(self, params=None):
        from corehq.apps.appstore.views import es_query
        if params is None:
            params = {}
        terms = ['search']
        q = {"query": {"match_all":{}}}

        search_query = params.get('search', "")
        if search_query:
            q['query'] = {
                "bool": {
                    "must": {
                        "match" : {
                            "_all" : {
                                "query" : search_query,
                                "operator" : "or", }}}}}

        q["facets"] = {}

        sort = self.get_sorting_block()
        q["sort"] = sort if sort else [{"username.exact" : {"order": "asc"}},]
        start_at=self.pagination.start
        size=self.pagination.count

        return es_query(params, self.es_facet_list, terms, q, USER_INDEX + '/user/_search', start_at, size)

    @property
    def rows(self):
        users = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        def format_date(dstr, default):
            # use [:19] so that only only the 'YYYY-MM-DDTHH:MM:SS' part of the string is parsed
            return datetime.strptime(dstr[:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y/%m/%d %H:%M:%S') if dstr else default

        def get_domains(user):
            if user.get('doc_type') == "WebUser":
                return ", ".join([dm['domain'] for dm in user.get('domain_memberships', [])])
            return user.get('domain_membership', {}).get('domain', _('No Domain Data'))

        for u in users:
            yield [
                u.get('username'),
                get_domains(u),
                format_date(u.get('date_joined'), _('No date')),
                format_date(u.get('last_login'), _('No date')),
                u.get('doc_type'),
                u.get('is_superuser'),
            ]

