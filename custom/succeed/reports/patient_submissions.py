from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from corehq.apps.api.es import ReportXFormES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.users.models import CommCareUser
from custom.succeed.reports import SUBMISSION_SELECT_FIELDS, EMPTY_FIELD, INTERACTION_OUTPUT_DATE_FORMAT
from custom.succeed.reports.patient_details import PatientDetailsReport
from custom.succeed.utils import SUCCEED_DOMAIN
from django.utils import html
from dimagi.utils.decorators.memoized import memoized
from custom.succeed.utils import format_date


class PatientSubmissionReport(PatientDetailsReport):
    slug = "patient_submissions"
    name = 'Patient Submissions'
    xform_es = ReportXFormES(SUCCEED_DOMAIN)
    ajax_pagination = True
    asynchronous = True
    default_sort = {
        "received_on": "desc"
    }

    @property
    def base_template_filters(self):
        return 'succeed/report.html'

    @property
    def fields(self):
        return ['custom.succeed.fields.PatientFormNameFilter',
                'corehq.apps.reports.standard.cases.filters.CaseSearchFilter']

    @property
    def headers(self):
        return DataTablesHeader(
            # In order to get dafault_sort working as expected, first column cannot contain a 'prop_name'.
            DataTablesColumn("", visible=False),
            DataTablesColumn("Form Name", prop_name='@name'),
            DataTablesColumn("Submitted By", prop_name='form.meta.username'),
            DataTablesColumn("Completed", prop_name='received_on'))


    @property
    def es_results(self):
        if not self.request.GET.has_key('patient_id'):
            return None
        full_query = {
            'query': {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": self.request.domain}},
                            {"term": {"doc_type": "xforminstance"}},
                            {
                                "nested": {
                                    "path": "form.case",
                                    "filter": {
                                        "or": [
                                            {
                                                "term": {
                                                    "@case_id": "%s" % self.request.GET[
                                                        'patient_id']
                                                }
                                            },
                                            {
                                                "term": {
                                                    "case_id": "%s" % self.request.GET['patient_id']
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    },
                    "query": {"match_all": {}}
                }
            },
            "sort": self.get_sorting_block(),
            "size": self.pagination.count,
            "from": self.pagination.start
        }

        form_name_group = self.request.GET.get('form_name_group', None)
        form_name_xmnls = self.request.GET.get('form_name_xmlns', None)
        search_string = SearchFilter.get_value(self.request, self.domain)

        if search_string:
            query_block = {"queryString": {"query": "*" + search_string + "*"}}
            full_query["query"]["filtered"]["query"] = query_block

        if form_name_group and form_name_xmnls == '':
            xmlns_terms = []
            forms = filter(lambda obj: obj['val'] == form_name_group, SUBMISSION_SELECT_FIELDS)[0]
            for form in forms['next']:
                xmlns_terms.append(form['val'])

            full_query['query']['filtered']['filter']['and'].append({"terms": {"xmlns.exact": xmlns_terms}})

        if form_name_xmnls:
            full_query['query']['filtered']['filter']['and'].append({"term": {"xmlns.exact": form_name_xmnls}})

        res = self.xform_es.run_query(full_query)
        return res

    @property
    def rows(self):
        if self.request.GET.has_key('patient_id'):
            def _format_row(row_field_dict):
                return [None, self.submit_history_form_link(row_field_dict["_id"],
                                                      row_field_dict['_source'].get('es_readable_name', EMPTY_FIELD)),
                        row_field_dict['_source']['form']['meta'].get('username', EMPTY_FIELD),
                        self.form_completion_time(row_field_dict['_source']['form']['meta'].get('timeEnd', EMPTY_FIELD))
                ]

            res = self.es_results
            if res:
                if res.has_key('error'):
                    pass
                else:
                    for result in res['hits']['hits']:
                        yield list(_format_row(result))

    def submit_history_form_link(self, form_id, form_name):
        url = reverse('render_form_data', args=[self.domain, form_id])
        return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, html.escape(form_name)))

    def form_completion_time(self, date_string):
        if date_string != EMPTY_FIELD:
            return format_date(date_string, INTERACTION_OUTPUT_DATE_FORMAT, localize=True)
        else:
            return EMPTY_FIELD

    @property
    def report_context(self):
        ret = super(PatientSubmissionReport, self).report_context
        ret['view_mode'] = 'submissions'
        tabular_context = super(PatientDetailsReport, self).report_context
        tabular_context.update(ret)
        self.report_template_path = "patient_submissions.html"
        tabular_context['patient_id'] = self.request_params['patient_id']
        return tabular_context
