from datetime import timedelta
import datetime
from django.utils.translation import ugettext_noop
from django.utils import html
from casexml.apps.case.models import CommCareCase
from django.core.urlresolvers import reverse, NoReverseMatch
import pytz
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard.cases.basic import CaseListReport

from corehq.apps.api.es import ReportCaseES
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.pillows.base import restore_property_dict
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.decorators.memoized import memoized
from corehq.util.timezones import utils as tz_utils


def visit_completion_counter(case):
    mother_counter = 0
    child_counter = 0
    case_obj = CommCareCase.get(case['_id'])
    baby_case = [c for c in case_obj.get_subcases().all() if c.type == 'baby']
    for i in range(1, 8):
        if "pp_%s_done" % i in case:
            val = case["pp_%s_done" % i]
            try:
                if val.lower() == 'yes':
                    mother_counter += 1
                elif int(float(val)) == 1:
                    mother_counter += 1
            except ValueError:
                pass
        if baby_case and "bb_pp_%s_done" % i in baby_case[0]:
            val = baby_case[0]["bb_pp_%s_done" % i]
            try:
                if val.lower() == 'yes':
                    child_counter += 1
                elif int(float(val)) == 1:
                    child_counter += 1
            except ValueError:
                pass

    return mother_counter if mother_counter > child_counter else child_counter


class HNBCReportDisplay(CaseDisplay):

    @property
    def dob(self):
        if 'date_birth' not in self.case:
            return '---'
        else:
            return self.report.date_to_json(self.parse_date(self.case['date_birth']))

    @property
    def visit_completion(self):
        return "%s/7" % visit_completion_counter(self.case)

    @property
    def delivery(self):
        if 'place_birth' not in self.case:
            return '---'
        else:
            if "at_home" == self.case['place_birth']:
                return _('Home')
            elif "in_hospital" == self.case['place_birth']:
                return _('Hospital')
            else:
                return _('Other')


    @property
    def case_link(self):
        case_id, case_name = self.case['_id'], self.case['mother_name']
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(reverse('crs_details_report', args=[self.report.domain, case_id, self.report.slug])),
                html.escape(case_name),
            ))
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name

    @property
    def baby_name(self):
        case = CommCareCase.get(self.case['_id'])

        baby_case = [c for c in case.get_subcases().all() if c.type == 'baby']
        if baby_case:
            return baby_case[0].name
        else:
            return '---'

class BaseHNBCReport(CustomProjectReport, CaseListReport):

    fields = ['custom.apps.crs_reports.fields.SelectBlockField',
              'custom.apps.crs_reports.fields.SelectSubCenterField', # Todo: Currently there is no data about it in case
              'custom.apps.crs_reports.fields.SelectASHAField']

    ajax_pagination = True
    include_inactive = True
    module_name = 'crs_reports'
    report_template_name = None

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    def build_es_query(self, case_type=None, afilter=None, status=None):

        def _domain_term():
            return {"term": {"domain.exact": self.domain}}

        subterms = [_domain_term(), afilter] if afilter else [_domain_term()]
        if case_type:
            subterms.append({"term": {"type.exact": case_type}})

        if status:
            subterms.append({"term": {"closed": (status == 'closed')}})

        es_query = {
            'query': {
                'filtered': {
                    'query': {"match_all": {}},
                    'filter': {'and': subterms}
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start,
            'size': self.pagination.count,
        }

        return es_query

    @property
    @memoized
    def es_results(self):
        query = self.build_es_query(case_type=self.case_type, afilter=self.case_filter, status=self.case_status)
        return self.case_es.run_query(query)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Mother Name"), prop_name="mother_name.#value"),
            DataTablesColumn(_("Baby Name"), sortable=False),
            DataTablesColumn(_("CHW Name"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Date of Delivery"),  prop_name="date_birth.#value"),
            DataTablesColumn(_("PNC Visit Completion"), sortable=False),
            DataTablesColumn(_("Delivery"), prop_name="place_birth"),
        )
        return headers

    @property
    def rows(self):
        case_displays = (HNBCReportDisplay(self, restore_property_dict(self.get_case(case)))
                         for case in self.es_results['hits'].get('hits', []))

        for disp in case_displays:
            yield [
                disp.case_link,
                disp.baby_name,
                disp.owner_display,
                disp.dob,
                disp.visit_completion,
                disp.delivery,
            ]

    @property
    @memoized
    def rendered_report_title(self):
        if not self.individual:
            self.name = _("%(report_name)s for (0-42 days after delivery)") % {
                "report_name": _(self.name)
            }
        return self.name


    def base_filters(self):
        block = self.request_params.get('block', '')
        individual = self.request_params.get('individual', '')
        filters = []

        if block:
            filters.append({'term': {'block.#value': block}})
        if individual:
            filters.append({'term': {'owner_id': individual}})
        return filters

    def date_to_json(self, date):
        return ServerTime(date).user_time(self.timezone).done().strftime('%d-%m-%Y') if date else ""


class HBNCMotherReport(BaseHNBCReport):

    name = ugettext_noop('Mother HBNC Form')
    slug = 'hbnc_mother_report'
    report_template_name = 'mothers_form_reports_template'
    default_case_type = 'pregnant_mother'

    @property
    def case_filter(self):
        now = datetime.datetime.now()
        fromdate = now - timedelta(days=42)
        filters = BaseHNBCReport.base_filters(self)
        filters.append({'term': {'pp_case_filter.#value': "1"}})
        filters.append({'range': {'date_birth.#value': {"gte": fromdate.strftime("%Y-%m-%d")}}})
        status = self.request_params.get('PNC_status', '')

        or_stmt = []

        if status:
            if status == 'On Time':
                for i in range(1, 8):
                    filters.append({'term': {'case_pp_%s_done.#value' % i: 'yes'}})
            else:
                for i in range(1, 8):
                    or_stmt.append({"not": {'term': {'case_pp_%s_done.#value' % i: 'yes'}}})
                or_stmt = {'or': or_stmt}
                filters.append(or_stmt)

        return {'and': filters} if filters else {}

