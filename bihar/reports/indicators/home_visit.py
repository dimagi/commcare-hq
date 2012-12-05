from bihar.reports.indicators.calculations import DoneDueMixIn,\
    IndicatorCalculator, MemoizingCalculatorMixIn, MotherPreDeliveryMixIn,\
    MotherPostDeliveryMixIn
from bihar.reports.indicators.visits import visit_is
import datetime as dt
from bihar.reports.indicators.filters import get_edd, is_pregnant_mother,\
    get_add, A_MONTH

GRACE_PERIOD = dt.timedelta(days=7)

def _mother_due_in_window(case, days):
    get_visitduedate = lambda case: case.edd - dt.timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_edd(case) and _in_last_month(get_visitduedate(case))

def _mother_delivered_in_window(case, days):
    get_visitduedate = lambda case: case.add + dt.timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_add(case) and _in_last_month(get_visitduedate(case))

def _in_last_month(date):
    today = dt.datetime.today().date()
    return today - A_MONTH < date < today

def _visits_due(case, schedule):
    return [i + 1 for i, days in enumerate(schedule) \
            if _mother_delivered_in_window(case, days)]

def _visits_done(case, schedule, type):
    due = _visits_due(case, schedule)
    count = len(filter(lambda a: visit_is(a, type), case.actions))
    return len([v for v in due if count > v])

class BP2Calculator(MotherPreDeliveryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):
    def _numerator(self, case):
        return 1 if _mother_due_in_window(case, 75) else 0

    def _denominator(self, case):
        return 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 2 else 0

class BP3Calculator(MotherPreDeliveryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):
    def _numerator(self, case):
        return 1 if _mother_due_in_window(case, 45) else 0

    def _denominator(self, case):
        return 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 3 else 0

class VisitCalculator(MotherPostDeliveryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):
    schedule = ()      # override
    visit_type = None  # override
    def _numerator(self, case):
        return _visits_done(case, self.schedule, self.visit_type)

    def _denominator(self, case):
        return len(_visits_due(case, self.schedule))

class PNCCalculator(VisitCalculator):
    schedule = (1, 3, 6)
    visit_type = "pnc"

class EBCalculator(VisitCalculator):
    schedule = (14, 28, 60, 90, 120, 150)
    visit_type = "eb"

class CFCalculator(VisitCalculator):    
    schedule_in_months = (6, 7, 8, 9, 12, 15, 18)
    schedule = (m * 30 for m in schedule_in_months)
    visit_type = "cf"