from datetime import datetime
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
import math
from corehq.apps.domain.calculations import dom_calc, _all_domain_stats, ES_CALCED_PROPS
from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.dispatcher import BasicReportDispatcher, AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, ElasticTabularReport
from django.utils.translation import ugettext as _
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX


class DomainStatsReport(GenericTabularReport):
    dispatcher = BasicReportDispatcher
    asynchronous = True
    section_name = 'DOMSTATS'
    base_template = "reports/async/default.html"
    custom_params = []

    name = ugettext_noop('Domain Statistics')
    slug = 'dom_stats'

    def get_domains(self):
        return getattr(self, 'domains', [])

    def is_custom_param(self, param):
        raise NotImplementedError

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Project"),
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
        def numcell(text, value=None):
            if value is None:
                try:
                    value = int(text)
                    if math.isnan(value):
                        text = '---'
                except ValueError:
                    value = text
            return util.format_datatables_data(text=text, sort_key=value)
        all_stats = _all_domain_stats()
        domains = self.get_domains()
        for domain in domains:
            dom = getattr(domain, 'name', domain) # get the domain name if domains is a list of domain objects
            yield [
                getattr(domain, 'hr_name', dom), # get the hr_name if domain is a domain object
                numcell(dom_calc("mobile_users", dom)),
                numcell(all_stats["commcare_users"][dom]),
                numcell(dom_calc("cases_in_last", dom, 120)),
                numcell(all_stats["cases"][dom]),
                numcell(all_stats["forms"][dom]),
                dom_calc("first_form_submission", dom),
                dom_calc("last_form_submission", dom),
                numcell(all_stats["web_users"][dom]),
            ]

    @property
    def shared_pagination_GET_params(self):
        ret = super(DomainStatsReport, self).shared_pagination_GET_params
        for param in self.request.GET.iterlists():
            if self.is_custom_param(param[0]):
                for val in param[1]:
                    ret.append(dict(name=param[0], value=val))
        return ret

class OrgDomainStatsReport(DomainStatsReport):
    def get_domains(self):
        from corehq.apps.orgs.models import Organization
        from corehq.apps.domain.models import Domain
        org = self.request.GET.get('org', None)
        organization = Organization.get_by_name(org, strict=True)
        if organization and \
                (self.request.couch_user.is_superuser or self.request.couch_user.is_member_of_org(org)):
            return [d for d in Domain.get_by_organization(organization.name).all()]
        return []

    def is_custom_param(self, param):
        return param in ['org']

DOMAIN_FACETS = [
    "cp_is_active",
    "cp_has_app",
    "uses reminders",
    "project_type",
    "area",
    "case_sharing",
    "commtrack_enabled",
    "customer_type",
    "deployment.city",
    "deployment.country",
    "deployment.date",
    "deployment.public",
    "deployment.region",
    "hr_name",
    "internal.area",
    "internal.can_use_data",
    "internal.commcare_edition",
    "internal.custom_eula",
    "internal.initiative",
    "internal.project_state",
    "internal.self_started",
    "internal.services",
    "internal.sf_account_id",
    "internal.sf_contract_id",
    "internal.sub_area",
    "internal.using_adm",
    "internal.using_call_center",

    "is_approved",
    "is_public",
    "is_shared",
    "is_sms_billable",
    "is_snapshot",
    "is_test",
    "license",
    "multimedia_included",

    "phone_model",
    "published",
    "sub_area",
    "survey_management_enabled",
    "tags",
]

def es_domain_query(params, facets=None, terms=None, domains=None, return_q_dict=False, start_at=None, size=None, sort=None):
    from corehq.apps.appstore.views import es_query
    if terms is None:
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
                            "operator" : "or" }}}}}

    q["facets"] = {}
    stats = ['cp_n_active_cases', 'cp_n_active_cc_users', 'cp_n_cc_users', 'cp_n_web_users', 'cp_n_forms', 'cp_n_cases']
    for prop in stats:
        q["facets"].update({"%s-STATS" % prop: {"statistical": {"field": prop}}})

    q["sort"] = sort if sort else [{"name" : {"order": "asc"}},]

    return es_query(params, facets, terms, q, DOMAIN_INDEX + '/hqdomain/_search', start_at, size, dict_only=return_q_dict)

