from django.http import Http404
import simplejson
from corehq.apps.api.es import XFormES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators import inline
from dimagi.utils.decorators.memoized import memoized
from pact.reports import  PactDrilldownReportMixin, chw_schedule, ESSortableMixin
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
    default_sort = {"received_on": "desc"}

    hide_filters = True
    filters = []
    #    fields = ['corehq.apps.reports.fields.FilterUsersField', 'corehq.apps.reports.fields.DatespanField',]
    #    hide_filters=False

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


    @property
    def name(self):
        if hasattr(self, 'request') and self.request.GET.has_key('chw_id'):
            return "CHW Profile :: %s" % self.get_user().raw_username
        else:
            return "CHW Profile"


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
                yield row_field_dict["received_on"].replace('_', ' ').title()

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


