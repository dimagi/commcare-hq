from datetime import datetime
from django.http import Http404
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.xform_es import XFormES
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from pact.models import CDotWeeklySchedule, PactPatientCase
from pact.reports import PactPatientDispatcher, PactDrilldownReportMixin, PatientNavigationReport


class PactPatientInfoReport(PactDrilldownReportMixin, GenericTabularReport, CustomProjectReport):
#    name = "Patient Info"
    slug = "patient"
    description = "some patient"

    hide_filters = True
    filters = []
    ajax_pagination = True
    xform_es = XFormES()


    def prepare_schedule(self, patient_doc, context):
        #patient_doc is the case doc
        computed = patient_doc['computed_']

        def get_current(x):
            if x.deprecated:
                return False
            if x.ended is None and x.started < datetime.utcnow():
                return True
            if x.ended < datetime.utcnow():
                return False

            print "made it to the end somehow..."
            print '\n'.join(x.weekly_arr)
            return False

        if computed.has_key('pact_weekly_schedule'):
            schedule_arr = [CDotWeeklySchedule.wrap(x) for x in computed['pact_weekly_schedule']]

            past = filter(lambda x: x.ended is not None and x.ended < datetime.utcnow(),
                          schedule_arr)
            current = filter(get_current, schedule_arr)
            future = filter(lambda x: x.deprecated and x.started > datetime.utcnow(), schedule_arr)

            #            print '\n'.join([x.weekly_arr() for x in current])
            past.reverse()
            print current
            if len(current) > 1:
                for x in current:
                    print '\n'.join(x.weekly_arr())

            context['current_schedule'] = current[0]
            context['past_schedules'] = past
            context['future_schedules'] = future


    @memoized
    def get_case(self):
        self._case_doc = PactPatientCase.get(self.request.GET['patient_id'])
        return self._case_doc

    @property
    def name(self):
        if hasattr(self, 'request'):
            if self.request.GET.get('patient_id', None) is not None:
                case = self.get_case()
                return "Patient Info :: %s" % case.name
        else:
            return "Patient Info"

    def patient_submissions_query(self):
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
                        "query": {
                            "query_string": {
                                "query": "(form.case.case_id:{{ patient_doc.get_id }} OR form.case.@case_id:{{ patient_doc.get_id }})"},
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


    @property
    def report_context(self):
        patient_doc = self.get_case()
        view_mode = self.request.GET.get('view', 'info')
        ret = {'patient_doc': patient_doc}
        ret['pt_root_url'] = PactPatientInfoReport.get_url(
            *[self.request.domain]) + "?patient_id=%s" % self.request.GET['patient_id']
        ret['view_mode'] = view_mode
        print ret

        if view_mode == 'info':
            self.report_template_path = "pact/patient/pactpatient_info.html"
        elif view_mode == 'submissions':
            tabular_context = super(PactPatientInfoReport, self).report_context
            tabular_context.update(ret)
            self.report_template_path = "pact/patient/pactpatient_submissions.html"
            return tabular_context
        elif view_mode == 'schedule':
            self.prepare_schedule(patient_doc, ret)
            self.report_template_path = "pact/patient/pactpatient_schedule.html"
        else:
            raise Http404
        return ret


    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Form"),
                                DataTablesColumn("CHW"),
                                DataTablesColumn("Created Date"),
                                DataTablesColumn("Encounter Date"),
                                DataTablesColumn("Received"),
        )

    @property
    @memoized
    def es_results(self):
        if not self.request.GET.has_key('patient_id'):
            return None

        full_query =  {
            'query': {
                "filtered": {
                    "query": {
                        "query_string": {
                            "query": "(form.case.case_id:%(case_id)s OR form.case.@case_id:%(case_id)s)" % dict(case_id=self.request.GET['patient_id']),
                        }
                    },
                    "filter": {
                        "and": [
                            {
                                "term": {
                                    "domain.exact": self.request.domain
                                }
                            }
                        ]
                    },
                }
            },
            "fields": [
                "form.#type",
                "form.encounter_date",
                "form.note.encounter_date",
                "form.case.case_id",
                "form.case.@case_id",
                "form.pact_id",
                "form.note.pact_id",
                "received_on",
                "form.meta.timeStart",
                "form.meta.timeEnd",
                "form.meta.username"
            ],
            "sort": {
                "received_on": "desc"
            },
            "size": self.pagination.count,
            "from":self.pagination.start

        }
        return self.xform_es.run_query(full_query)


    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        if self.request.GET.has_key('patient_id'):
            rows = []
            def _format_row(row_field_dict):
                yield row_field_dict["form.#type"].replace('_', ' ').title()
                yield row_field_dict.get("form.meta.username", "")
                yield row_field_dict["form.meta.timeStart"]

                for p in ["form.encounter_date", "form.note.encounter_date", None]:
                    if p is None:
                        yield "None"
                    if row_field_dict.has_key(p):
                        yield row_field_dict[p]
                        break
                yield row_field_dict["received_on"]

            res = self.es_results
            print simplejson.dumps(res.keys(), indent=4)
            if res.has_key('error'):
                pass
            else:
                for result in res['hits']['hits']:
                    yield list(_format_row(result['fields']))

    @property
    def total_records(self):
        """
            Override for pagination.
            Returns an integer.
        """
        res = self.es_results
        if res is not None:
            return res['hits'].get('total', 0)
        else:
            return 0

    @property
    def shared_pagination_GET_params(self):
        """
            Override.
            Should return a list of dicts with the name and value of the GET parameters
            that you'd like to pass to the server-side pagination.
            ex: [dict(name='group', value=self.group_name)]
        """
        ret = []
        for k,v in self.request.GET.items():
            ret.append(dict(name=k, value=v))
        return ret
