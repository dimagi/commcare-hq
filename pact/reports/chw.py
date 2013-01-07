from django.core.urlresolvers import NoReverseMatch, reverse
from django.http import Http404
import simplejson
from corehq.apps.api.es import XFormES, CaseES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.users.models import CommCareUser
from dimagi.utils import html
from dimagi.utils.decorators import inline
from dimagi.utils.decorators.memoized import memoized
from pact.enums import PACT_CASE_TYPE
from pact.reports import  PactDrilldownReportMixin, chw_schedule, ESSortableMixin, query_per_case_submissions_facet
from pact.utils import pact_script_fields, case_script_field


class XFormDisplay(object):
    def __init__(self, result_row):
        self.result_row = result_row


    @property
    def pact_id(self):
        pass

    @property
    def case_id(self):
        pass

    @property
    def form_type(self):
        pass

    @property
    def encounter_date(self):
        pass

    @property
    def received_on(self):
        pass


class PactCHWProfileReport(PactDrilldownReportMixin, ESSortableMixin,GenericTabularReport, CustomProjectReport):
    slug = "chw_profile"
    description = "CHW Profile"
    view_mode = 'info'
    ajax_pagination = True
    xform_es = XFormES()
    case_es = CaseES()
    default_sort = {"received_on": "desc"}

    name = "CHW Profile"

    hide_filters = True
    filters = []
    #    fields = ['corehq.apps.reports.fields.FilterUsersField', 'corehq.apps.reports.fields.DatespanField',]
    #    hide_filters=False


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

        #get list of patients and their submissions on who this chw is assigned as primary hp

        case_query = {
            "filter": {
                "and": [
                    { "term": { "domain.exact": self.request.domain } },
                    { "term": { "type": PACT_CASE_TYPE } },
                    { "term": { "hp": self.get_user().raw_username } }
                ]
            },
            "fields": [ "_id", "name", "pactid", "hp_status", "dot_status" ]
        }
        case_type = PACT_CASE_TYPE

        chw_patients_res = self.case_es.run_query(case_query)

        case_ids = [x['fields']['_id'] for x in chw_patients_res['hits']['hits']]
        #todo, facet this on num submits?

        assigned_patients = [x['fields'] for x in chw_patients_res['hits']['hits']]

        for x in assigned_patients:
            x['info_url'] = self.pact_case_link(x['_id'])
            if x['dot_status'] is not None or x['dot_status'] != "":
                x['dot_url'] = self.pact_dot_link(x['_id'])
        return sorted(assigned_patients, key=lambda x: int(x['pactid']))
        #return assigned_patients


    def get_fields(self):
        if self.view_mode == 'submissions':
            yield 'corehq.apps.reports.fields.FilterUsersField'
            yield 'corehq.apps.reports.fields.DatespanField'


    @memoized
    def get_user(self):
        print self.request.GET.keys()
        if hasattr(self, 'request') and self.request.GET.has_key('chw_id'):
            self._user_doc = CommCareUser.get(self.request.GET['chw_id'])
            return self._user_doc
        else:
            return None


#    @property
#    def name(self):
#        if hasattr(self, 'request') and self.request.GET.has_key('chw_id'):
#            return "CHW Profile :: %s" % self.get_user().raw_username
#        else:
#            return "CHW Profile"


    @property
    def report_context(self):
        user_doc = self.get_user()
        self.view_mode = self.request.GET.get('view', 'info')
        ret = {'user_doc': user_doc}
        ret['view_mode'] = self.view_mode
        ret['chw_root_url'] = PactCHWProfileReport.get_url(*[self.request.domain]) + "?chw_id=%s" % self.request.GET['chw_id']

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
                                                                        user_doc.raw_username)
            ret.update(scheduled_context)
            self.report_template_path = "pact/chw/pact_chw_profile_schedule.html"
        else:
            raise Http404
        return ret


    #submission stuff
    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Pact ID", sortable=False, span=2),
                                DataTablesColumn("Encounter Date", sortable=False, span=2),

                                DataTablesColumn("Form", prop_name="form.#type", sortable=True, span=2),
                                DataTablesColumn("Received", prop_name="received_on", sortable=True, span=2),
        )

    @property
    def es_results(self):
        user = self.get_user()
        query = self.xform_es.base_query(self.request.domain, start=self.pagination.start,
                                         size=self.pagination.count)
        query['fields'] = [
            "_id",
            "form.#type",
#            "form.encounter_date",
#            "form.note.encounter_date",
#            "form.case.case_id",
#            "form.case.@case_id",
#            "form.pact_id",
#            "form.note.pact_id",
            "received_on",
            "form.meta.timeStart",
            "form.meta.timeEnd"
        ]
        query['filter']['and'].append({"term": {"form.meta.username": user.raw_username}})
        query['script_fields'] = {}
        query['script_fields'].update(pact_script_fields())
        query['script_fields'].update(case_script_field())
        query['sort'] = self.get_sorting_block()

        print simplejson.dumps(query, indent=4)
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
                yield row_field_dict['script_pact_id']
                yield row_field_dict['script_encounter_date']
                yield row_field_dict["form.#type"].replace('_', ' ').title()
                yield "%s %s" % (row_field_dict["received_on"].replace('_', ' ').title(),
                html.mark_safe("<a class='ajax_dialog' href='%s'>View</a>" % ( reverse('render_form_data', args=[self.domain, row_field_dict['_id']]))))
            res = self.es_results
            if res.has_key('error'):
                pass
            else:
                for result in res['hits']['hits']:
                    yield list(_format_row(result['fields']))



    def my_submissions(self):
        #todo: delete, unused
        user = self.get_user()
        query = {
            "fields": [
                "form.#type",
                "form.encounter_date",
                "form.note.encounter_date",
                "form.case.case_id",
                "form.case.@case_id",
                "received_on",
                "form.meta.timeStart",
                "form.meta.timeEnd"
            ],
            "filter": {
                "and": [
                    {
                        "term": {
                            "domain.exact": "pact"
                        }
                    },
                    {
                        "term": {
                            "form.meta.username": user.raw_username
                        }
                    }
                ]
            },
            "sort": {
                "received_on": "desc"
            },
            "size": 10,
            "from": 0
        }


