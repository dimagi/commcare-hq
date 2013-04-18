from django.utils.translation import ugettext_noop
from corehq.apps.domain.calculations import CALC_FNS
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.dispatcher import BasicReportDispatcher, AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
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
                help_text=_("The number of mobile workers who have submitted a form in the last 30 days")),
            DataTablesColumn(_("# Mobile Workers"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# Active Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("The number of cases modified in the last 120 days")),
            DataTablesColumn(_("# Cases"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# Form Submissions"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("First Form Submission")),
            DataTablesColumn(_("Last Form Submission")),
            DataTablesColumn(_("# Web Users"), sort_type=DTSortType.NUMERIC),
            # DataTablesColumn(_("Admins"))
        )
        # headers.no_sort = True
        return headers

    @property
    def rows(self):
        from corehq.apps.hqadmin.views import _all_domain_stats
        all_stats = _all_domain_stats()
        # domains = sorted(self.get_domains())
        domains = self.get_domains()
        for domain in domains:
            dom = getattr(domain, 'name', domain) # get the domain name if domains is a list of domain objects
            yield [
                getattr(domain, 'hr_name', dom), # get the hr_name if domain is a domain object
                int(CALC_FNS["mobile_users"](dom)),
                int(all_stats["commcare_users"][dom]),
                int(CALC_FNS["cases_in_last"](dom, 120)),
                int(all_stats["cases"][dom]),
                int(all_stats["forms"][dom]),
                CALC_FNS["first_form_submission"](dom),
                CALC_FNS["last_form_submission"](dom),
                int(all_stats["web_users"][dom]),
                # [row["doc"]["email"] for row in get_db().view("users/admins_by_domain",
                #                                               key=dom, reduce=False, include_docs=True).all()],
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
    return facets

def es_domain_query(params, facets=None, terms=None, domains=None, return_q_dict=False, start_at=None, size=None):
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

    q["sort"] = [{"name" : {"order": "asc"}},]

    return q if return_q_dict else es_query(params, facets, terms, q, DOMAIN_INDEX + '/hqdomain/_search', start_at, size)

ES_PREFIX = "es_"
class AdminDomainStatsReport(DomainStatsReport):
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

    def get_domains(self):
        self.es_query()
        domains = self.es_domains
        return domains

    @property
    def total_records(self):
        return int(self.es_results['hits']['total'])

    def es_query(self):
        from corehq.apps.appstore.views import parse_args_for_es, generate_sortables_from_facets
        if not self.es_queried:
            self.es_params, _ = parse_args_for_es(self.request, prefix=ES_PREFIX)
            self.es_facets = project_stats_facets()
            self.es_results = es_domain_query(self.es_params, self.es_facets,
                                              start_at=self.pagination.start, size=self.pagination.count)
            self.es_domains = [res['_source']['name'] for res in self.es_results.get('hits', {}).get('hits', [])]
            self.es_sortables = generate_sortables_from_facets(self.es_results, self.es_params, prefix=ES_PREFIX)
            self.es_queried = True

    def is_custom_param(self, param):
        return param.startswith(ES_PREFIX)
