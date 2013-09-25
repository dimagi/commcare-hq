from couchdbkit import RequestFailed
from django.utils.translation import ugettext_noop
from corehq.apps.api.es import FullCaseES

from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard.inspect import CaseDisplay, CaseListReport
from django.utils import html
from django.core.urlresolvers import reverse, NoReverseMatch

import pytz
from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils


def visit_completion_counter(case):
    counter = 0
    for i in range(1, 8):
        if "case_pp_%s_done" % i in case and case["case_pp_%s_done" % i].upper() == "YES":
            counter += 1
    return counter


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
        case_id, case_name = self.case['_id'], self.case['name']
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(reverse('crs_details_report', args=[self.report.domain, case_id, self.report.slug])),
                html.escape(case_name),
            ))
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name


    @property
    def pnc_status(self):
        if visit_completion_counter(self.case) == 7:
            return _("On Time")
        else:
            return _("Late")

class BaseHNBCReport(CustomProjectReport, CaseListReport):

    fields = ['custom.apps.crs_reports.fields.SelectBlockField',
              'custom.apps.crs_reports.fields.SelectSubCenterField', # Todo: Currently there is no data about it in case
              'custom.apps.crs_reports.fields.SelectASHAField',
              'custom.apps.crs_reports.fields.SelectPNCStatusField',
              'corehq.apps.reports.standard.inspect.CaseSearchFilter']

    ajax_pagination = True
    include_inactive = True
    module_name = 'crs_reports'
    report_template_name = None

    @property
    @memoized
    def case_es(self):
        return FullCaseES(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Case Type"), prop_name="type.exact"),
            DataTablesColumn(_("Case Name"), prop_name="name.exact"),
            DataTablesColumn(_("CHW Name"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Date of Delivery"),  prop_name="date_birth"),
            DataTablesColumn(_("PNC Visit Completion"), sortable=False),
            DataTablesColumn(_("Delivery"), prop_name="place_birth"),
            DataTablesColumn(_("Case/PNC Status"), sortable=False)
        )
        return headers

    @property
    def rows(self):
        case_displays = (HNBCReportDisplay(self, self.get_case(case))
                         for case in self.es_results['hits'].get('hits', []))

        for disp in case_displays:
            yield [
                disp.case_type,
                disp.case_link,
                disp.owner_display,
                disp.dob,
                disp.visit_completion,
                disp.delivery,
                disp.pnc_status,
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
        status = self.request_params.get('PNC_status', '')

        filters = []
        or_stmt = []

        if block:
            filters.append({'term': {'block': block}})

        if status:
            if status == 'On Time':
                for i in range(1, 8):
                    filters.append({'term': {'case_pp_%s_done' % i: 'yes'}})
            else:
                for i in range(1, 8):
                    or_stmt.append( {"not": {'term': {'case_pp_%s_done' % i: 'yes'}}})
                or_stmt = {'or': or_stmt}
                filters.append(or_stmt)
        return filters

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%d-%m-%Y') if date else ""


class HNBCMotherReport(BaseHNBCReport):

    name = ugettext_noop('Mother HNBC Form')
    slug = 'hnbc_mother_report'
    report_template_name = 'mothers_form_reports_template'
    default_case_type = 'pregnant_mother'

    @property
    def case_filter(self):
        pp_case_filter = BaseHNBCReport.base_filters(self)
        pp_case_filter.append({'term': {'pp_case_filter': "1"}})
        return {'and': pp_case_filter} if pp_case_filter else {}

    @property
    def user_filter(self):
        return super(HNBCMotherReport, self).user_filter


class HNBCInfantReport(BaseHNBCReport):
    name = ugettext_noop('Infant HNBC Form')
    slug = 'hnbc_infant_report'
    report_template_name = 'baby_form_reports_template'
    default_case_type = 'baby'

    @property
    def case_filter(self):
        filters = BaseHNBCReport.base_filters(self)
        return {'and': filters} if filters else {}

    @property
    def user_filter(self):
        return super(HNBCInfantReport, self).user_filter

