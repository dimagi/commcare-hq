import datetime
import logging
from custom.bihar.calculations.types import DoneDueCalculator, TotalCalculator
from custom.bihar.calculations.utils.calculations import get_forms
from custom.bihar.calculations.utils.filters import is_pregnant_mother,\
    get_add, get_edd, A_MONTH
from custom.bihar.calculations.utils.home_visit import GRACE_PERIOD
from custom.bihar.calculations.utils.visits import visit_is, has_visit
import fluff


class BPCalculator(DoneDueCalculator):

    def __init__(self, days, n_visits, window=A_MONTH):
        self.days = days
        self.n_visits = n_visits
        super(BPCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_edd(case)

    @fluff.date_emitter
    def numerator(self, case):
        yield case.edd - datetime.timedelta(days=self.days) + GRACE_PERIOD

    @fluff.null_emitter
    def total(self, case):
        n_visits = len(filter(lambda a: visit_is(a, 'bp'), case.actions))
        if n_visits >= self.n_visits:
            yield None


class VisitCalculator(DoneDueCalculator):

    def __init__(self, schedule, visit_type, window=A_MONTH):
        self.schedule = schedule
        self.visit_type = visit_type
        super(VisitCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.date_emitter
    def numerator(self, case):
        n_qualifying_visits = len(
            filter(lambda a: visit_is(a, self.visit_type), case.actions)
        )
        # What's below is true to the original, but I think it should be
        # self.schedule[:n_qualifying_visits]
        # to be revisited
        if n_qualifying_visits != 0:
            for days in self.schedule[:n_qualifying_visits - 1]:
                yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD

    @fluff.date_emitter
    def total(self, case):
        for days in self.schedule:
            yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD


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
        # if not has_visit(case, 'reg'):
        #     logging.error('Case has no reg action: %s' % case.get_id)
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
