from datetime import datetime, timedelta, time
import uuid
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import ReportCaseES, ReportXFormES
from corehq.apps.hqcase.dbaccessors import get_number_of_cases_in_domain
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.util.dates import iso_string_to_date
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date

from pact.enums import PACT_DOMAIN, PACT_CASE_TYPE, XMLNS_DOTS_FORM
from pact.models import PactPatientCase, DOTSubmission, CObservation
from pact.reports.dot_calendar import DOTCalendarReporter


class PactDOTPatientField(BaseSingleOptionFilter):
    slug = "dot_patient"
    label = "DOT Patient"
    default_option = "Select DOT Patient"

    @property
    @memoized
    def options(self):
        fmt = lambda case: "(%s) - %s" % (case.get('pactid.#value', '[none]'), case['name'])
        return [
            (case['_id'], fmt(case))
            for case in self.get_pact_cases()
        ]

    @property
    def selected(self):
        return self.request.GET.get(self.slug, '')

    @classmethod
    def get_pact_cases(cls):
        # query couch to get reduce count of all PACT cases
        case_es = ReportCaseES(PACT_DOMAIN)
        # why 'or 100'??
        total_count = \
            get_number_of_cases_in_domain('pact', type=PACT_CASE_TYPE) or 100
        fields = ['_id', 'name', 'pactid.#value']
        query = case_es.base_query(terms={'type': PACT_CASE_TYPE},
                                   fields=fields,
                                   start=0,
                                   size=total_count)
        query['filter']['and'].append({"prefix": {"dot_status.#value": "dot"}})

        results = case_es.run_query(query)
        for res in results['hits']['hits']:
            yield res['fields']


class PactDOTReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin,
                    DatespanMixin):
    name = "DOT Patient List"
    slug = "dots"

    report_template_path = "pact/dots/dots_report.html"
    flush_layout = True
    fields = ['pact.reports.dot.PactDOTPatientField', 'corehq.apps.reports.filters.dates.DatespanFilter']

    @property
    def report_context(self):
        ret = {}
        if not self.request.GET.has_key('dot_patient') or self.request.GET.get('dot_patient') == "":
            self.report_template_path = "pact/dots/dots_report_nopatient.html"
            return ret
        submit_id = self.request.GET.get('submit_id', None)
        ret['dot_case_id'] = self.request.GET['dot_patient']
        casedoc = PactPatientCase.get(ret['dot_case_id'])
        ret['patient_case'] = casedoc
        start_date_str = self.request.GET.get('startdate',
                                              json_format_date(datetime.utcnow() - timedelta(days=7)))
        end_date_str = self.request.GET.get('enddate', json_format_date(datetime.utcnow()))

        start_date = datetime.combine(iso_string_to_date(start_date_str), time())
        end_date = datetime.combine(iso_string_to_date(end_date_str), time())

        ret['startdate'] = start_date_str
        ret['enddate'] = end_date_str

        dcal = DOTCalendarReporter(casedoc, start_date=start_date, end_date=end_date, submit_id=submit_id)
        ret['dot_calendar'] = dcal

        unique_visits = dcal.unique_xforms()
        xform_es = ReportXFormES(PACT_DOMAIN)

        q = xform_es.base_query(size=len(unique_visits))
        lvisits = list(unique_visits)
        if len(lvisits) > 0:
            q['filter']['and'].append({"ids": {"values": lvisits}})
            #todo double check pactid/caseid matches
        q['sort'] = {'received_on': 'desc'}
        res = xform_es.run_query(q)

        #ugh, not storing all form data by default - need to get?
        ret['sorted_visits'] = [DOTSubmission.wrap(x['_source']) for x in
                                filter(lambda x: x['_source']['xmlns'] == XMLNS_DOTS_FORM,
                                       res['hits']['hits'])]
        return ret


