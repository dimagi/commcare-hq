import logging
from custom.bihar import getters
from custom.bihar.calculations.types import DoneDueCalculator, TotalCalculator
from custom.bihar.calculations.utils.calculations import get_forms
from custom.bihar.calculations.utils.filters import is_pregnant_mother,\
    get_add, get_edd, A_MONTH
from custom.bihar.calculations.utils.visits import visit_is, has_visit
import fluff


class BPCalculator(DoneDueCalculator):

    def __init__(self, days, window=A_MONTH):
        self.days = days
        super(BPCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_edd(case)

    def _form_filter(self, case, form):
        lower, upper = self.days
        date_modified = getters.date_modified(form)
        return lower <= (case.edd - date_modified).days < upper

    @fluff.date_emitter
    def numerator(self, case):
        for form in get_forms(case, action_filter=lambda a: visit_is(a, 'bp')):
            date = getters.date_next_bp(form)
            days_overdue = getters.days_visit_overdue(form)
            if date and days_overdue == 0 and self._form_filter(case, form):
                yield date

    @fluff.date_emitter
    def total(self, case):
        for form in get_forms(case, action_filter=lambda a: visit_is(a, 'bp') or visit_is(a, 'reg')):
            date = getters.date_next_bp(form)
            if date and self._form_filter(case, form):
                yield date


class VisitCalculator(DoneDueCalculator):

    def __init__(self, form_types, visit_type, get_date_next, window=A_MONTH):
        self.form_types = form_types
        self.visit_type = visit_type
        self.get_date_next = get_date_next
        super(VisitCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    def _numerator_action_filter(self, a):
        return visit_is(a, self.visit_type)

    def _total_action_filter(self, a):
        return any(visit_is(a, visit_type)
                   for visit_type in self.form_types)

    @fluff.date_emitter
    def numerator(self, case):
        for form in get_forms(case, action_filter=self._numerator_action_filter):
            date = self.get_date_next(form)
            days_overdue = getters.days_visit_overdue(form)
            if date and days_overdue in (-1, 0, 1):
                yield date

    @fluff.date_emitter
    def total(self, case):
        for form in get_forms(case, action_filter=self._total_action_filter):
            date = self.get_date_next(form)
            if date:
                yield date


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
                form.xpath(xpath) != 'yes'
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