ES_PREFIX = "es_"
class AdminDomainStatsReport(DomainStatsReport, ElasticTabularReport):
    default_sort = None
    slug = "domains"
    dispatcher = AdminReportDispatcher
    base_template = "hqadmin/stats_report.html"
    asynchronous = False
    ajax_pagination = True
    es_queried = False
    exportable = True

    @property
    def template_context(self):
        ctxt = super(AdminDomainStatsReport, self).template_context

        self.es_query()

        ctxt.update({
            'layout_flush_content': True,
            'sortables': sorted(self.es_sortables),
            'query_str': self.request.META['QUERY_STRING'],
        })
        return ctxt

    @property
    def total_records(self):
        return int(self.es_results['hits']['total'])

    @property
    def es_results(self):
        if not getattr(self, 'es_response', None):
            self.es_query()
        return self.es_response

    def es_query(self):
        from corehq.apps.appstore.views import parse_args_for_es, generate_sortables_from_facets
        if not self.es_queried:
            self.es_params, _ = parse_args_for_es(self.request, prefix=ES_PREFIX)
            self.es_facets = DOMAIN_FACETS
            results = es_domain_query(self.es_params, self.es_facets, sort=self.get_sorting_block(),
                start_at=self.pagination.start, size=self.pagination.count)
            self.es_sortables = generate_sortables_from_facets(results, self.es_params, prefix=ES_PREFIX)
            self.es_queried = True
            self.es_response = results
        return self.es_response

    def is_custom_param(self, param):
        return param.startswith(ES_PREFIX)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Project"),
            DataTablesColumn(_("Organization"), prop_name="internal.organization_name"),
            DataTablesColumn(_("Deployment Date"), prop_name="deployment.date"),
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
            DataTablesColumn(_("Notes"), prop_name="internal.notes"),
            DataTablesColumn(_("Services"), prop_name="internal.services"),
            DataTablesColumn(_("Project State"), prop_name="internal.project_state"),
        )
        return headers

    @property
    def export_table(self):
        self.pagination.count = 1000000 # terrible hack to get the export to return all rows
        self.show_name = True
        return super(AdminDomainStatsReport, self).export_table


    @property
    def rows(self):
        domains = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        def get_from_stat_facets(prop, what_to_get):
            return self.es_results.get('facets', {}).get('%s-STATS' % prop, {}).get(what_to_get)

        CALCS_ROW_INDEX = {
            3: "cp_n_active_cc_users",
            4: "cp_n_cc_users",
            5: "cp_n_active_cases",
            6: "cp_n_cases",
            7: "cp_n_forms",
            10: "cp_n_web_users",
        }
        NUM_ROWS = 14
        def stat_row(name, what_to_get, type='float'):
            row = [name]
            for index in range(1, NUM_ROWS): #todo: switch to len(self.headers) when that userstatus report PR is merged
                if index in CALCS_ROW_INDEX:
                    val = get_from_stat_facets(CALCS_ROW_INDEX[index], what_to_get)
                    row.append('%.2f' % float(val) if val and type=='float' else val or "not yet calced")
                else:
                    row.append('---')
            return row

        self.total_row = stat_row(_('Total'), 'total', type='int')
        self.statistics_rows = [
            stat_row(_('Mean'), 'mean'),
            stat_row(_('STD'), 'std_deviation'),
        ]

        def format_date(dstr, default):
            return datetime.strptime(dstr, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y/%m/%d %H:%M:%S') if dstr else default

        def get_name_or_link(d):
            if not getattr(self, 'show_name', None):
                return '<a href="%s">%s</a>' % \
                       (reverse("domain_homepage", args=[d['name']]), d.get('hr_name') or d['name'])
            else:
                return d['name']

        for dom in domains:
            if dom.has_key('name'): # for some reason when using the statistical facet, ES adds an empty dict to hits
                yield [
                    get_name_or_link(dom),
                    dom.get("internal", {}).get('organization_name') or _('No org'),
                    format_date(dom.get('deployment', {}).get('date'), _('No date')),
                    dom.get("cp_n_active_cc_users", _("Not Yet Calculated")),
                    dom.get("cp_n_cc_users", _("Not Yet Calculated")),
                    dom.get("cp_n_active_cases", _("Not Yet Calculated")),
                    dom.get("cp_n_cases", _("Not Yet Calculated")),
                    dom.get("cp_n_forms", _("Not Yet Calculated")),
                    format_date(dom.get("cp_first_form"), _("No Forms")),
                    format_date(dom.get("cp_last_form"), _("No Forms")),
                    dom.get("cp_n_web_users", _("Not Yet Calculated")),
                    dom.get('internal', {}).get('notes') or _('No notes'),
                    dom.get('internal', {}).get('services') or _('No info'),
                    dom.get('internal', {}).get('project_state') or _('No info'),
                ]
