"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers)
These are used in the Beneficiary Payment Report and Conditions Met Report
"""
import re
import datetime
from decimal import Decimal
from django.core.urlresolvers import reverse
from dimagi.utils.dates import months_between

from dimagi.utils.dates import add_months
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _

from corehq.util.translation import localize

from .constants import *


EMPTY_FIELD = "---"
M_ATTENDANCE_Y = 'attendance_vhnd_y.png'
M_ATTENDANCE_N = 'attendance_vhnd_n.png'
C_ATTENDANCE_Y = 'child_attendance_vhnd_y.png'
C_ATTENDANCE_N = 'child_attendance_vhnd_n.png'
M_WEIGHT_Y = 'woman_checking_weight_yes.png'
M_WEIGHT_N = 'woman_checking_weight_no.png'
C_WEIGHT_Y = 'child_weight_y.png'
C_WEIGHT_N = 'child_weight_n.png'
MEASLEVACC_Y = 'child_child_measlesvacc_y.png'
MEASLEVACC_N = 'child_child_measlesvacc_n.png'
C_REGISTER_Y = 'child_child_register_y.png'
C_REGISTER_N = 'child_child_register_n.png'
CHILD_WEIGHT_Y = 'child_weight_2_y.png'
CHILD_WEIGHT_N = 'child_weight_2_n.png'
IFA_Y = 'ifa_receive_y.png'
IFA_N = 'ifa_receive_n.png'
EXCBREASTFED_Y = 'child_child_excbreastfed_y.png'
EXCBREASTFED_N = 'child_child_excbreastfed_n.png'
ORSZNTREAT_Y = 'child_orszntreat_y.png'
ORSZNTREAT_N = 'child_orszntreat_n.png'
GRADE_NORMAL_Y = 'grade_normal_y.png'
GRADE_NORMAL_N = 'grade_normal_n.png'
SPACING_PROMPT_Y = 'birth_spacing_prompt_y.png'
SPACING_PROMPT_N = 'birth_spacing_prompt_n.png'
VHND_NO = 'VHND_no.png'


# This is just a string processing function, not moving to class
indexed_child = lambda prop, num: prop.replace("child1", "child" + str(num))


class OPMCaseRow(object):

    def __init__(self, case, report, child_index=1):
        self.child_index = child_index
        self.case = case
        self.report = report
        self.data_provider = report.data_provider
        self.block = report.block.lower()
        self.datespan = self.report.datespan

        if report.snapshot is not None:
            report.filter(
                lambda key: self.case[key],
                # case.awc_name, case.block_name
                [('awc_name', 'awcs'), ('block_name', 'block'), ('owner_id', 'gp'), ('closed', 'is_open')],
            )
        if not report.is_rendered_as_email:
            self.img_elem = '<div style="width:100px !important;"><img src="/static/opm/img/%s"></div>'
        else:
            self.img_elem = '<div><img src="/static/opm/img/%s"></div>'

        self.set_case_properties()
        self.add_extra_children()

        if report.is_rendered_as_email:
            with localize('hin'):
                self.status = _(self.status)

    def condition_image(self, image_y, image_n, condition):
        if condition is None:
            return ''
        elif condition is True:
            return self.img_elem % image_y
        elif condition is False:
            return self.img_elem % image_n

    @property
    @memoized
    def form_properties(self):
        # TODO this isn't the best way to do this - these properties come
        # from a number of different forms, and how do we know which value
        # to store for each property if there are multiple forms?
        # The names are diverse enough that I don't think we have to worry
        # about name clashes, but a better way would be to store a set of
        # all values for each property and/or split these up by form xmlns
        properties = {
            'window_1_1': None,
            'window_1_2': None,
            'window_1_3': None,
            'soft_window_1_3': None,
            'window_2_1': None,
            'window_2_2': None,
            'window_2_3': None,
            'soft_window_2_3': None,
            'attendance_vhnd_3': None,
            'attendance_vhnd_6': None,
            indexed_child('child1_vhndattend_calc', self.child_index): None,
            indexed_child('prev_child1_vhndattend_calc', self.child_index): None,
            indexed_child('child1_attendance_vhnd', self.child_index): None,
            'weight_tri_1': None,
            'prev_weight_tri_1': None,
            'weight_tri_2': None,
            'prev_weight_tri_2': None,
            indexed_child('child1_growthmon_calc', self.child_index): None,
            indexed_child('prev_child1_growthmon_calc', self.child_index): None,
            indexed_child('child1_excl_breastfeed_calc', self.child_index): None,
            indexed_child('prev_child1_excl_breastfeed_calc', self.child_index): None,
            indexed_child('child1_ors_calc', self.child_index): None,
            indexed_child('prev_child1_ors_calc', self.child_index): None,
            indexed_child('child1_weight_calc', self.child_index): None,
            indexed_child('child1_register_calc', self.child_index): None,
            indexed_child('child1_measles_calc', self.child_index): None,
            indexed_child('prev_child1_weight_calc', self.child_index): None,
            indexed_child('prev_child1_register_calc', self.child_index): None,
            indexed_child('prev_child1_measles_calc', self.child_index): None,
            indexed_child('child1_suffer_diarrhea', self.child_index): None,
            'interpret_grade_1': None,
        }
        for form in self.forms:
            if self.form_in_range(form):
                for prop in properties:
                    if prop == indexed_child('child1_suffer_diarrhea', self.child_index):
                        child_group = "child_" + str(self.child_index)
                        if child_group in form.form and prop in form.form[child_group]:
                            properties[prop] = form.form[child_group][prop]
                    else:
                        # TODO is this right?  Multiple matching forms will overwrite
                        if prop in form.form:
                            properties[prop] = form.form[prop]
        return properties

    @property
    def preg_attended_vhnd(self):
        # in month 9 they always meet this condition
        if self.preg_month == 9:
            return True
        elif not self.vhnd_available:
            return True
        elif 9 > self.preg_month > 3:
            vhnd_attendance = {
                4: self.case_property('attendance_vhnd_1', 0),
                5: self.case_property('attendance_vhnd_2', 0),
                6: self.case_property('attendance_vhnd_3', 0),
                7: self.case_property('month_7_attended', 0),
                8: self.case_property('month_8_attended', 0)
            }
            return vhnd_attendance[self.preg_month] == '1'
        else:
            return False

    # TODO abstract this pattern of looking for received in form_property s
    # and in case_property s
    @property
    def child_attended_vhnd(self):
        if self.child_age == 1:
            return True
        elif not self.vhnd_available:
            return True
        else:
            return any(
                form.form.get(indexed_child('child1_vhndattend_calc', self.child_index)) == 'received'
                for form in self.forms
                if form.xmlns in CHILDREN_FORMS and self.form_in_range(form)
            )

    @property
    def preg_weighed(self):
        if self.preg_month == 6:
            return self.case_property('weight_tri_1') == 'received'
        elif self.preg_month == 9:
            return self.case_property('weight_tri_2') == 'received'

    def filtered_forms(self, xmlns_or_list=None, num_months=None):
        """
        Returns a list of forms filtered by xmlns if specified
        and from the previous number of calendar months if specified
        """
        if not isinstance(xmlns_or_list, list):
            xmlns_list = [xmlns_or_list]
        else:
            xmlns_list = xmlns_or_list
        end = self.datespan.enddate
        if num_months is not None:
            new_year, new_month = add_months(end.year, end.month, -num_months)
            start = end.replace(month=new_month, year=new_year)
        else:
            start = None
        def check_form(form):
            if xmlns_or_list and form.xmlns not in xmlns_list:
                return False
            if start and form.received_on <= start:
                return False
            if end and form.received_on > end:
                return False
            return True
        return filter(check_form, self.forms)

    @property
    def child_growth_calculated(self):
        if self.child_age % 3 == 0:
            for form in self.filtered_forms(CHILDREN_FORMS, 3):
                prop = indexed_child('child1_growthmon_calc', self.child_index)
                if form.form.get(prop) == 'received':
                    return True
            return False

    @property
    def preg_received_ifa(self):
        if self.preg_month == 6:
            if self.block== "atri":
                return self.case_property('ifa_tri_1', 0) == 'received'

    @property
    def child_received_ors(self):
        if self.child_age % 3 == 0:
            if self.form_properties[indexed_child('child1_suffer_diarrhea', self.child_index)] == '1':
                return 'received' in [
                    self.form_properties[indexed_child('child1_ors_calc', self.child_index)],
                    self.form_properties[indexed_child('prev_child1_ors_calc', self.child_index)]
                ]

    @property
    def child_condition_four(self):
        # TODO This appears to be one of several unrelated conditions
        # depending on the child's age, I think it's wrong
        if self.block == 'atri':
            if self.child_age == 3:
                # TODO reformat
                prev_forms = [form for form in self.forms
                        if (self.datespan.startdate - datetime.timedelta(90))
                            <= form.received_on <= self.datespan.enddate]
                weight_key = indexed_child("child1_child_weight", self.child_index)
                prev_forms = [form for form in self.forms if self.form_in_range(form, adjust_lower=-90)]
                child_group = "child_" + str(self.child_index)
                child_forms = [form.form[child_group] for form in prev_forms if child_group in form.form]
                birth_weight = {child[weight_key] for child in child_forms if weight_key in child}
                child_birth_weight_taken = '1' in birth_weight
                return child_birth_weight_taken
            elif self.child_age == 6:
                return 'received' in [
                    self.form_properties[indexed_child('child1_register_calc', self.child_index)],
                    self.form_properties[indexed_child('prev_child1_register_calc', self.child_index)]
                ]
            elif self.child_age == 12:
                return 'received' in [
                    self.form_properties[indexed_child('child1_measles_calc', self.child_index)],
                    self.form_properties[indexed_child('prev_child1_measles_calc', self.child_index)]
                ]

    @property
    def child_breastfed(self):
        if self.child_age == 6 and self.block == 'atri':
            excl_key = indexed_child("child1_child_excbreastfed", self.child_index)
            for form in self.filtered_forms(CHILDREN_FORMS):
                if form.form.get(excl_key) == '0':
                    return False
            return True

    @property
    def birth_spacing_years(self):
        """
        returns None if inapplicable, False if not met, or
        2 for 2 years, or 3 for 3 years.
        """
        # TODO should this actually be [25, 37] ?
        if self.child_age in [24, 36]:
            for form in self.filtered_forms(CHILDREN_FORMS):
                if form.form.get('birth_spacing_prompt') == '1':
                    return False
            return self.child_age/12

    def case_property(self, name, default=None):
        return getattr(self.case, name, default)

    def form_in_range(self, form, adjust_lower=0):
        lower = self.datespan.startdate + datetime.timedelta(days=adjust_lower)
        upper = self.datespan.enddate
        return lower <= form.received_on <= upper

    def set_case_properties(self):
        reporting_date = self.datespan.enddate.date()  # last day of the month
        status = "unknown"
        self.preg_month = None
        self.child_age = None
        window = None
        dod_date = self.case_property('dod')
        edd_date = self.case_property('edd')
        if dod_date:
            if dod_date > reporting_date:
                status = 'pregnant'
                self.preg_month = 9 - (dod_date - reporting_date).days / 30  # edge case
            elif dod_date < reporting_date:
                status = 'mother'
                self.child_age = len(months_between(dod_date, reporting_date))
        elif edd_date:
            if edd_date >= reporting_date:
                status = 'pregnant'
                self.preg_month = 9 - (edd_date - reporting_date).days / 30
            elif edd_date < reporting_date:  # edge case
                raise InvalidRow
        else: #if dod_date is None and edd_date is None:
            raise InvalidRow
        if status == 'pregnant' and (self.preg_month > 3 and self.preg_month < 10):
            self.window = (self.preg_month - 1) / 3
        elif status == 'mother' and (self.child_age > 0 and self.child_age < 37):
            self.window = (self.child_age - 1) / 3 + 1
        else:
            raise InvalidRow
        if (self.child_age is None and self.preg_month is None):
            raise InvalidRow

        self.status = status

        url = reverse("case_details", args=[DOMAIN, self.case_property('_id', '')])
        self.name = "<a href='%s'>%s</a>" % (url, self.case_property('name', EMPTY_FIELD))
        self.awc_name = self.case_property('awc_name', EMPTY_FIELD)
        self.block_name = self.case_property('block_name', EMPTY_FIELD)
        self.husband_name = self.case_property('husband_name', EMPTY_FIELD)
        self.bank_name = self.case_property('bank_name', EMPTY_FIELD)
        self.ifs_code = self.case_property('ifsc', EMPTY_FIELD)
        self.village = self.case_property('village_name', EMPTY_FIELD)
        self.case_id = self.case_property('_id', EMPTY_FIELD)
        self.owner_id = self.case_property('owner_id', '')
        self.closed = self.case_property('closed', False)

        account = self.case_property('bank_account_number', None)
        if isinstance(account, Decimal):
            account = int(account)
        self.account_number = unicode(account) if account else ''
        # fake cases will have accounts beginning with 111
        if re.match(r'^111', self.account_number):
            raise InvalidRow

    @property
    @memoized
    def vhnd_available(self):
        if self.owner_id not in self.data_provider.vhnd_availability:
            raise InvalidRow
        return self.data_provider.vhnd_availability[self.owner_id]

    def add_extra_children(self):
        if self.child_index == 1:
            # app supports up to three children only
            num_children = min(int(self.case_property("live_birth_amount", 1)), 3)
            if num_children > 1:
                extra_child_objects = [(ConditionsMet(self.case, self.report, child_index=num + 2)) for num in range(num_children - 1)]
                self.report.set_extra_row_objects(extra_child_objects)

    @property
    @memoized
    def forms(self):
        return self.case.get_forms()

    @property
    def all_conditions_met(self):
        if not self.vhnd_available:
            return True
        if self.status == 'mother':
            relevant_conditions = [
                self.child_attended_vhnd,
                self.child_growth_calculated,
                self.child_received_ors,
                self.child_condition_four,
                self.child_breastfed,
            ]
        else:
            relevant_conditions = [
                self.preg_attended_vhnd,
                self.preg_weighed,
                self.preg_received_ifa,
            ]
        return False not in relevant_conditions

    @property
    def month_amt(self):
        return MONTH_AMT if self.all_conditions_met else 0

    @property
    def spacing_cash(self):
        return {
            2: TWO_YEAR_AMT,
            3: THREE_YEAR_AMT,
        }.get(self.birth_spacing_years, 0)

    @property
    def cash_amt(self):
        return self.month_amt + self.spacing_cash

    @property
    def cash(self):
        cash_html = '<span style="color: {color};">Rs. {amt}</span>'
        return cash_html.format(
            color="red" if self.cash_amt == 0 else "green",
            amt=self.cash_amt,
        )


class ConditionsMet(OPMCaseRow):
    method_map = {
        "atri": [
            ('name', _("List of Beneficiary"), True),
            ('awc_name', _("AWC Name"), True),
            ('block_name', _("Block Name"), True),
            ('husband_name', _("Husband Name"), True),
            ('status', _("Current status"), True),
            ('preg_month', _('Pregnancy Month'), True),
            ('child_name', _("Child Name"), True),
            ('child_age', _("Child Age"), True),
            ('window', _("Window"), True),
            ('one', _("1"), True),
            ('two', _("2"), True),
            ('three', _("3"), True),
            ('four', _("4"), True),
            ('five', _("5"), True),
            ('cash', _("Payment Amount"), True),
            ('case_id', _('Case ID'), True),
            ('owner_id', _("Owner Id"), False),
            ('closed', _('Closed'), False)
        ],
        'wazirganj': [
            ('name', _("List of Beneficiary"), True),
            ('awc_name', _("AWC Name"), True),
            ('block_name', _("Block Name"), True),
            ('husband_name', _("Husband Name"), True),
            ('status', _("Current status"), True),
            ('preg_month', _('Pregnancy Month'), True),
            ('child_name', _("Child Name"), True),
            ('child_age', _("Child Age"), True),
            ('window', _("Window"), True),
            ('one', _("1"), True),
            ('two', _("2"), True),
            ('three', _("3"), True),
            ('four', _("4"), True),
            ('cash', _("Payment Amount"), True),
            ('case_id', _('Case ID'), True),
            ('owner_id', _("Owner Id"), False),
            ('closed', _('Closed'), False)
        ]
    }

    def __init__(self, case, report, child_index=1):
        super(ConditionsMet, self).__init__(case, report, child_index=child_index)
        if self.status == 'mother':
            self.child_name = self.case_property(indexed_child("child1_name", child_index), EMPTY_FIELD)
            self.preg_month = EMPTY_FIELD
            self.one = self.condition_image(C_ATTENDANCE_Y, C_ATTENDANCE_N, self.child_attended_vhnd)
            self.two = self.condition_image(C_WEIGHT_Y, C_WEIGHT_N, self.child_growth_calculated)
            self.three = self.condition_image(ORSZNTREAT_Y, ORSZNTREAT_N, self.child_received_ors)
            self.four = self.condition_image(MEASLEVACC_Y, MEASLEVACC_N, self.child_condition_four)
            self.five = self.condition_image(EXCBREASTFED_Y, EXCBREASTFED_N, self.child_breastfed)
        elif self.status == 'pregnant':
            self.child_name = EMPTY_FIELD
            self.one = self.condition_image(M_ATTENDANCE_Y, M_ATTENDANCE_N, self.preg_attended_vhnd)
            self.two = self.condition_image(M_WEIGHT_Y, M_WEIGHT_N, self.preg_weighed)
            self.three = self.condition_image(IFA_Y, IFA_N, self.preg_received_ifa)
            self.four = ''
            self.five = ''

        # This is what I think is meant by this stuff
        # https://github.com/dimagi/commcare-hq/blob/cacf077042edb23c1167563c5127b810dbcd555a/custom/opm/opm_reports/conditions_met.py#L297-L314
        if self.child_age in (24, 36):
            if self.birth_spacing_years:
                self.five = self.img_elem % SPACING_PROMPT_Y
            elif self.birth_spacing_years is False:
                self.five = self.img_elem % SPACING_PROMPT_N
            else:
                self.five = ''

        if not self.vhnd_available:
            met_or_not = True
            self.one = self.img_elem % VHND_NO
            self.two, self.three, self.four, self.five = '','','',''


class Beneficiary(OPMCaseRow):
    """
    Constructor object for each row in the Beneficiary Payment Report
    """
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', _("List of Beneficiaries"), True),
        ('husband_name', _("Husband Name"), True),
        ('awc_name', _("AWC Name"), True),
        ('bank_name', _("Bank Name"), True),
        ('ifs_code', _("IFS Code"), True),
        ('account_number', _("Bank Account Number"), True),
        ('block_name', _("Block Name"), True),
        ('village', _("Village Name"), True),
        ('bp1_cash', _("Birth Preparedness Form 1"), True),
        ('bp2_cash', _("Birth Preparedness Form 2"), True),
        ('delivery_cash', _("Delivery Form"), True),
        ('child_cash', _("Child Followup Form"), True),
        ('spacing_cash', _("Birth Spacing Bonus"), True),
        ('total', _("Amount to be paid to beneficiary"), True),
        ('owner_id', _("Owner ID"), False)
    ]

    def __init__(self, case, report):
        super(Beneficiary, self).__init__(case, report)
        self.bp1_cash = MONTH_AMT if self.bp1 else 0
        self.bp2_cash = MONTH_AMT if self.bp2 else 0
        self.delivery_cash = MONTH_AMT if self.delivery else 0
        self.child_cash = MONTH_AMT if self.child_followup else 0
        self.total = min(
            MONTH_AMT,
            self.bp1_cash + self.bp2_cash + self.delivery_cash + self.child_cash
        )
        # Show only cases that require payment
        if self.total == 0:
            raise InvalidRow

    @property
    def bp1(self):
        if self.block == 'atri':
            properties = ['window_1_1', 'window_1_2', 'window_1_3']
        else:
            properties = ['window_1_1', 'window_1_2', 'soft_window_1_3']
        for prop in properties:
            if self.form_properties[prop] == '1':
                return True
        return False

    @property
    def bp2(self):
        if self.block == 'atri':
            properties = ['window_2_1', 'window_2_2', 'window_2_3']
        else:
            properties = ['window_2_1', 'window_2_2', 'soft_window_2_3']
        for prop in properties:
            if self.form_properties[prop] == '1':
                return True
        return False

    @property
    def delivery(self):
        for form in self.forms:
            if form.xmlns == DELIVERY_XMLNS:
                if form.form.get('mother_preg_outcome') in ['2', '3']:
                    return True
        return False

    @property
    def child_followup(self):
        """
        wazirganj - total_soft_conditions = 1
        """
        xmlns_list = CHILDREN_FORMS + [CHILD_FOLLOWUP_XMLNS]
        for form in self.forms:
            if form.xmlns in CHILDREN_FORMS:
                if self.block == "wazirganj":
                    if form.form.get("total_soft_conditions", 0) == 1:
                        return True
                else:
                    # TODO Sravan, is there an aggregated calc in the app?
                    for prop in [
                        'window%d_child%d' % (window, child)
                        for window in range(3, 15) for child in range(1, 4)
                    ]:
                        if form.form.get(prop) == 1:
                            return True
        return False
