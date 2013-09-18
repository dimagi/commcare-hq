from django.utils.translation import ugettext_noop

from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.fields import StrongFilterUsersField
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
        if "pp_visit_%s" % i in case and case["case_pp_%s_done" % i].upper() == "YES":
            counter += 1
    return counter


class HNBCReportDisplay(CaseDisplay):

    @property
    def dob(self):
        if 'date_birth' not in self.case:
            return '---'
        else:
            return self.case['date_birth']

    @property
    def visit_completion(self):
        return "%s/7" % visit_completion_counter(self.case)

    @property
    def delivery(self):
        if 'place_birth' not in self.case:
            return '---'
        else:
            return self.case['place_birth']

    @property
    def pnc_status(self):
        if visit_completion_counter(self.case) == 7:
            return "On Time"
        else:
            return "Late"

    @property
    def case_link(self):
        case_id, case_name = self.case['_id'], self.case['name']
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(reverse('case_details_report', args=[self.report.domain, case_id,
                            self.report.module_name, self.report.report_template_name, self.report.slug])),
                html.escape(case_name),
            ))
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name


class BaseHNBCReport(CustomProjectReport, DatespanMixin, CaseListReport):

    fields = ['corehq.apps.reports.fields.SelectBlockField',
              'corehq.apps.reports.fields.SelectSubCenterField',
              'corehq.apps.reports.fields.SelectASHAField',
              'corehq.apps.reports.fields.SelectPNCStatusField',
              'corehq.apps.reports.standard.inspect.CaseSearchFilter']

    ajax_pagination = True
    filter_users_field_class = StrongFilterUsersField
    include_inactive = True
    module_name = 'crs_reports'
    report_template_name = None

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Case Type"), prop_name="type.exact"),
            DataTablesColumn(_("Case Name"), prop_name="name.exact"),
            DataTablesColumn(_("CHW Name"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("DOB"), prop_name="dob"),
            DataTablesColumn(_("PNC Visit Completion"), prop_name="visit_completion"),
            DataTablesColumn(_("Delivery"), prop_name="delivery"),
            DataTablesColumn(_("Case/PNC Status"), prop_name="pnc_status")
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
    def case_filter(self):
        filters = [{'term': {'pp_case_filter': "1"}}]
        return {'and': filters} if filters else {}

    @property
    @memoized
    def rendered_report_title(self):
        if not self.individual:
            self.name = _("%(report_name)s for (0-42 days after delivery)") % {
                "report_name": _(self.name)
            }
        return self.name

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%Y-%m-%d') if date else ""


class HNBCMotherReport(BaseHNBCReport):

    name = ugettext_noop('Mother HNBC Form')
    slug = 'hnbc_mother_report'
    report_template_name = 'mothers_form_reports_template'
    default_case_type = 'pregnant_mother'

    @property
    def user_filter(self):
        return super(HNBCMotherReport, self).user_filter


class HNBCInfantReport(BaseHNBCReport):
    name = ugettext_noop('Infant HNBC Form')
    slug = 'hnbc_infant_report'
    report_template_name = 'baby_form_reports_template'
    default_case_type = 'baby'

    @property
    def user_filter(self):
        return super(HNBCInfantReport, self).user_filter

