from datetime import timedelta
import logging
from custom.bihar import getters
from custom.bihar.calculations.types import DoneDueCalculator, TotalCalculator
from custom.bihar.calculations.utils.calculations import get_forms
from custom.bihar.calculations.utils.filters import is_pregnant_mother,\
    get_add, get_edd, A_MONTH
from custom.bihar.calculations.utils.visits import visit_is, has_visit
import fluff


def date_in_range(date_to_check, reference, lower_window=10, upper_window=10):
    if not date_to_check:
        return False
    ret = reference - timedelta(days=lower_window) <= date_to_check <= reference + timedelta(days=upper_window)
    return ret


def no_filter(*args, **kwargs): return True

class DateRangeFilter(object):

    def __init__(self, days):
        self.days = days

    def __call__(self, case, date):
        lower, upper = self.days
        return getattr(case, 'edd', None) and lower <= (case.edd - date).days < upper


class VisitCalculator(DoneDueCalculator):

    def __init__(self, form_types, visit_type, get_date_next, case_filter,
                 additional_filter=no_filter, window=A_MONTH):
        self.form_types = form_types
        self.visit_type = visit_type
        self.get_date_next = get_date_next
        self.case_filter = case_filter
        self.additional_filter = additional_filter
        super(VisitCalculator, self).__init__(window)

    def filter(self, case):
        return self.case_filter(case)


    def _get_numerator_action_filter(self, form, date):
        """
        The filter used to determine relevant actions from the numerator.
        The form is the form contributing to the denominator and the date is
        the due date for the visit.
        """
        def _filter(a):
            return (visit_is(a, self.visit_type)  # right type
                    and date_in_range(a.date.date(), date)  # within window
                    and a.date > getters.date_modified(form, force_to_date=False, force_to_datetime=True)  # came after "due" visit
                    and a.xform_id not in self._visits_used)  # not already counted
        return _filter

    def _total_action_filter(self, a):
        return any(visit_is(a, visit_type)
                   for visit_type in self.form_types)

    @fluff.date_emitter
    def total(self, case):
        return (date for date, form in self._total(case))

    def _total(self, case):
        """
        Private method for calculating the "total" for the denominator. In addition to emitting
        the appropriate date it also emits the form that generated it, so that it can be referenced
        by the numerator.
        """
        for form in get_forms(case, action_filter=self._total_action_filter):
            date = self.get_date_next(form)
            if date and self.additional_filter(case, date):
                yield (date, form)

    @fluff.date_emitter
    def numerator(self, case):
        self._visits_used = set()
        for date, form in self._total(case):
            for form in get_forms(case,
                                  action_filter=self._get_numerator_action_filter(form, date)):
                self._visits_used.add(form._id)
                yield date
                break  # only allow one numerator per denominator


class DueNextMonth(TotalCalculator):

    window = 2 * A_MONTH

    @fluff.filter_by
    def has_edd(self, case):
        return is_pregnant_mother(case) and get_edd(case) and not get_add(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_edd(case) - self.window / 2


class RecentDeliveryList(TotalCalculator):
    window = A_MONTH
    include_closed = True

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class RecentlyOpened(TotalCalculator):
    """Abstract"""

    window = A_MONTH

    @fluff.filter_by
    def case_type(self, case):
        return is_pregnant_mother(case)

    @fluff.date_emitter
    def total(self, case):
        for action in case.actions:
            if visit_is(action, 'reg'):
                if not action.date:
                    logging.error('Reg action has no date! Case %s' % case.get_id)
                else:
                    yield action.date


class NoBPList(RecentlyOpened):

    def filter(self, case):
        return not has_visit(case, 'bp')

    @fluff.filter_by
    def no_bp_date(self, case):
        return all(getattr(case, p, '') == '' for p in (
            'date_bp_1',
            'date_bp_2',
            'date_bp_3',
        ))


class NoIFAList(RecentlyOpened):

    def filter(self, case):
        ifa = int(getattr(case, "ifa_tablets", None) or 0)
        return ifa == 0


class NoBPPrep(TotalCalculator):
    """Abstract"""
    no_prep_paths = ()

    def action_filter(self, action):
        return visit_is(action, 'bp')

    @fluff.filter_by
    def no_prep(self, case):
        forms = list(get_forms(case, action_filter=self.action_filter))
        return any(
            all(
                form.get_data(xpath) != 'yes'
                for form in forms
            )
            for xpath in self.no_prep_paths
        )


class NoEmergencyPrep(NoBPPrep, DueNextMonth):

    no_prep_paths = (
        'form/bp2/maternal_danger_signs',
        'form/bp2/danger_institution',
    )


class NoNewbornPrep(NoBPPrep, DueNextMonth):

    no_prep_paths = (
        'form/bp2/wrapping',
        'form/bp2/skin_to_skin',
        'form/bp2/immediate_breastfeeding',
        'form/bp2/cord_care',
    )


class NoPostpartumCounseling(NoBPPrep, DueNextMonth):

    no_prep_paths = (
        'form/family_planning_group/counsel_accessible',
    )


class NoFamilyPlanning(DueNextMonth):
    def filter(self, case):
        return getattr(case, 'couple_interested', None) == 'no'
