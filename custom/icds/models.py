
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.expressions.getters import transform_date


from .constants import *


class ChildHealthCaseRow(object):
    def __init__(self, case, snapshot_start_date, snapshot_end_date, forms_provider=[]):
        """
        Snapshot of the case in the duration specified by snapshot_start_date and snapshot_end_date

        args:
            case: case of type 'child_health'
            snapshot_start_date: Start date of duration to snapshot the case on
            snapshot_end_date: End date of duration to snapshot the case on.

        dates can be date/datetime objects or a valid strings
        """
        if not isinstance(case, CommCareCase):
            case = CommCareCase.wrap(case)
        self.case = case
        self.snapshot_start_date = transform_date(snapshot_start_date)
        self.snapshot_end_date = transform_date(snapshot_end_date)
        self.forms_provider = forms_provider

    # needs caching
    def forms(self):
        for action in self.case.actions:
            yield XFormInstance.get(action.xform_id)

    def case_property(self, case, property, default=None):
        prop = getattr(case, property, default)
        if isinstance(prop, basestring) and prop.strip() == "":
            return default
        return prop

    def filtered_forms(self, xmlns):
        for form in self.forms:
            if form.xmlns == xmlns and are_in_same_month(form.received_on, self.snapshot_start_date):
                yield form

    def is_open(self):
        return are_in_same_month(self.case.opened_on, self.snapshot_start_date)

    def nutrition_status(self):
        statuses = [
            form.get_data("form/z_score_wfa_ql/nutrition_status")
            for form in self.filtered_forms(GMP_XMLNS)
            if form.get_data("form/z_score_wfa_ql/nutrition_status")
        ]
        return statuses[0] if any(statuses) else 'unweighed'

    @property
    def dob(self):
        return transform_date(self.case_property(self.mother_case, "dob"))

    @property
    def age_in_days(self):
        return (self.dob - self.snapshot_end_date).days

    @property
    def age_in_months(self):
        return self.age_in_days / 30.4

    @property
    def age_in_years(self):
        return self.age_in_days / 365.25

    @property
    def age_group(self):
        if self.age_in_days <= 28:
            return '0-28days'
        elif self.age_in_days > 28 and self.age_in_months <= 6:
            return '28-6mo'
        elif 6 < self.age_in_months <= 12:
            '6-12mo'
        elif 12 < self.age_in_months <= 24:
            '1-2yr'
        elif 24 < self.age_in_months <= 36:
            '2-3yr'
        elif 36 < self.age_in_months <= 48:
            '3-4yr'
        elif 48 < self.age_in_months <= 60:
            '4-5yr'
        elif 60 < self.age_in_months <= 72:
            '5-6yr'

    @property
    def mother_case(self):
        return self.case.parent

    def household_case(self):
            return self.mother_case.parent if self.mother_case else None

    def nutrition_status_severely_underweight(self):
        return one_or_zero(self.nutrition_status == 'severely underweight')

    def nutrition_status_moderately_underweight(self):
        return one_or_zero(self.nutrition_status == 'moderately underweight')

    def nutrition_status_normal(self):
        return one_or_zero(self.nutrition_status == 'normal')

    def nutrition_status_unweighed(self):
        return one_or_zero(self.nutrition_status == 'unweighed')

    def nutrition_status_weighed(self):
        return one_or_zero(self.nutrition_status != 'unweighed')

    def num_rations(self):
        gmp_forms = self.filtered_forms(GMP_XMLNS)

    def thr_eligible(self):
        return one_or_zero(6 <= self.age_in_months <= 36)

    def pse_eligible(self):
        return one_or_zero(self.age_in_months > 36)

    def pse_days_attended(self):
        pse_forms = self.filtered_forms(PSE_XMLNS)
        pse_updates = self.case.actions
        for update in pse_updates:
            if are_in_same_month(update.server_date, self.snapshot_start_date):
                # todo
                return True

    def pse_attended_16_days(self):
        return one_or_zero(pse_days_attended == 16)

    @property
    def low_birth_weight(self):
        return self.case_property(self.case, "low_birth_weight")

    @property
    def low_birth_weight_in_current_month(self):
        return one_or_zero(self.low_birth_weight == "yes" and self.born_in_month)

    @property
    def born_in_month(self):
        return one_or_zero(0 < self.age_in_days <= 31)

    @property
    def ebf_eligible(self):
        return one_or_zero(self.age_in_months <= 6)

    def _latest_ebf_property(self, property):
        if self.ebf_eligible:
            return [
                form.get_data(property)
                for form in self.filtered_forms(EBF_XMLNS)
            ][-1]
        else:
            return None

    @property
    def ebf_in_month(self):
        is_ebf = self._latest_ebf_property("child/is_ebf")
        return one_or_zero(is_ebf == 'yes')

    @property
    def no_ebf_in_month(self):
        is_ebf = self._latest_ebf_property("child/is_ebf")
        return one_or_zero(is_ebf == 'no')

    @property
    def ebf_unknown(self):
        return one_or_zero(self._latest_ebf_property is None)

    @property
    def _no_ebf_reason(self):
        return self._latest_ebf_property("child/not_breastfeading")

    @property
    def no_ebf_reason_no_milk(self):
        return one_or_zero(self._no_ebf_reason == "not_enough_milk")

    @property
    def no_ebf_reason_pregnant_again(self):
        return one_or_zero(self._no_ebf_reason == "pregnant_again")

    @property
    def no_ebf_reason_child_too_old(self):
        return one_or_zero(self._no_ebf_reason == "child_too_old")

    @property
    def no_ebf_reason_child_mother_sick(self):
        return one_or_zero(self._no_ebf_reason == "child_mother_sick")

    @property
    def no_ebf_reason_water_or_animal_milk(self):
        return one_or_zero(self.latest_ebf_property('child/water_or_milk') == 'yes')

    @property
    def no_ebf_reason_tea(self):
        return one_or_zero(self.latest_ebf_property('child/tea_other') == 'yes')

    @property
    def no_ebf_reason_eating_food(self):
        return one_or_zero(self.latest_ebf_property('child/eating') == 'yes')

    @property
    def cf_eligible(self):
        return one_or_zero(6 <= self.age_in_months <= 24)

    @property
    def _comp_feeding_property(self):
        if self.ebf_eligible:
            return [
                form.get_data('child/comp_feeding')
                for form in self.filtered_forms(CF_XMLNS)
            ][-1]
        else:
            return None

    @property
    def cf_in_month(self):
        return one_or_zero(self._comp_feeding_property() == 'yes')

    @property
    def no_cf_in_month(self):
        return one_or_zero(self._comp_feeding_property() == 'no')

    @property
    def cf_unknown(self):
        return one_or_zero(self._comp_feeding_property() is None)

    @property
    def fully_immunized_eligible(self):
        return one_or_zero(self.age_in_months >= 12)


def one_or_zero(bool_val):
    return 1 if bool_val else 0


def are_in_same_month(date1, date2):
    date1 = transform_date(date1)
    date2 = transform_date(date2)
    return date1.year == date2.year and date1.month and date2.month
