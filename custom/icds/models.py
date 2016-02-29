
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.expressions.getters import transform_date
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from dimagi.utils.decorators.memoized import memoized

from . import constants


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

    # needs caching across UCR build cycle
    @property
    @memoized
    def forms(self):
        if self.forms_provider:
            return self.forms_provider
        forms = []
        for form_id in self.case.xform_ids:
            forms.append(FormAccessors(self.case.domain).get_form(form_id))

    def case_property(self, case, property, default=None):
        prop = case.dynamic_case_properties().get(property, default)
        if isinstance(prop, basestring) and prop.strip() == "":
            return default
        return prop

    def filtered_forms(self, xmlns):
        for form in self.forms:
            if form.xmlns == xmlns and are_in_same_month(form.received_on, self.snapshot_start_date):
                yield form

    @property
    @memoized
    def is_open(self):
        return are_in_same_month(self.case.opened_on, self.snapshot_start_date)

    @property
    @memoized
    def nutrition_status(self):
        statuses = [
            form.get_data("form/z_score_wfa_ql/nutrition_status")
            for form in self.filtered_forms(constants.GMP_XMLNS)
            if form.get_data("form/z_score_wfa_ql/nutrition_status")
        ]
        return statuses[0] if any(statuses) else 'unweighed'

    @property
    @memoized
    def dob(self):
        return transform_date(self.case_property(self.mother_case, "dob"))

    @property
    @memoized
    def age_in_days(self):
        return (self.dob - self.snapshot_end_date).days

    @property
    @memoized
    def age_in_months(self):
        return self.age_in_days / 30.4

    @property
    @memoized
    def age_in_years(self):
        return self.age_in_days / 365.25

    @property
    @memoized
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
    @memoized
    def mother_case(self):
        return self.case.parent

    @property
    @memoized
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

    def thr_eligible(self):
        return one_or_zero(6 <= self.age_in_months <= 36)

    def pse_eligible(self):
        return one_or_zero(self.age_in_months > 36)

    def pse_attended_16_days(self):
        return one_or_zero(self.pse_days_attended == 16)

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


def one_or_zero(bool_val):
    return 1 if bool_val else 0


def are_in_same_month(date1, date2):
    date1 = transform_date(date1)
    date2 = transform_date(date2)
    return date1.year == date2.year and date1.month and date2.month
