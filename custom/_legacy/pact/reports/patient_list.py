from django.core.urlresolvers import  NoReverseMatch
from django.utils import html

from corehq.apps.api.es import ReportCaseES, ReportXFormES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.users.models import CommCareUser
from corehq.elastic import SIZE_LIMIT
from pact.enums import PACT_DOMAIN, PACT_HP_CHOICES, PACT_DOT_CHOICES, PACT_CASE_TYPE
from pact.reports import PactElasticTabularReportMixin
from pact.reports.dot import PactDOTReport
from pact.reports.patient import PactPatientInfoReport
from pact.utils import query_per_case_submissions_facet


class PactPrimaryHPField(BaseSingleOptionFilter):
    slug = "primary_hp"
    label = "PACT HPs"
    default_text = "All CHWs"

    @property
    def options(self):
        chws = list(self.get_chws())
        return [(c['val'], c['text']) for c in chws]


    @classmethod
    def get_chws(cls):
        users = CommCareUser.by_domain(PACT_DOMAIN)
        for x in users:
            #yield dict(val=x._id, text=x.raw_username)
            yield dict(val=x.raw_username, text=x.raw_username)
#        self.options = [dict(val=case['_id'], text="(%s) - %s" % (case['pactid'], case['name'])) for case in patient_cases]


class HPStatusField(BaseSingleOptionFilter):
    slug = "hp_status"
    label = "HP Status"
    default_text = "All Active HP"
    ANY_HP = "any_hp"

    @property
    def options(self):
        options = [(self.ANY_HP, "All Active HP")]
        options.extend(PACT_HP_CHOICES)
        return options


class DOTStatus(BaseSingleOptionFilter):
    slug = "dot_status"
    label = "DOT Status"
    default_text = "All"
    ANY_DOT = "any_dot"

    @property
    def options(self):
        options = [(self.ANY_DOT, "Any DOT")]
        options.extend(PACT_DOT_CHOICES[:3])
        return options


