from couchdbkit import ResourceNotFound
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
    def baby_name(self):
        case = CommCareCase.get(self.case['_id'])

        baby_case = [c for c in case.get_subcases().all() if c.type == 'baby']
        if baby_case:
            return baby_case[0].name
        else:
            return '---'

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
              'custom.apps.crs_reports.fields.SelectPNCStatusField']

    ajax_pagination = True
    include_inactive = True
    module_name = 'crs_reports'
    report_template_name = None

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and (user.is_previewer() or 'soldevelo' in user.username)

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Mother Name"), prop_name="name.exact"),
            DataTablesColumn(_("Baby Name"), sortable=False),
            DataTablesColumn(_("CHW Name"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Date of Delivery"),  prop_name="date_birth"),
            DataTablesColumn(_("PNC Visit Completion"), sortable=False),
            DataTablesColumn(_("Delivery"), prop_name="place_birth"),
            DataTablesColumn(_("Case/PNC Status"), sortable=False)
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

        filters = []

        if block:
            filters.append({'term': {'block.#value': block}})

        return filters

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%d-%m-%Y') if date else ""


class HBNCMotherReport(BaseHNBCReport):

    name = ugettext_noop('Mother HBNC Form')
    slug = 'hbnc_mother_report'
    report_template_name = 'mothers_form_reports_template'
    default_case_type = 'pregnant_mother'

    @property
    def case_filter(self):
        filters = BaseHNBCReport.base_filters(self)
        filters.append({'term': {'pp_case_filter.#value': "1"}})

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

    @property
    def user_filter(self):
        return super(HBNCMotherReport, self).user_filter

