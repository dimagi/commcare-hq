from django.core.urlresolvers import NoReverseMatch, reverse
from django.http import Http404
from corehq.apps.api.es import ReportCaseES, ReportXFormES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.users.models import CommCareUser
from dimagi.utils import html
from dimagi.utils.decorators.memoized import memoized
from pact.enums import PACT_CASE_TYPE, PACT_DOMAIN
from . import chw_schedule
from pact.reports import PactDrilldownReportMixin, PactElasticTabularReportMixin
from pact.utils import pact_script_fields, case_script_field


class PactCHWProfileReport(PactDrilldownReportMixin, PactElasticTabularReportMixin):
    slug = "chw_profile"
    description = "CHW Profile"
    view_mode = 'info'
    ajax_pagination = True
    xform_es = ReportXFormES(PACT_DOMAIN)
    case_es = ReportCaseES(PACT_DOMAIN)
    default_sort = {"received_on": "desc"}

    name = "CHW Profile"

    hide_filters = True
    filters = []

    is_bootstrap3 = True

    def pact_case_link(self, case_id):
        #stop the madness
        from pact.reports.patient import PactPatientInfoReport

        try:
            return PactPatientInfoReport.get_url(*[self.domain]) + "?patient_id=%s" % case_id
        except NoReverseMatch:
            return "#"

    def pact_dot_link(self, case_id ):
        from pact.reports.dot import PactDOTReport

        try:
            return PactDOTReport.get_url(*[self.domain]) + "?dot_patient=%s" % case_id
        except NoReverseMatch:
            return "#"


    def get_assigned_patients(self):
        """get list of patients and their submissions on who this chw is assigned as primary hp"""
        fields = ["_id", "name", "pactid.#value", "hp_status.#value", "dot_status.#value"]
        case_query = self.case_es.base_query(
            terms={'type': PACT_CASE_TYPE, 'hp.#value': self.get_user().raw_username}, fields=fields,
            size=100)

        case_query['filter']['and'].append({'not': {'term': {'hp_status.#value': 'discharged'}}})
        chw_patients_res = self.case_es.run_query(case_query)
        assigned_patients = [x['fields'] for x in chw_patients_res['hits']['hits']]

        for x in assigned_patients:
            x['info_url'] = self.pact_case_link(x['_id'])
            if x['dot_status.#value'] is not None or x['dot_status.#value'] != "":
                x['dot_url'] = self.pact_dot_link(x['_id'])
        return sorted(assigned_patients, key=lambda x: int(x['pactid.#value']))


    def get_fields(self):
        if self.view_mode == 'submissions':
            yield 'corehq.apps.reports.filters.users.UserTypeFilter'
            yield 'corehq.apps.reports.filters.dates.DatespanFilter'


    @memoized
    def get_user(self):
        if hasattr(self, 'request') and self.request.GET.has_key('chw_id'):
            self._user_doc = CommCareUser.get(self.request.GET['chw_id'])
            return self._user_doc
        else:
            return None


    @property
    def report_context(self):
        user_doc = self.get_user()
        self.view_mode = self.request.GET.get('view', 'info')
        self.interval = self.request.GET.get('interval', 7)

        ret = {
            'user_doc': user_doc,
            'view_mode': self.view_mode,
            'chw_root_url': PactCHWProfileReport.get_url(*[self.request.domain]) + "?chw_id=%s" % self.request.GET['chw_id']
        }

        if self.view_mode == 'info':
            self.hide_filters = True
            self.report_template_path = "pact/chw/pact_chw_profile_info.html"
            ret['assigned_patients'] = self.get_assigned_patients()
        elif self.view_mode == 'submissions':
            tabular_context = super(PactCHWProfileReport, self).report_context
            tabular_context.update(ret)
            self.report_template_path = "pact/chw/pact_chw_profile_submissions.html"
            return tabular_context
        elif self.view_mode == 'schedule':
            scheduled_context = chw_schedule.chw_calendar_submit_report(self.request,
                                                                        user_doc.raw_username, interval=self.interval)
            ret.update(scheduled_context)
            self.report_template_path = "pact/chw/pact_chw_profile_schedule.html"
        else:
            raise Http404
        return ret


    #submission stuff
    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Show Form", sortable=False, span=1),
            DataTablesColumn("Pact ID", sortable=False, span=1),
            DataTablesColumn("Received", prop_name="received_on", sortable=True, span=1),
            DataTablesColumn("Encounter Date", sortable=False, span=1),
            DataTablesColumn("Form", prop_name="form.#type", sortable=True, span=1),
        )

    @property
    def es_results(self):
        user = self.get_user()
        fields = [
            "_id",
            "form.#type",
            "received_on",
            "form.meta.timeStart",
            "form.meta.timeEnd"
        ]
        query = self.xform_es.base_query(terms={'form.meta.username': user.raw_username},
                                         fields=fields, start=self.pagination.start,
                                         size=self.pagination.count)
        query['script_fields'] = {}
        query['script_fields'].update(pact_script_fields())
        query['script_fields'].update(case_script_field())
        query['sort'] = self.get_sorting_block()
        return self.xform_es.run_query(query)

    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        if self.get_user() is not None:
            def _format_row(row_field_dict):
                yield html.mark_safe("<a class='ajax_dialog' href='%s'>View</a>" % (
                reverse('render_form_data', args=[self.domain, row_field_dict['_id']])))
                yield row_field_dict['script_pact_id']
                yield self.format_date(row_field_dict["received_on"].replace('_', ' ').title())
                yield self.format_date(row_field_dict['script_encounter_date'])
                yield row_field_dict["form.#type"].replace('_', ' ').title().strip()

            res = self.es_results
            if res.has_key('error'):
                pass
            else:
                for result in res['hits']['hits']:
                    yield list(_format_row(result['fields']))
