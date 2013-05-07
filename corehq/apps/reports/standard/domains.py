from django.utils.translation import ugettext_noop
from corehq.apps.domain.calculations import dom_calc, _all_domain_stats, ES_CALCED_PROPS
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
        all_stats = _all_domain_stats()
        domains = self.get_domains()
        for domain in domains:
            dom = getattr(domain, 'name', domain) # get the domain name if domains is a list of domain objects
            yield [
                getattr(domain, 'hr_name', dom), # get the hr_name if domain is a domain object
                int(dom_calc("mobile_users", dom)),
                int(all_stats["commcare_users"][dom]),
                int(dom_calc("cases_in_last", dom, 120)),
                int(all_stats["cases"][dom]),
                int(all_stats["forms"][dom]),
                dom_calc("first_form_submission", dom),
                dom_calc("last_form_submission", dom),
                int(all_stats["web_users"][dom]),
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


def project_stats_facets():
    from corehq.apps.domain.models import Domain, InternalProperties, Deployment, LicenseAgreement
    facets = Domain.properties().keys()
    facets += ['internal.' + p for p in InternalProperties.properties().keys()]
    facets += ['deployment.' + p for p in Deployment.properties().keys()]
    facets += ['cda.' + p for p in LicenseAgreement.properties().keys()]
    for p in ['internal', 'deployment', 'cda', 'migrations', 'eula']:
        facets.remove(p)
    facets += ES_CALCED_PROPS
    return facets

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

    search_query = params.get('search', "")
    if search_query:
        q['query'] = {
            "bool": {
                "must": {
                    "match" : {
                        "_all" : {
                            "query" : search_query,
                            "operator" : "and" }}}}}

    q["facets"] = {}
    stats = ['cp_n_active_cases', 'cp_n_active_cc_users', 'cp_n_cc_users', 'cp_n_web_users', 'cp_n_forms', 'cp_n_cases']
    for prop in stats:
        q["facets"].update({"%s-STATS" % prop: {"statistical": {"field": prop}}})

    q["sort"] = sort if sort else [{"name" : {"order": "asc"}},]

    # la = es_query(params, facets, terms, q, DOMAIN_INDEX + '/hqdomain/_search', start_at, size, dict_only=True)
    # import json
    # print json.dumps(la)
    # print DOMAIN_INDEX + '/hqdomain/_search'

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
            self.es_facets = project_stats_facets()
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
            DataTablesColumn(_("Organization"), prop_name="organization"),
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
        )
        return headers

    @property
    def rows(self):
        domains = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]
        import pprint
        pp = pprint.PrettyPrinter(indent=2)
        pp.pprint(self.es_results.get('facets'))

        calcs_row_index = {
            "cp_n_active_cc_users": 3,
            "cp_n_cc_users": 4,
            "cp_n_active_cases": 5,
            "cp_n_cases": 6,
            "cp_n_forms": 7,
            "cp_n_web_users": 10,
        }
        def get_from_stat_facets(prop, what_to_get):
            return self.es_results.get('facets', {}).get('%s-STATS' % prop, {}).get(what_to_get)

        total_row = ['total', None, None, ]
        for dom in domains:
            if dom.has_key('name'): # for some reason when using the statistical facet, ES adds an empty dict to hits
                yield [
                    dom.get('hr_name') or dom['name'],
                    dom.get("organization") or _('No org'),
                    dom.get('deployment', {}).get('date') or _('No date'),
                    dom.get("cp_n_active_cc_users", _("Not Yet Calculated")),
                    dom.get("cp_n_cc_users", _("Not Yet Calculated")),
                    dom.get("cp_n_active_cases", _("Not Yet Calculated")),
                    dom.get("cp_n_cases", _("Not Yet Calculated")),
                    dom.get("cp_n_forms", _("Not Yet Calculated")),
                    dom.get("cp_first_form", _("No Forms")),
                    dom.get("cp_last_form", _("No Forms")),
                    dom.get("cp_n_web_users", _("Not Yet Calculated")),
                    dom.get('internal', {}).get('notes') or _('No notes'),
                ]
