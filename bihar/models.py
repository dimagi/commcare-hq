import datetime
from bihar.reports.indicators.filters import is_pregnant_mother, get_add, get_edd, A_MONTH
from bihar.reports.indicators.home_visit import GRACE_PERIOD
from bihar.reports.indicators.visits import visit_is
from casexml.apps.case.models import CommCareCase
import fluff


class BPCalculator(fluff.Calculator):

    def __init__(self, days, n_visits, window=A_MONTH):
        self.days = days
        self.n_visits = n_visits
        super(BPCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_edd(case)

    @fluff.emitter
    def numerator(self, case):
        yield case.edd - datetime.timedelta(days=self.days) + GRACE_PERIOD

    @fluff.emitter
    def denominator(self, case):
        if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= self.n_visits:
            yield None


class VisitCalculator(fluff.Calculator):

    def __init__(self, schedule, visit_type, window=A_MONTH):
        self.schedule = schedule
        self.visit_type = visit_type
        super(VisitCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.emitter
    def numerator(self, case):
        n_qualifying_visits = len(filter(lambda a: visit_is(a, self.visit_type), case.actions))
        # I think originally this was
        # self.schedule[:n_qualifying_visits - 1]
        # but that seems wrong
        for days in self.schedule[:n_qualifying_visits]:
            yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD

    @fluff.emitter
    def denominator(self, case):
        for days in self.schedule:
            yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD


class CareBiharIndicators(fluff.IndicatorDocument):
    document_class = CommCareCase

    bp2 = BPCalculator(days=75, n_visits=2)
    bp3 = BPCalculator(days=45, n_visits=3)

    pnc = VisitCalculator(schedule=(1, 3, 6), visit_type='pnc')
    ebf = VisitCalculator(schedule=(14, 28, 60, 90, 120, 150), visit_type='eb')
    cf = VisitCalculator(schedule=(m * 30 for m in (6, 7, 8, 9, 12, 15, 18)),
                         visit_type='cf')

CareBiharIndicatorsPillow = CareBiharIndicators.pillow()