# coding=utf-8
"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers)
These are used in the Beneficiary Payment Report and Conditions Met Report
"""
import re
import datetime
from decimal import Decimal
from django.core.urlresolvers import reverse
from django.template.defaultfilters import yesno
from corehq.apps.reports.datatables import DTSortType
from custom.opm.constants import InvalidRow, BIRTH_PREP_XMLNS, CHILDREN_FORMS, CFU1_XMLNS, DOMAIN, CFU2_XMLNS, \
    MONTH_AMT, TWO_YEAR_AMT, THREE_YEAR_AMT
from custom.opm.utils import numeric_fn
from dimagi.utils.dates import months_between, first_of_next_month, add_months_to_date

from dimagi.utils.dates import add_months
from dimagi.utils.decorators import datespan
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq.util.translation import localize


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


class OPMCaseRow(object):

    def __init__(self, case, report, child_index=1, is_secondary=False, explicit_month=None, explicit_year=None):
        self.child_index = child_index
        self.case = case
        self.report = report
        self.data_provider = report.data_provider
        self.block = report.block.lower()
        self.month = explicit_month or report.month
        self.year = explicit_year or report.year
        self.is_secondary = is_secondary
        self.case_is_out_of_range = False

        if not report.is_rendered_as_email:
            self.img_elem = '<div style="width:160px !important;"><img src="/static/opm/img/%s">' \
                            '<text class="image-descriptor" style="display:none">%s</text></div>'
        else:
            self.img_elem = '<div><img src="/static/opm/img/%s"><text class="image-descriptor" ' \
                            'style="display:none">%s</text></div>'

        self.set_case_properties()
        self.last_month_row = None
        if not is_secondary:
            self.add_extra_children()
            # if we were called directly, set the last month's row on this
            last_year, last_month = add_months(self.year, self.month, -1)
            try:
                self.last_month_row = OPMCaseRow(case, report, 1, is_secondary=True,
                                                 explicit_month=last_month, explicit_year=last_year)
            except InvalidRow:
                pass

    @property
    def readable_status(self):
        if self.report.is_rendered_as_email:
            with localize('hin'):
                return _(self.status)
        return self.status

    def child_xpath(self, template):
        return template.format(num=self.child_index)

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

    def get_date_property(self, property):
        prop = self.case_property(property)
        if prop and not isinstance(prop, datetime.date):
            raise InvalidRow("{} must be a date!".format(property))
        return prop

    @property
    @memoized
    def dod(self):
        return self.get_date_property('dod')

    @property
    @memoized
    def edd(self):
        return self.get_date_property('edd')

    @property
    @memoized
    def lmp(self):
        return self.get_date_property('lmp_date')

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
            raise InvalidRow("Case doesn't specify an EDD or DOD.")

    @property
    @memoized
    def preg_month(self):
        if self.status == 'pregnant':
            if not self.edd:
                raise InvalidRow('No edd found for pregnant mother.')
            base_window_start = add_months_to_date(self.edd, -9)
            try:
                non_adjusted_month = len(months_between(base_window_start, self.reporting_window_start)) - 1
            except AssertionError:
                self.case_is_out_of_range = True
                non_adjusted_month = 0

            # the date to check one month after they first become eligible,
            # aka the end of their fourth month of pregnancy
            vhnd_date_to_check = add_months_to_date(self.preg_first_eligible_date, 1)

            month = self._adjust_for_vhnd_presence(non_adjusted_month, vhnd_date_to_check)
            if month < 4 or month > 9:
                self.case_is_out_of_range = True
            return month

    @property
    def preg_month_display(self):
        return numeric_fn(self.preg_month) if self.preg_month is not None else EMPTY_FIELD

    @property
    @memoized
    def child_age(self):
        if self.status == 'mother':
            non_adjusted_month = len(months_between(self.dod, self.reporting_window_start)) - 1
            # anchor date should be their one month birthday
            anchor_date = add_months_to_date(self.dod, 1)

            month = self._adjust_for_vhnd_presence(non_adjusted_month, anchor_date)
            if month < 1:
                self.case_is_out_of_range = True
            return month

    @property
    def child_age_display(self):
        return numeric_fn(self.child_age) if self.child_age is not None else EMPTY_FIELD

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
    def preg_first_eligible_date(self):
        """
        The date we first start looking for mother data. This is the beginning of the 4th month of pregnancy.
        """
        if self.status == 'pregnant':
            return add_months_to_date(self.edd, -6)

    @property
    def preg_first_eligible_datetime(self):
        """
        The date we first start looking for mother data. This is the beginning of the 4th month of pregnancy.
        """
        date = self.preg_first_eligible_date
        if date:
            return datetime.datetime.combine(date, datetime.time())

    def set_case_properties(self):
        if self.child_age is None and self.preg_month is None:
            raise InvalidRow("Window not found")

        if self.window > 14:
            self.case_is_out_of_range = True

        name = self.case_property('name', EMPTY_FIELD)
        if getattr(self.report,  'show_html', True):
            url = reverse("case_details", args=[DOMAIN, self.case_property('_id', '')])
            self.name = "<a href='%s'>%s</a>" % (url, name)
        else:
            self.name = name
        self.awc_name = self.case_property('awc_name', EMPTY_FIELD)
        self.block_name = self.case_property('block_name', EMPTY_FIELD)
        self.husband_name = self.case_property('husband_name', EMPTY_FIELD)
        self.bank_name = self.case_property('bank_name', EMPTY_FIELD)
        self.bank_branch_name = self.case_property('bank_branch_name', EMPTY_FIELD)
        self.ifs_code = self.case_property('ifsc', EMPTY_FIELD)
        self.village = self.case_property('village_name', EMPTY_FIELD)
        self.closed = self.case_property('closed', False)

        account = self.case_property('bank_account_number', None)
        if isinstance(account, Decimal):
            account = int(account)
        self.account_number = unicode(account) if account else ''
        # fake cases will have accounts beginning with 111
        if re.match(r'^111', self.account_number):
            raise InvalidRow("Account begins with 111, assuming test case")

    @property
    def closed_date(self):
        if not self.closed:
            return EMPTY_FIELD
        return str(self.case_property('closed_on', EMPTY_FIELD))

    @property
    def closed_in_reporting_month(self):
        if not self.closed:
            return False

        closed_datetime = self.case_property('closed_on', EMPTY_FIELD)
        if closed_datetime and not isinstance(closed_datetime, datetime.datetime):
            raise InvalidRow('Closed date is not of datetime.datetime type')
        closed_date = closed_datetime.date()
        return closed_date >= self.reporting_window_start and\
            closed_date < self.reporting_window_end

    def condition_image(self, image_y, image_n, descriptor_y, descriptor_n, condition):
        if condition is None:
            return ''
        elif condition is True:
            return self.img_elem % (image_y, descriptor_y)
        elif condition is False:
            return self.img_elem % (image_n, descriptor_n)

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
                            'explicit_start': self.preg_first_eligible_datetime
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
                    form.xpath(self.child_xpath('form/child_{num}/child{num}_attendance_vhnd')) == '1'
                    for form in self.filtered_forms(CHILDREN_FORMS, 1)
                )

    @property
    def preg_weighed(self):
        return self.preg_weighed_trimestered(self.preg_month)

    def preg_weighed_trimestered(self, query_preg_month):
        def _from_case(property):
            return self.case_property(property, 0) == 'received'

        def _from_forms(filter_kwargs):
            return any(
                form.xpath('form/pregnancy_questions/mother_weight') == '1'
                for form in self.filtered_forms(BIRTH_PREP_XMLNS, **filter_kwargs)
            )

        if self.preg_month == 6 and query_preg_month == 6:
            if not self.is_service_available('func_bigweighmach', months=3):
                return True

            return _from_case('weight_tri_1') or _from_forms({'explicit_start': self.preg_first_eligible_datetime})
        elif self.preg_month == 9 and query_preg_month == 9:
            if not self.is_service_available('func_bigweighmach', months=3):
                return True

            return _from_case('weight_tri_2') or _from_forms({'months_before': 3})

    def get_months_before(self, months_before=None):
        new_year, new_month = add_months(self.year, self.month, -months_before)
        return first_of_next_month(datetime.datetime(new_year, new_month, 1))

    def get_months_after(self, months_after=None):
        new_year, new_month = add_months(self.year, self.month, months_after)
        return first_of_next_month(datetime.datetime(new_year, new_month, 1))

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
            start = self.get_months_before(months_before)
        else:
            start = explicit_start

        if months_after is not None:
            end = self.get_months_after(months_after)
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
        if self.child_age and self.child_age % 3 == 0:
            if not self.is_service_available('func_childweighmach', months=3):
                return True

            xpath = self.child_xpath('form/child_{num}/child{num}_child_growthmon')
            return any(
                form.xpath(xpath) == '1'
                for form in self.filtered_forms(CHILDREN_FORMS, 3)
            )

    @property
    def growth_calculated_aww(self):
        """
        For the AWW we don't factor in the month window into growth calculations
        """
        xpath = self.child_xpath('form/child_{num}/child{num}_child_growthmon')
        return any(
            form.xpath(xpath) == '1'
            for form in self.filtered_forms(CHILDREN_FORMS, 1)
        )

    def child_growth_calculated_in_window(self, query_age):
        """
            query_age - must be last month of a window, multiple of 3
            given last month of a window, this returns if
            the child in that window attended at least 1 growth session or not
        """
        # do not handle middle months of a window
        if query_age is 0 or query_age % 3 != 0:
            return None
        if self.child_age in [query_age - 2, query_age - 1, query_age]:
            months_in_window = self.child_age % 3 or 3
            if not self.is_service_available('func_childweighmach', months=months_in_window):
                return True

            xpath = self.child_xpath('form/child_{num}/child{num}_child_growthmon')
            return any(
                form.xpath(xpath) == '1'
                for form in self.filtered_forms(CHILDREN_FORMS, months_in_window)
            )

    @property
    def preg_received_ifa(self):
        if self.preg_month == 6:
            if self.block == "atri":
                if not self.is_service_available('stock_ifatab', months=3):
                    return True

                def _from_case():
                    return self.case_property('ifa_tri_1', 0) == 'received'

                def _from_forms():
                    return any(
                        form.xpath('form/pregnancy_questions/ifa_receive') == '1'
                        for form in self.filtered_forms(BIRTH_PREP_XMLNS,
                                                        explicit_start=self.preg_first_eligible_datetime)
                    )
                return _from_case() or _from_forms()

    @property
    def child_received_ors(self):
        if self.child_age % 3 == 0:
            if not self.is_service_available('stock_ors', months=3):
                return True

            for form in self.filtered_forms(CHILDREN_FORMS, 3):
                xpath = self.child_xpath('form/child_{num}/child{num}_child_orszntreat')
                if form.xpath(xpath) == '0':
                    return False
            return True

    @property
    def child_with_diarhea_received_ors(self):
        for form in self.filtered_forms(CHILDREN_FORMS):
            xpath = self.child_xpath('form/child_{num}/child{num}_child_orszntreat')
            if form.xpath(xpath) and form.xpath(xpath) == '1':
                return True
        return False

    @property
    def child_has_diarhea(self):
        for form in self.filtered_forms(CHILDREN_FORMS):
            xpath = self.child_xpath('form/child_{num}/child{num}_suffer_diarrhea')
            if form.xpath(xpath) == '1':
                return True
        return False

    @property
    def child_weighed_once(self):
        if self.child_age == 3 and self.block == 'atri':
            # This doesn't depend on a VHND - it should happen at the hospital
            def _test(form):
                return form.xpath(self.child_xpath('form/child_{num}/child{num}_child_weight')) == '1'

            return any(
                _test(form)
                for form in self.filtered_forms(CFU1_XMLNS, 3)
            )

    @property
    def child_birth_registered(self):
        if self.child_age == 6 and self.block == 'atri':
            if not self.is_vhnd_last_three_months:
                return True

            def _test(form):
                return form.xpath(self.child_xpath('form/child_{num}/child{num}_child_register')) == '1'
            return any(
                _test(form)
                for form in self.filtered_forms(CFU1_XMLNS, 3)
            )

    @property
    def child_received_measles_vaccine(self):
        if self.child_age == 12 and self.block == 'atri':
            if not self.is_service_available('stock_measlesvacc', months=3):
                return True

            def _test(form):
                return form.xpath(self.child_xpath('form/child_{num}/child{num}_child_measlesvacc')) == '1'

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
    def child_image_four(self):
        if self.block == 'atri':
            if self.child_age == 3:
                return (CHILD_WEIGHT_Y, CHILD_WEIGHT_N, "जन्म के समय वजन लिया गया",
                        "जन्म के समय वजन नहीं लिया गया")
            if self.child_age == 6:
                return (C_REGISTER_Y, C_REGISTER_N, "जन्म पंजीकृत", "जन्म पंजीकृत नहीं")
            if self.child_age == 12:
                return (MEASLEVACC_Y, MEASLEVACC_N, "खसरे का टिका लगाया", "खसरे का टिका नहीं लगाया")

    @property
    def child_breastfed(self):
        if self.child_age == 6 and self.block == 'atri':
            xpath = self.child_xpath("form/child_{num}/child{num}_child_excbreastfed")
            forms = self.filtered_forms(CHILDREN_FORMS)
            return bool(forms) and all([form.xpath(xpath) == '1' for form in forms])

    @property
    def weight_grade_normal(self):
        if self.block == "atri":
            if self.child_age in [24, 36]:
                if self.child_index == 1:
                    form_prop = 'interpret_grade'
                else:
                    form_prop = 'interpret_grade_{}'.format(self.child_index)
                forms = self.filtered_forms(CHILDREN_FORMS, 3)
                if len(forms) == 0:
                    return False
                form = sorted(forms, key=lambda form: form.received_on)[-1]
                if form.form.get(form_prop) == 'normal':
                    return self.child_age/12
                return False

    def weight_grade_status(self, status):
        if self.status == 'pregnant':
            return False
        if self.child_index == 1:
            form_prop = 'interpret_grade'
        else:
            form_prop = 'interpret_grade_{}'.format(self.child_index)

        forms = self.filtered_forms(CHILDREN_FORMS, 1)
        if len(forms) == 0:
            return False
        form = sorted(forms, key=lambda form: form.received_on)[-1]
        # callers' responsibility to pass acceptable statuses
        # status can be one of SAM, MAM, normal, overweight
        if form.form.get(form_prop) == status:
            return True
        return False

    @property
    def birth_spacing_years(self):
        """
        returns None if inapplicable, False if not met, or
        2 for 2 years, or 3 for 3 years.
        """
        if self.block == "wazirganj":
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

    @property
    @memoized
    def vhnd_available(self):
        return self.is_service_available('vhnd_available', months=1)

    @property
    def vhnd_available_display(self):
        return yesno(self.vhnd_available)

    @property
    @memoized
    def is_vhnd_last_three_months(self):
        return self.is_service_available('vhnd_available', months=3)

    @property
    @memoized
    def is_vhnd_last_six_months(self):
        return self.is_service_available('vhnd_available', months=6)

    def is_service_available(self, prop, months=1):
        return bool(self.data_provider.get_dates_in_range(
            owner_id=self.owner_id,
            startdate=self.get_months_before(months).date(),
            enddate=self.reporting_window_end,
            prop=prop,
        ))

    @property
    def num_children(self):
        if self.status == 'pregnant':
            return 0
        return self.raw_num_children

    @property
    def raw_num_children(self):
        # the raw number of children, regardless of pregnancy status
        return int(self.case_property("live_birth_amount", 0))

    def add_extra_children(self):
        if self.child_index == 1:
            # app supports up to three children only
            num_children = min(self.num_children, 3)
            if num_children > 1:
                extra_child_objects = [
                    self.__class__(self.case, self.report, child_index=num + 2, is_secondary=True)
                    for num in range(num_children - 1)
                ]
                self.report.set_extra_row_objects(extra_child_objects)

    @property
    @memoized
    def forms(self):
        return self.case.get_forms()

    @property
    def all_conditions_met(self):
        if self.status == 'mother':
            return self.child_followup
        else:
            return self.bp_conditions

    @property
    def month_amt(self):
        return MONTH_AMT if self.all_conditions_met else 0

    @property
    def year_end_bonus_cash(self):
        year_value = self.birth_spacing_years or self.weight_grade_normal
        return {
            2: TWO_YEAR_AMT,
            3: THREE_YEAR_AMT,
        }.get(year_value, 0)

    @property
    def cash_amt(self):
        return self.month_amt + self.year_end_bonus_cash

    @property
    def cash(self):
        cash_html = '<span style="color: {color};">Rs. {amt}</span>'
        return cash_html.format(
            color="red" if self.cash_amt == 0 else "green",
            amt=self.cash_amt,
        )

    @property
    def bp1(self):
        if 3 < self.preg_month < 7:
            return self.bp_conditions

    @property
    def bp2(self):
        if 6 < self.preg_month < 10:
            return self.bp_conditions

    @property
    @memoized
    def bp_conditions(self):
        if self.status == "pregnant":
            return False not in [
                self.preg_attended_vhnd,
                self.preg_weighed,
                self.preg_received_ifa,
            ]

    @property
    @memoized
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

    def bad_edd(self):
        """The expected date of delivery is beyond program range"""
        # EDD is more than nine months from the date the report is run
        if self.edd and self.edd > add_months_to_date(datetime.date.today(), 9):
            return _("Incorrect EDD")

    def bad_dod(self):
        """DOD doesn't line up with the EDD (more than a month's difference)"""
        if (self.dod and self.edd
            and abs(self.edd - self.dod) > datetime.timedelta(days=30)):
            return _("Incorrect DOD")

    def bad_lmp(self):
        """The LMP date is beyond program range"""
        if self.lmp and not (self.lmp < datetime.date.today()):
            return _("Incorrect LMP date")

    def bad_account_num(self):
        """Account number is incorrect"""
        if not (11 <= len(self.account_number) <= 16):
            return _("Account number is the wrong length")

    def bad_ifsc(self):
        """IFSC is not precisely 11 characters"""
        if len(self.ifs_code) != 11:
            return _("IFSC {} incorrect").format(self.ifs_code)

    @property
    def issues(self):
        return ", ".join(filter(None, [
            self.bad_edd(),
            self.bad_dod(),
            self.bad_lmp(),
            self.bad_account_num(),
            self.bad_ifsc(),
        ]))

    @property
    def bp1_cash(self):
        return MONTH_AMT if self.bp1 else 0

    @property
    def bp2_cash(self):
        return MONTH_AMT if self.bp2 else 0

    @property
    def child_cash(self):
        return MONTH_AMT if self.child_followup else 0

    @property
    def total_cash(self):
        """
        This exists as a function separate from cash_amt only to be certain
        that it's consistent with the values being summed
        """
        amount = min(
            MONTH_AMT,
            self.bp1_cash + self.bp2_cash + self.child_cash
        ) + self.year_end_bonus_cash
        if not self.case_is_out_of_range:
            assert amount == self.cash_amt, "The CMR and BPR disagree on payment!"
        return amount


class ConditionsMet(OPMCaseRow):
    method_map = [
        ('serial_number', ugettext_lazy("Serial number"), True, DTSortType.NUMERIC),
        ('name', ugettext_lazy("List of Beneficiaries"), True, None),
        ('awc_name', ugettext_lazy("AWC Name"), True, None),
        ('awc_code', ugettext_lazy("AWC Code"), True, DTSortType.NUMERIC),
        ('block_name', ugettext_lazy("Block Name"), True, None),
        ('husband_name', ugettext_lazy("Husband Name"), True, None),
        ('readable_status', ugettext_lazy("Current status"), True, None),
        ('preg_month_display', ugettext_lazy('Pregnancy Month'), True, DTSortType.NUMERIC),
        ('child_name', ugettext_lazy("Child Name"), True, None),
        ('child_age_display', ugettext_lazy("Child Age"), True, DTSortType.NUMERIC),
        ('window', ugettext_lazy("Window"), True, None),
        ('one', ugettext_lazy("Condition 1"), True, None),
        ('two', ugettext_lazy("Condition 2"), True, None),
        ('three', ugettext_lazy("Condition 3"), True, None),
        ('four', ugettext_lazy("Condition 4"), True, None),
        ('five', ugettext_lazy("Condition 5"), True, None),
        ('cash', ugettext_lazy("Payment amount this month (Rs.)"), True, None),
        ('payment_last_month', ugettext_lazy("Payment amount last month (Rs.)"), True, None),
        ('cash_received_last_month', ugettext_lazy("Cash received last month"), True, None),
        ('case_id', ugettext_lazy('Case ID'), True, None),
        ('closed_date', ugettext_lazy("Closed On"), True, None),
        ('issue', ugettext_lazy('Issues'), True, None)
    ]

    def __init__(self, case, report, child_index=1, awc_codes={}, **kwargs):
        super(ConditionsMet, self).__init__(case, report, child_index=child_index, **kwargs)
        self.serial_number = child_index
        self.payment_last_month = "Rs.%d" % (self.last_month_row.cash_amt if self.last_month_row else 0)
        self.cash_received_last_month = self.last_month_row.vhnd_available_display if self.last_month_row else 'no'
        self.awc_code = numeric_fn(awc_codes.get(self.awc_name, EMPTY_FIELD))
        self.issue = ''
        if self.status == 'mother':
            self.child_name = self.case_property(self.child_xpath("child{num}_name"), EMPTY_FIELD)
            self.one = self.condition_image(C_ATTENDANCE_Y, C_ATTENDANCE_N, "पोषण दिवस में उपस्थित",
                                            "पोषण दिवस में उपस्थित नही", self.child_attended_vhnd)
            self.two = self.condition_image(C_WEIGHT_Y, C_WEIGHT_N, "बच्चे का वज़न लिया गया",
                                            "बच्चे का वज़न लिया गया", self.child_growth_calculated)
            self.three = self.condition_image(ORSZNTREAT_Y, ORSZNTREAT_N, "दस्त होने पर ओ.आर.एस एवं जिंक लिया",
                                              "दस्त होने पर ओ.आर.एस एवं जिंक नहीं लिया", self.child_received_ors)
            if self.child_condition_four is not None:
                self.four = self.condition_image(self.child_image_four[0], self.child_image_four[1],
                                                 self.child_image_four[2], self.child_image_four[3],
                                                 self.child_condition_four)
            else:
                self.four = ''
            self.five = self.condition_image(EXCBREASTFED_Y, EXCBREASTFED_N, "केवल माँ का दूध खिलाया गया",
                                             "केवल माँ का दूध नहीं खिलाया गया", self.child_breastfed)
        elif self.status == 'pregnant':
            self.child_name = EMPTY_FIELD
            self.one = self.condition_image(C_ATTENDANCE_Y, C_ATTENDANCE_N, "पोषण दिवस में उपस्थित",
                                            "पोषण दिवस में उपस्थित नही", self.preg_attended_vhnd)
            self.two = self.condition_image(M_WEIGHT_Y, M_WEIGHT_N, "गर्भवती का वज़न हुआ",
                                            "गर्भवती का वज़न नही हुआा", self.preg_weighed)
            self.three = self.condition_image(IFA_Y, IFA_N, "तीस आयरन की गोलियां लेना",
                                              "तीस आयरन की गोलियां नही लिया", self.preg_received_ifa)
            self.four = ''
            self.five = ''
        if self.child_age in (24, 36):
            if self.block == 'atri':
                met, pos, neg = self.weight_grade_normal, GRADE_NORMAL_Y, GRADE_NORMAL_N
            else:
                met, pos, neg = self.birth_spacing_years, SPACING_PROMPT_Y, SPACING_PROMPT_N

            if met:
                self.five = self.img_elem % (pos, "")
            elif met is False:
                self.five = self.img_elem % (neg, "")
            else:
                self.five = ''

        if not self.vhnd_available:
            self.one = self.img_elem % (VHND_NO, "पोषण दिवस का आयोजन नहीं हुआ")


class Beneficiary(OPMCaseRow):
    """
    Constructor object for each row in the Beneficiary Payment Report
    """
    method_map = [
        # If you need to change any of these names, keep the key intact
        ('name', ugettext_lazy("List of Beneficiaries"), True, None),
        ('husband_name', ugettext_lazy("Husband Name"), True, None),
        ('awc_name', ugettext_lazy("AWC Name"), True, None),
        ('bank_name', ugettext_lazy("Bank Name"), True, None),
        ('bank_branch_name', ugettext_lazy("Bank Branch Name"), True, None),
        ('ifs_code', ugettext_lazy("IFS Code"), True, None),
        ('account_number', ugettext_lazy("Bank Account Number"), True, None),
        ('block_name', ugettext_lazy("Block Name"), True, None),
        ('village', ugettext_lazy("Village Name"), True, None),
        ('child_count', ugettext_lazy("Number of Children"), True, DTSortType.NUMERIC),
        ('bp1_cash', ugettext_lazy("Birth Preparedness Form 1"), True, None),
        ('bp2_cash', ugettext_lazy("Birth Preparedness Form 2"), True, None),
        ('child_cash', ugettext_lazy("Child Followup Form"), True, None),
        ('year_end_bonus_cash', ugettext_lazy("Bonus Payment"), True, None),
        ('total_cash', ugettext_lazy("Amount to be paid to beneficiary"), True, None),
        ('case_id', ugettext_lazy('Case ID'), True, None),
        ('owner_id', ugettext_lazy("Owner ID"), False, None),
        ('closed_date', ugettext_lazy("Closed On"), True, None),
        ('vhnd_available_display', ugettext_lazy('VHND organised this month'), True, None),
        ('payment_last_month', ugettext_lazy('Payment last month'), True, DTSortType.NUMERIC),
        ('issues', ugettext_lazy("Issues"), True, None),
    ]

    def __init__(self, case, report, child_index=1, **kwargs):
        super(Beneficiary, self).__init__(case, report, child_index=child_index, **kwargs)
        self.child_count = numeric_fn(0 if self.status == "pregnant" else 1)

        # Show only cases that require payment
        if self.total_cash == 0:
            raise InvalidRow("Case does not require payment")

        self.payment_last_month = numeric_fn(self.last_month_row.total_cash if self.last_month_row else 0)
