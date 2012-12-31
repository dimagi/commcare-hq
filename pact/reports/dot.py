from datetime import datetime, timedelta
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import CaseES, XFormES
from corehq.apps.hqcase.paginator import CasePaginator
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import SelectMobileWorkerField, ReportSelectField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.standard.inspect import CaseListReport, CaseDisplay, CaseListMixin

from couchdbkit.resource import RequestFailed
from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized
from pact.enums import PACT_DOMAIN, PACT_CASE_TYPE, XMLNS_DOTS_FORM
from pact.reports.dot_calendar import DOTCalendarReporter


class PactDOTPatientField(ReportSelectField):
    slug = "dot_patient"
    name = "DOT Patient"
    default_option = "Select DOT Patient"
#    cssId = "case_type_select"

    def update_params(self):
        patient_cases = self.get_pact_cases()
        case_type = self.request.GET.get(self.slug, '')

        self.selected = case_type
        self.options = [dict(val=case['_id'], text="(%s) - %s" % (case.get('pactid', '[none]'), case['name'])) for case in patient_cases]

    @classmethod
    def get_pact_cases(cls):
        domain = PACT_DOMAIN
        case_es = CaseES()
        query = case_es.base_query(domain, start=0, size=None)
        query['filter']['and'].append({ "prefix": { "dot_status": "dot" } })
        query['filter']['and'].append({ "term": { "type": PACT_CASE_TYPE } })

        query['fields'] = ['_id', 'name', 'pactid']
        results = case_es.run_query(query)
        for res in results['hits']['hits']:
            print res
            yield res['fields']

class PactDOTReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    name = "DOT Patient List"
    slug = "dots"

    description = "PACT DOT Report"
    report_template_path = "pact/dots/dots_report.html"
#    hide_filters = True
    flush_layout = True
    fields=['pact.reports.dot.PactDOTPatientField', 'corehq.apps.reports.fields.DatespanField']

    @property
    def report_context(self):
        ret = {}
        if not self.request.GET.has_key('dot_patient') or self.request.GET.get('dot_patient') == "":
            self.report_template_path = "pact/dots/dots_report_nopatient.html"
            return ret
        ret['dot_case_id'] = self.request.GET['dot_patient']
        casedoc = CommCareCase.get(ret['dot_case_id'])
        ret['patient_case'] = casedoc
        start_date_str = self.request.GET.get('startdate', (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d'))
        end_date_str = self.request.GET.get('enddate', datetime.utcnow().strftime("%Y-%m-%d"))

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

        ret['startdate'] = start_date_str
        ret['enddate'] = end_date_str
        dcal = DOTCalendarReporter(casedoc, start_date=start_date, end_date=end_date)
        ret['dot_calendar'] = dcal

        unique_visits = dcal.unique_xforms()
        xform_es = XFormES()

        q = xform_es.base_query(PACT_DOMAIN, size=None)
        lvisits = list(unique_visits)
        if len(lvisits) > 0:
            q['filter']['and'].append({
                        "ids": {
                            "values": lvisits
                        }
                    }
            )
        #todo double check pactid/caseid matches
#        q['filter']['and'].append({ "term": {"pactid": casedoc.pactid} })
#        q['fields'] =  [
#                "form.#type",
#                "form.encounter_date",
#                "form.pact_id",
#                "received_on",
#                "form.meta.timeStart",
#                "form.meta.timeEnd",
#                "form.meta.username"
#            ]
        q['sort'] = {'received_on': 'desc'}

        res = xform_es.run_query(q)


        #ugh, not storing all form data by default - need to get?
        ret['sorted_visits'] = [XFormInstance.wrap(x['_source']) for x in filter(lambda x: x['_source']['xmlns'] == XMLNS_DOTS_FORM, res['hits']['hits'])]
        return ret


