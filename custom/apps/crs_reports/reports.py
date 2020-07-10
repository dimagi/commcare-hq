from datetime import timedelta
import datetime
from django.utils.translation import ugettext_noop
from django.utils import html
from casexml.apps.case.models import CommCareCase
from django.urls import reverse, NoReverseMatch
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard.cases.basic import CaseListReport

from corehq.apps.es import filters
from corehq.apps.es.cases import CaseES
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.pillows.base import restore_property_dict
from corehq.util.timezones.conversions import PhoneTime
from dimagi.utils.dates import force_to_datetime
from memoized import memoized
from dimagi.utils.parsing import json_format_date


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
            return self.report.date_to_json(self.case['date_birth'])

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
    def es_results(self):
        query = CaseES('report_cases').domain(self.domain)
        if self.case_type:
            query = query.case_type(self.case_type)

        if self.case_filter:
            query = query.filter(self.case_filter)

        if self.case_status:
            query = query.filter(filters.term("closed", self.case_status == 'closed'))

        query = (
            query
            .set_sorting_block(self.get_sorting_block())
            .start(self.pagination.start)
            .size(self.pagination.count)
        )
        return query.run().hits

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Mother Name"), prop_name="mother_name.#value"),
            DataTablesColumn(_("Baby Name"), sortable=False),
            DataTablesColumn(_("CHW Name"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Date of Delivery"),  prop_name="date_birth.#value"),
            DataTablesColumn(_("PNC Visit Completion"), sortable=False),
            DataTablesColumn(_("Delivery"), prop_name="place_birth.#value"),
        )
        return headers

    @property
    def rows(self):
        case_displays = (HNBCReportDisplay(self, restore_property_dict(self.get_case(case)))
                         for case in self.es_results)

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
        if date:
            try:
                date = force_to_datetime(date)
                return (PhoneTime(date, self.timezone).user_time(self.timezone)
                        .ui_string('%d-%m-%Y'))
            except ValueError:
                return ''
        else:
            return ''


class HBNCMotherReport(BaseHNBCReport):

    name = ugettext_noop('Mother HBNC Form')
    slug = 'hbnc_mother_report'
    report_template_name = 'mothers_form_reports_template'
    default_case_type = 'pregnant_mother'

    @property
    def case_filter(self):
        now = datetime.datetime.utcnow()
        fromdate = now - timedelta(days=42)
        _filters = BaseHNBCReport.base_filters(self)
        _filters.append(filters.term('pp_case_filter.#value', '1'))
        _filters.append(filters.range(gte=json_format_date(fromdate)))
        status = self.request_params.get('PNC_status', '')

        if status:
            if status == 'On Time':
                for i in range(1, 8):
                    _filters.append(filters.term('case_pp_%s_done.#value' % i, 'yes'))
            else:
                or_stmt = []
                for i in range(1, 8):
                    or_stmt.append(filters.not_term('case_pp_%s_done.#value' % i, 'yes'))
                if or_stmt:
                    _filters.append(filters.OR(*or_stmt))

        return filters.AND(*_filters)

CUSTOM_REPORTS = (
    (_('Custom Reports'), (
        HBNCMotherReport,
    )),
)

QUESTION_TEMPLATES = (
    (HBNCMotherReport.slug, [
        { 'questions' :[
            {'case_property': 'section_a',
             'question': _('A. Ask Mother.')
            },
            {'case_property': 'meals',
            'question': _('Number of times mother takes full meals in 24 hours?'),
            },
            {'case_property': 'bleeding',
            'question': _('Bleeding. How many Pads are changed in a day?'),
            },
            {'case_property': 'warm',
            'question': _('During the cold season is the baby being kept warm?'),
            },
            {'case_property': 'feeding',
            'question': _('Is the baby being fed properly?'),
            },
            {'case_property': 'incessant_cry',
            'question': _('Is the baby crying incessantly or passing urine less than 6 times?'),
            },
            {'case_property': 'section_b',
            'question': _('B. Examination of mother'),
            },
            {'case_property': 'maternal_temp',
            'question': _('Temperature: Measure and Record?'),
            },
            {'case_property': 'discharge',
            'question': _('Foul Smelling Discharge?'),
            },
            {'case_property': 'maternal_fits',
            'question': _('Is mother speaking normally or having fits'),
            },
            {'case_property': 'no_milk',
            'question': _('Mother has no milk since delivery or less milk'),
            },
            {'case_property': 'sore_breast',
            'question': _('Cracked Nipples/Painful or Engorged Breast/'),
            }]
        },
        { 'questions' :[
            {'case_property': 'section_c',
             'question': _('C.  Examination of Baby')
            },
            {'case_property': 'baby_eye',
            'question': _('Eyes Swollen with pus?'),
            },
            {'case_property': 'weight',
            'question': _('Weight (7,14,21,28)?'),
            },
            {'case_property': 'baby_temp',
            'question': _('Temperature: Measure and Record?'),
            },
            {'case_property': 'pustules',
            'question': _('Skin: Pus filled pustules?'),
            },
            {'case_property': 'cracks',
            'question': _('Cracks and Redness on the skin fold?'),
            },
            {'case_property': 'jaundice',
            'question': _('Yellowness in eyes'),
            }]
        },
        { 'questions' :[
            {'case_property': 'section_d',
             'question': _('D.  Sepsis Signs Checkup')
            },
            {'case_property': 'limbs',
            'question': _('All limbs up?'),
            },
            {'case_property': 'feeding_less',
            'question': _('Feeding Less/Stopped?'),
            },
            {'case_property': 'cry',
            'question': _('Cry Weak/Stopped?'),
            },
            {'case_property': 'abdomen_vomit',
            'question': _('Distant Abdomen?'),
            },
            {'case_property': 'cold',
            'question': _('Baby Cold to touch?'),
            },
            {'case_property': 'chest',
            'question': _('Chest Indrawing?'),
            },
            {'case_property': 'pus',
            'question': _('Pus on umbilicus?'),
            }]
        }
    ]),
)
