import datetime
from bihar.calculations.types import DoneDueCalculator, CaseCalculator
from bihar.calculations.utils.filters import get_add, is_pregnant_mother, A_MONTH, A_DAY
from bihar.reports.indicators.calculations import _get_time_of_visit_after_birth, _get_tob, _get_prop_from_forms
from bihar.reports.indicators.visits import get_related_prop
import fluff


class BirthPlace(DoneDueCalculator):
    """Abstract"""

    window = A_MONTH

    def __init__(self, at, window=None):
        super(BirthPlace, self).__init__(window=window)
        self.at = at if not isinstance(at, basestring) else (at,)

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.filter_by
    def correct_birthplace(self, case):
        return getattr(case, 'birth_place', None) in self.at


class VisitedQuicklyBirthPlace(BirthPlace):
    visited_window = A_DAY

    @fluff.date_emitter
    def numerator(self, case):
        visit_time = _get_time_of_visit_after_birth(case)
        time_birth = _get_tob(case)
        if visit_time and time_birth:
            if time_birth < visit_time < time_birth + self.visited_window:
                # matches denominator, so you know this will be a subset of those
                yield case.add

    @fluff.date_emitter
    def denominator(self, case):
        yield case.add


class LiveBirthCalculator(CaseCalculator):
    """Abstract"""

    @fluff.filter_by
    def live_birth(self, case):
        return get_related_prop(case, 'birth_status') == "live_birth"


class BreastFedBirthPlace(BirthPlace, LiveBirthCalculator):

    @fluff.date_emitter
    def numerator(self, case):
        dtf = _get_prop_from_forms(case, 'date_time_feed')
        tob = get_related_prop(case, 'time_of_birth')
        if dtf and tob:
            if dtf - tob <= datetime.timedelta(hours=1):
                yield case.add

    @fluff.date_emitter
    def denominator(self, case):
        yield case.add


class LiveBirthPlace(BirthPlace, LiveBirthCalculator):

    def correct_birthplace(self, case):
        """
        don't filter by this because denominator is ALL live births

        this is relying on an implementation detail of fluff:
        only the name 'correct_birthplace' is stored in the list of filters
        so this function, and not the original decorated function, is called

        """
        return True

    @fluff.date_emitter
    def denominator(self, case):
        yield case.add

    @fluff.date_emitter
    def numerator(self, case):
        if super(LiveBirthPlace, self).correct_birthplace(case):
            yield case.add
