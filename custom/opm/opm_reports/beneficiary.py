"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers)
These are used in the Beneficiary Payment Report and Conditions Met Report
"""
import re
import datetime
from decimal import Decimal
from django.core.urlresolvers import reverse
from dimagi.utils.dates import months_between, first_of_next_month, add_months_to_date

from dimagi.utils.dates import add_months
from dimagi.utils.decorators import datespan
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


# replace all instances of 'child1' in a string with 'child{N}'
indexed_child = lambda prop, num: prop.replace("child1", "child" + str(num))


class OPMCaseRow(object):

    def __init__(self, case, report, child_index=1):
        self.child_index = child_index
        self.case = case
        self.report = report
        self.data_provider = report.data_provider
        self.block = report.block.lower()
        self.month = report.month
        self.year = report.year

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

    @property
    def datespan(self):
        return datespan.from_month(self.month, self.year)

    @property
    def reporting_window_end(self):
        return first_of_next_month(datetime.date(self.year, self.month, 1))

    @property
    def reporting_window_start(self):
        return datetime.date(self.year, self.month, 1)

    @property
    @memoized
    def case_id(self):
        return self.case._id

    @property
    @memoized
    def dod(self):
        return self.case_property('dod')

    @property
    @memoized
    def edd(self):
        return self.case_property('edd')

    @property
    @memoized
    def owner_id(self):
        return self.case_property('owner_id')

    @property
    @memoized
    def status(self):
        if self.dod is not None:
            # if they delivered within the reporting month, or afterwards they are treated as pregnant
            if self.dod > self.reporting_window_start:
                return 'pregnant'
            else:
                return 'mother'
        elif self.edd is not None:
            # they haven't delivered, so they're pregnant
            return 'pregnant'
        else:
            # no dates, not valid
            raise InvalidRow()

    @property
    @memoized
    def preg_month(self):
        if self.status == 'pregnant':
            base_window_start = add_months_to_date(self.edd, -9)
            non_adjusted_month = len(months_between(base_window_start, self.reporting_window_start)) - 1

            # the date to check one month after they first become eligible,
            # aka the end of their fourth month of pregnancy
            vhnd_date_to_check = add_months_to_date(self.preg_first_eligible_date, 1)

            month = self._adjust_for_vhnd_presence(non_adjusted_month, vhnd_date_to_check)
            if month < 4 or month > 9:
                raise InvalidRow('pregnancy month %s not valid' % month)
            return month

    @property
    def preg_month_display(self):
        return self.preg_month if self.preg_month is not None else EMPTY_FIELD

    @property
    @memoized
    def child_age(self):
        if self.status == 'mother':
            non_adjusted_month = len(months_between(self.dod, self.reporting_window_start)) - 1
            # anchor date should be their one month birthday
            anchor_date = add_months_to_date(self.dod, 1)

            month = self._adjust_for_vhnd_presence(non_adjusted_month, anchor_date)
            if month < 1:
                raise InvalidRow('child month %s not valid' % month)

            return month

    @property
    def child_age_display(self):
        return self.child_age if self.child_age is not None else EMPTY_FIELD

    def _adjust_for_vhnd_presence(self, non_adjusted_month, anchor_date_to_check):
        """
        check the base window month for a VHND after the anchor date.
        if no VHND occurs then the month is bumped back a month
        """
        # look at vhnds in the same month as the anchor date
        startdate = datetime.date(anchor_date_to_check.year, anchor_date_to_check.month, 1)
        enddate = first_of_next_month(startdate)
        vhnds_to_check = self.data_provider.get_dates_in_range(self.owner_id, startdate, enddate)

        # if any vhnd in the month occurred after the anchor date or it didn't occur at all, no need to adjust.
        # if it occurred before the anchor date, adjust, by subtracting one from the non-adjusted month
        adjust = max(vhnds_to_check) < anchor_date_to_check if vhnds_to_check else False
        return non_adjusted_month - 1 if adjust else non_adjusted_month

    @property
    @memoized
    def window(self):
        if self.status == 'pregnant':
            # 4, 5, 6 --> 1,
            # 7, 8, 9 --> 2
            return (self.preg_month - 1) / 3
        else:
            # 1, 2, 3 --> 3
            # 4, 5, 6 --> 4...
            return ((self.child_age - 1) / 3) + 3

    @property
    @memoized
    def preg_first_eligible_date(self):
        """
        The date we first start looking for mother data. This is the beginning of the 4th month of pregnancy.
        """
        if self.status == 'pregnant':
            return add_months_to_date(self.edd, -6)

    def set_case_properties(self):
        if self.child_age is None and self.preg_month is None:
            raise InvalidRow

        url = reverse("case_details", args=[DOMAIN, self.case_property('_id', '')])
        self.name = "<a href='%s'>%s</a>" % (url, self.case_property('name', EMPTY_FIELD))
        self.awc_name = self.case_property('awc_name', EMPTY_FIELD)
        self.block_name = self.case_property('block_name', EMPTY_FIELD)
        self.husband_name = self.case_property('husband_name', EMPTY_FIELD)
        self.bank_name = self.case_property('bank_name', EMPTY_FIELD)
        self.ifs_code = self.case_property('ifsc', EMPTY_FIELD)
        self.village = self.case_property('village_name', EMPTY_FIELD)
        self.closed = self.case_property('closed', False)

        account = self.case_property('bank_account_number', None)
        if isinstance(account, Decimal):
            account = int(account)
        self.account_number = unicode(account) if account else ''
        # fake cases will have accounts beginning with 111
        if re.match(r'^111', self.account_number):
            raise InvalidRow

    def condition_image(self, image_y, image_n, condition):
        if condition is None:
            return ''
        elif condition is True:
            return self.img_elem % image_y
        elif condition is False:
            return self.img_elem % image_n

    @property
    def preg_attended_vhnd(self):
        if self.status == 'pregnant':
            # in month 9 they always meet this condition
            if self.preg_month == 9:
                return True
            if not self.vhnd_available:
                return True
            elif 9 > self.preg_month > 3:
                def _legacy_method():
                    vhnd_attendance = {
                        4: self.case_property('attendance_vhnd_1', 0),
                        5: self.case_property('attendance_vhnd_2', 0),
                        6: self.case_property('attendance_vhnd_3', 0),
                        7: self.case_property('month_7_attended', 0),
                        8: self.case_property('month_8_attended', 0)
                    }
                    return vhnd_attendance[self.preg_month] == '1'

                def _new_method():
                    if self.preg_month == 4:
                        kwargs = {
                            'explicit_start': datetime.datetime.combine(self.preg_first_eligible_date,
                                                                        datetime.time())
                        }
                    else:
                        kwargs = {'months_before': 1}
                    return any(
                        form.xpath('form/pregnancy_questions/attendance_vhnd') == '1'
                        for form in self.filtered_forms(BIRTH_PREP_XMLNS, **kwargs)
                    )
                return _legacy_method() or _new_method()
            else:
                return False

    @property
    def child_attended_vhnd(self):
        if self.status == 'mother':
            if self.child_age == 1:
                return True
            elif not self.vhnd_available:
                return True
            else:
                return any(
                    form.xpath('form/child_1/child1_attendance_vhnd') == '1'
                    for form in self.filtered_forms(CHILDREN_FORMS, 1)
                )

    @property
    def preg_weighed(self):
        if self.preg_month == 6:
            return self.case_property('weight_tri_1') == 'received'
        elif self.preg_month == 9:
            return self.case_property('weight_tri_2') == 'received'

    def filtered_forms(self, xmlns_or_list=None, months_before=None, months_after=None, explicit_start=None):
        """
        Returns a list of forms filtered by xmlns if specified
        and from the previous number of calendar months if specified
        """
        if isinstance(xmlns_or_list, basestring):
            xmlns_list = [xmlns_or_list]
        else:
            xmlns_list = xmlns_or_list or []

        if months_before is not None:
            new_year, new_month = add_months(self.year, self.month, -months_before)
            start = first_of_next_month(datetime.datetime(new_year, new_month, 1))
        else:
            start = explicit_start

        if months_after is not None:
            new_year, new_month = add_months(self.year, self.month, months_after)
            end = first_of_next_month(datetime.datetime(new_year, new_month, 1))
        else:
            end = datetime.datetime.combine(self.reporting_window_end, datetime.time())

        def check_form(form):
            if xmlns_list and form.xmlns not in xmlns_list:
                return False
            if start and form.received_on < start:
                return False
            if end and form.received_on >= end:
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
            if self.block == "atri":
                return self.case_property('ifa_tri_1', 0) == 'received'

    @property
    def child_received_ors(self):
        if self.child_age % 3 == 0:
            for form in self.filtered_forms(CHILDREN_FORMS, 3):
                prop = indexed_child('child1_child_orszntreat', self.child_index)
                if form.form.get(prop) == '0':
                    return False
            return True

    @property
    def child_weighed_once(self):
        if self.child_age == 3:
            def _test(form):
                return form.xpath(indexed_child('form/child_1/child1_child_weight', self.child_index)) == '1'

            return any(
                _test(form)
                for form in self.filtered_forms(CFU1_XMLNS, 3)
            )

    @property
    def child_birth_registered(self):
        if self.child_age == 6:
            def _test(form):
                return form.xpath(indexed_child('form/child_1/child1_child_register', self.child_index)) == '1'

            return any(
                _test(form)
                for form in self.filtered_forms(CFU1_XMLNS, 3)
            )

    @property
    def child_received_measles_vaccine(self):
        if self.child_age == 12:
            def _test(form):
                return form.xpath(indexed_child('form/child_1/child1_child_measlesvacc', self.child_index)) == '1'

            return any(
                _test(form)
                for form in self.filtered_forms([CFU1_XMLNS, CFU2_XMLNS],3)
            )

    @property
    def child_condition_four(self):
        if self.block == 'atri':
            if self.child_age == 3:
                return self.child_weighed_once
            elif self.child_age == 6:
                return self.child_birth_registered
            elif self.child_age == 12:
                return self.child_received_measles_vaccine

    @property
    def child_breastfed(self):
        if self.child_age == 6 and self.block == 'atri':
            excl_key = indexed_child("child1_child_excbreastfed", self.child_index)
            for form in self.filtered_forms(CHILDREN_FORMS):
                if form.form.get(excl_key) == '0':
                    return False
            return True

    @property
    def live_delivery(self):
        # TODO czue, please verify the dates here, it should only be looking at
        # delivery forms submitted in the last month, but I'm seeing some cases
        # with child_age as 2 or 3, which is inconsistent.  Uncomment the print
        # lines below and run the report to replicate. (block: Atri, gp: Sahora
        # are the filters I'm using)
        for form in self.filtered_forms(DELIVERY_XMLNS, months_before=1):
            outcome = form.form.get('mother_preg_outcome')
            if outcome == '1':
                # print "*"*40, 'live_delivery', "*"*40
                # print self.child_age
                # print form.received_on
                return True
            elif outcome in ['2', '3']:
                return False

    @property
    def birth_spacing_years(self):
        """
        returns None if inapplicable, False if not met, or
        2 for 2 years, or 3 for 3 years.
        """
        if self.child_age in [24, 36]:
            for form in self.filtered_forms(CHILDREN_FORMS):
                if form.form.get('birth_spacing_prompt') == '1':
                    return False
            return self.child_age/12

    def case_property(self, name, default=None):
        prop = getattr(self.case, name, default)
        if isinstance(prop, basestring) and prop.strip() == "":
            return default
        return prop

    def form_in_range(self, form):
        # todo: the reporting window might be different than that data window
        return self.reporting_window_start <= form.received_on.date() < self.reporting_window_end

    @property
    @memoized
    def vhnd_available(self):
        return bool(self.data_provider.get_dates_in_range(self.owner_id,
                                                          self.reporting_window_start,
                                                          self.reporting_window_end))

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
            ('preg_month_display', _('Pregnancy Month'), True),
            ('child_name', _("Child Name"), True),
            ('child_age_display', _("Child Age"), True),
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
            ('preg_month_display', _('Pregnancy Month'), True),
            ('child_name', _("Child Name"), True),
            ('child_age_display', _("Child Age"), True),
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

        if self.child_age in (24, 36):
            if self.birth_spacing_years:
                self.five = self.img_elem % SPACING_PROMPT_Y
            elif self.birth_spacing_years is False:
                self.five = self.img_elem % SPACING_PROMPT_N
            else:
                self.five = ''

        if not self.vhnd_available:
            # TODO what if they don't meet the other conditions?
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
        self.delivery_cash = MONTH_AMT if self.live_delivery else 0
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
        if 3 < self.preg_month < 7:
            return self.bp_conditions

    @property
    def bp2(self):
        if 6 < self.preg_month < 10:
            return self.bp_conditions

    @property
    def bp_conditions(self):
        if self.status == "pregnant":
            return False not in [
                self.preg_attended_vhnd,
                self.preg_weighed,
                self.preg_received_ifa,
            ]

    @property
    def child_followup(self):
        """
        wazirganj - total_soft_conditions = 1
        """
        if self.status == 'mother':
            return False not in [
                self.child_attended_vhnd,
                self.child_received_ors,
                self.child_growth_calculated,
                self.child_weighed_once,
                self.child_birth_registered,
                self.child_received_measles_vaccine,
                self.child_breastfed,
            ]
