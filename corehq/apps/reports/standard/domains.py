from corehq.elastic import es_query
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.dispatcher import BasicReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from django.utils.translation import ugettext as _
from corehq.apps.reports.util import numcell
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from corehq.util.dates import iso_string_to_datetime
from corehq.util.view_utils import absolute_reverse


def format_date(dstr, default):
    if dstr:
        return iso_string_to_datetime(dstr).strftime('%Y/%m/%d %H:%M:%S')
    else:
        return default


class DomainStatsReport(GenericTabularReport):
    dispatcher = BasicReportDispatcher
    asynchronous = True
    section_name = 'DOMSTATS'
    base_template = "reports/async/bootstrap2/default.html"
    custom_params = []
    es_queried = False

    name = ugettext_noop('Domain Statistics')
    slug = 'dom_stats'

    def get_domains(self):
        return getattr(self, 'domains', [])

    def get_name_or_link(self, d, internal_settings=False):
        if not getattr(self, 'show_name', None):
            reverse_str = "domain_homepage" if not internal_settings else "domain_internal_settings"
            return mark_safe('<a href="%s">%s</a>' %
                             (absolute_reverse(reverse_str, args=[d['name']]), d.get('hr_name') or d['name']))
        else:
            return d['name']

    @property
    def es_results(self):
        if not getattr(self, 'es_response', None):
            self.es_query()
        return self.es_response

    def es_query(self):
        if not self.es_queried:
            results = es_domain_query(domains=[d.name for d in self.get_domains()])
            self.es_queried = True
            self.es_response = results
        return self.es_response

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Project", prop_name="name.exact"),
            DataTablesColumn(_("# Active Mobile Workers"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_active_cc_users",
                help_text=_("The number of mobile workers who have submitted a form in the last 30 days")),
            DataTablesColumn(_("# Mobile Workers"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_cc_users"),
            DataTablesColumn(_("# Active Cases"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_active_cases",
                help_text=_("The number of cases modified in the last 120 days")),
            DataTablesColumn(_("# Cases"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_cases"),
            DataTablesColumn(_("# Form Submissions"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_forms"),
            DataTablesColumn(_("First Form Submission"), prop_name="cp_first_form"),
            DataTablesColumn(_("Last Form Submission"), prop_name="cp_last_form"),
            DataTablesColumn(_("# Web Users"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_web_users"),
        )
        return headers

    @property
    def rows(self):
        domains = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for dom in domains:
            if dom.has_key('name'): # for some reason when using the statistical facet, ES adds an empty dict to hits
                first_form_default_message = _("No Forms")
                if dom.get("cp_last_form", None):
                    first_form_default_message = _("Unable to parse date")

                yield [
                    self.get_name_or_link(dom),
                    numcell(dom.get("cp_n_active_cc_users", _("Not yet calculated"))),
                    numcell(dom.get("cp_n_cc_users", _("Not yet calculated"))),
                    numcell(dom.get("cp_n_active_cases", _("Not yet calculated"))),
                    numcell(dom.get("cp_n_cases", _("Not yet calculated"))),
                    numcell(dom.get("cp_n_forms", _("Not yet calculated"))),
                    format_date(dom.get("cp_first_form"), first_form_default_message),
                    format_date(dom.get("cp_last_form"), _("No forms")),
                    numcell(dom.get("cp_n_web_users", _("Not yet calculated")))
                ]


def es_domain_query(params=None, facets=None, domains=None, start_at=None, size=None, sort=None, fields=None, show_stats=True):
    if params is None:
        params = {}
    terms = ['search']
    if facets is None:
        facets = []
    q = {"query": {"match_all":{}}}

    if domains is not None:
        q["query"] = {
            "in" : {
                "name" : domains,
            }
        }

    q["filter"] = {"and": [
        {"term": {"doc_type": "Domain"}},
        {"term": {"is_snapshot": False}},
    ]}

    search_query = params.get('search', "")
    if search_query:
        q['query'] = {
            "bool": {
                "must": {
                    "match" : {
                        "_all" : {
                            "query" : search_query,
                            "operator" : "and", }}}}}

    q["facets"] = {}
    if show_stats:
        stats = ['cp_n_active_cases', 'cp_n_inactive_cases', 'cp_n_active_cc_users', 'cp_n_cc_users',
                 "cp_n_users_submitted_form", 'cp_n_60_day_cases', 'cp_n_web_users', 'cp_n_forms', 'cp_n_cases']
        for prop in stats:
            q["facets"].update({"%s-STATS" % prop: {"statistical": {"field": prop}}})

    q["sort"] = sort if sort else [{"name" : {"order": "asc"}},]

    return es_query(params, facets, terms, q, DOMAIN_INDEX + '/hqdomain/_search', start_at, size, fields=fields)
