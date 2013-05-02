import datetime
from couchdbkit.ext.django.schema import Document
from bihar.reports.indicators.filters import is_pregnant_mother, get_add, get_edd, A_MONTH, delivered
from bihar.reports.indicators.home_visit import GRACE_PERIOD
from bihar.reports.indicators.visits import visit_is
from casexml.apps.case.models import CommCareCase
import fluff


class _(Document):
    pass


class CaseCalculator(fluff.Calculator):

    class __metaclass__(type(fluff.Calculator)):
        def __new__(mcs, name, bases, attrs):
            if name != 'CaseCalculator' and 'filter' in attrs:
                raise SyntaxError("Overriding 'filter' is not allowed. "
                                  "Just a precaution so you don't do it "
                                  "by mistake and silently get closed cases. "
                                  "Use case_filter instead.")
            return type(fluff.Calculator).__new__(mcs, name, bases, attrs)

    def filter(self, case):
        return not case.closed and self.case_filter(case)

    def case_filter(self, case):
        return True


class BPCalculator(CaseCalculator):

    def __init__(self, days, n_visits, window=A_MONTH):
        self.days = days
        self.n_visits = n_visits
        super(BPCalculator, self).__init__(window)

    def case_filter(self, case):
        return is_pregnant_mother(case) and get_edd(case)

    @fluff.date_emitter
    def numerator(self, case):
        yield case.edd - datetime.timedelta(days=self.days) + GRACE_PERIOD

    @fluff.null_emitter
    def denominator(self, case):
        if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= self.n_visits:
            yield None


class VisitCalculator(CaseCalculator):

    def __init__(self, schedule, visit_type, window=A_MONTH):
        self.schedule = schedule
        self.visit_type = visit_type
        super(VisitCalculator, self).__init__(window)

    def case_filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.date_emitter
    def numerator(self, case):
        n_qualifying_visits = len(filter(lambda a: visit_is(a, self.visit_type), case.actions))
        # I think originally this was
        # self.schedule[:n_qualifying_visits - 1]
        # but that seems wrong
        if n_qualifying_visits != 0:
            for days in self.schedule[:n_qualifying_visits - 1]:
                yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD

    @fluff.date_emitter
    def denominator(self, case):
        for days in self.schedule:
            yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD


class UpcomingDeliveryList(CaseCalculator):

    def case_filter(self, case):
        still_pregnant = is_pregnant_mother(case) and not delivered(case)
        return still_pregnant and get_edd(case)

    @fluff.date_emitter
    def total(self, case):
        edd = get_edd(case)
        yield edd - self.window/2


class CareBiharFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ('care-bihar',)
    group_by = ('domain', 'owner_id')

    bp2 = BPCalculator(days=75, n_visits=2)
    bp3 = BPCalculator(days=45, n_visits=3)

    pnc = VisitCalculator(schedule=(1, 3, 6), visit_type='pnc')
    ebf = VisitCalculator(schedule=(14, 28, 60, 90, 120, 150), visit_type='eb')
    cf = VisitCalculator(schedule=[m * 30 for m in (6, 7, 8, 9, 12, 15, 18)],
                         visit_type='cf')

    upcoming_deliveries = UpcomingDeliveryList(window=2 * A_MONTH)

    class Meta:
        app_label = 'bihar'

CareBiharFluffPillow = CareBiharFluff.pillow()