class PatientListDashboardReport(PactElasticTabularReportMixin):
    name = "All Patients"
    slug = "patients"
    ajax_pagination = True
    asynchronous = True
    default_sort = {"pactid": "asc"}
    report_template_path = "reports/async/bootstrap2/tabular.html"
    flush_layout = True

    fields = [
        'pact.reports.patient_list.PactPrimaryHPField',
        'pact.reports.patient_list.HPStatusField',
        'pact.reports.patient_list.DOTStatus',
    ]
    case_es = ReportCaseES(PACT_DOMAIN)
    xform_es = ReportXFormES(PACT_DOMAIN)

    def get_pact_cases(self):
        query = self.case_es.base_query(start=0, size=None)
        query['fields'] = ['_id', 'name', 'pactid.#value']
        results = self.case_es.run_query(query)
        for res in results['hits']['hits']:
            yield res['fields']

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("PACT ID", prop_name="pactid.#value"),
            DataTablesColumn("Name", prop_name="name", sortable=False, span=3),
            DataTablesColumn("Primary HP", prop_name="hp.#value"),
            DataTablesColumn("Opened On", prop_name="opened_on"),
            DataTablesColumn("Last Modified", prop_name="modified_on"),
            DataTablesColumn("HP Status", prop_name="hp_status.#value"),
            DataTablesColumn("DOT Status", prop_name='dot_status.#value'),
            DataTablesColumn("Status", prop_name="closed"),
            DataTablesColumn("Submissions", sortable=False),
        )
        return headers

    def case_submits_facet_dict(self, limit):
        query = query_per_case_submissions_facet(self.request.domain, limit=limit)
        results = self.xform_es.run_query(query)
        case_id_count_map = {}
        for f in results['facets']['case_submissions']['terms']:
            case_id_count_map[f['term']] = f['count']
        return case_id_count_map


    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        def _format_row(row_field_dict):
            yield row_field_dict.get("pactid.#value", '---').replace('_', ' ').title()
            yield self.pact_case_link(row_field_dict['_id'], row_field_dict.get("name", "---")),
            yield row_field_dict.get("hp.#value", "---")
            yield self.format_date(row_field_dict.get("opened_on"))
            yield self.format_date(row_field_dict.get("modified_on"))
            yield self.render_hp_status(row_field_dict.get("hp_status.#value"))
            yield self.pact_dot_link(row_field_dict['_id'], row_field_dict.get("dot_status.#value"))
            #for closed on, do two checks:
            if row_field_dict.get('closed', False):
                #it's closed
                yield "Closed (%s)" % self.format_date(row_field_dict.get('closed_on'))
            else:
                yield "Active"

            yield facet_dict.get(row_field_dict['_id'], 0)

        res = self.es_results
        if res.has_key('error'):
            pass
        else:
            #hack, do a facet query here
            facet_dict = self.case_submits_facet_dict(SIZE_LIMIT)
            for result in res['hits']['hits']:
                yield list(_format_row(result['fields']))


    @property
    def es_results(self):
        fields = [
            "_id",
            "name",
            "pactid.#value",
            "opened_on",
            "modified_on",
            "hp_status.#value",
            "hp.#value",
            "dot_status.#value",
            "closed_on",
            "closed"
        ]
        full_query = self.case_es.base_query(terms={'type': PACT_CASE_TYPE}, fields=fields,
                                             start=self.pagination.start,
                                             size=self.pagination.count)
        full_query['sort'] = self.get_sorting_block()

        def status_filtering(slug, field, prefix, any_field, default):
            if self.request.GET.get(slug, None) is not None:
                field_status_filter_query = self.request.GET[slug]

                if field_status_filter_query == "":
                    #silly double default checker here - set default or the any depending on preference
                    field_status_filter_query = default

                if field_status_filter_query is None:
                    return
                else:
                    if field_status_filter_query.startswith(prefix):
                        field_status_prefix = field_status_filter_query
                    elif field_status_filter_query == any_field:
                        field_status_prefix = prefix
                    else:
                        field_status_prefix = None
                        full_query['filter']['and'].append({"term": {field: field_status_filter_query.lower()}})

                    if field_status_prefix is not None:
                        field_filter = {"prefix": {field: field_status_prefix.lower()}}
                        full_query['filter']['and'].append(field_filter)

        status_filtering(DOTStatus.slug, "dot_status.#value", "DOT", DOTStatus.ANY_DOT, None)
        status_filtering(HPStatusField.slug, "hp_status.#value", "HP", HPStatusField.ANY_HP, HPStatusField.ANY_HP)

        #primary_hp filter from the user filter
        if self.request.GET.get(PactPrimaryHPField.slug, "") != "":
            primary_hp_term = self.request.GET[PactPrimaryHPField.slug]
            primary_hp_filter = {"term": {"hp.#value": primary_hp_term}}
            full_query['filter']['and'].append(primary_hp_filter)
        return self.case_es.run_query(full_query)


    def pact_case_link(self, case_id, name):
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(
                    PactPatientInfoReport.get_url(*[self.domain]) + "?patient_id=%s" % case_id),
                html.escape(name),
                ))
        except NoReverseMatch:
            return "%s (bad ID format)" % name

    def render_hp_status(self, status):
        if status is None or status == '':
            return ''
        else:
            if status.lower() == 'discharged':
                css = 'label'
            else:
                css = 'label label-info'
            return '<span class="%s">%s</span>' % (css, status)


    def pact_dot_link(self, case_id, status):

        if status is None or status == '':
            return ''

        try:
            return html.mark_safe("<span class='label label-info'>%s</span> <a class='ajax_dialog' href='%s'>Report</a>" % (
                html.escape(status),
                html.escape(
                    PactDOTReport.get_url(*[self.domain]) + "?dot_patient=%s" % case_id),
                ))
        except NoReverseMatch:
            return "%s (bad ID format)" % status
