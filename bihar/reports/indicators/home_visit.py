from bihar.reports.indicators.calculations import DoneDueMixIn,\
    IndicatorCalculator, MemoizingCalculatorMixIn, MotherPreDeliverySummaryMixIn,\
    MotherPostDeliveryMixIn, MotherPreDeliveryMixIn, MemoizingFilterCalculator,\
    MotherPostDeliverySummaryMixIn, get_forms
from bihar.reports.indicators.visits import visit_is, has_visit
import datetime as dt
from bihar.reports.indicators.filters import get_edd, is_pregnant_mother,\
    get_add, A_MONTH, due_next_month, delivered_last_month,\
    pregnancy_registered_last_month

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

class BP2Calculator(MotherPreDeliverySummaryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):
    def _numerator(self, case):
        return 1 if _mother_due_in_window(case, 75) else 0

    def _denominator(self, case):
        return 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 2 else 0

class BP3Calculator(MotherPreDeliverySummaryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):
    def _numerator(self, case):
        return 1 if _mother_due_in_window(case, 45) else 0

    def _denominator(self, case):
        return 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 3 else 0

class VisitCalculator(MotherPostDeliverySummaryMixIn, MemoizingCalculatorMixIn,
                      DoneDueMixIn, IndicatorCalculator):
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

# client list filters

class UpcomingDeliveryList(MotherPreDeliveryMixIn, MemoizingFilterCalculator,
                           IndicatorCalculator):
    def _filter(self, case):
        return due_next_month(case)

class RecentDeliveryList(MotherPostDeliveryMixIn, MemoizingFilterCalculator,
                         IndicatorCalculator):
    def _filter(self, case):
        return delivered_last_month(case)

class RecentRegistrationList(MotherPreDeliveryMixIn, MemoizingFilterCalculator,
                             IndicatorCalculator):
    def _filter(self, case):
        return pregnancy_registered_last_month(case)
    
class NoBPList(MotherPreDeliveryMixIn, MemoizingFilterCalculator,
                             IndicatorCalculator):
    def _filter(self, case):
        return pregnancy_registered_last_month(case) and not has_visit(case, 'bp')

class NoIFAList(MotherPreDeliveryMixIn, MemoizingFilterCalculator,
                             IndicatorCalculator):
    def _filter(self, case):
        def _ifa_tabs(case):
            ifa = getattr(case, "ifa_tablets", None)
            return int(ifa) if ifa else 0
        return pregnancy_registered_last_month(case) and _ifa_tabs(case) > 0

class NoEmergencyPrep(MotherPostDeliveryMixIn, MemoizingFilterCalculator,
                      IndicatorCalculator):
    def _filter(self, case):
        # filter by BP forms for cases with
        # /data/bp2/maternal_danger_signs = 'no' and
        # /data/bp2/danger_institution = 'no'
        def _no_prep(case):
            for form in get_forms(case, action_filter=lambda a: visit_is(a, 'bp')):
                if form.xpath('form/bp2/maternal_danger_signs') == 'no' and \
                        form.xpath('form/bp2/danger_institution') == 'no':
                    return True
            return False
        return due_next_month(case) and _no_prep(case)

class NoNewbornPrep(MotherPostDeliveryMixIn, MemoizingFilterCalculator,
                      IndicatorCalculator):
    def _filter(self, case):
        # filter by BP forms for cases with
        # /data/bp2/wrapping = 'no' and
        # /data/bp2/skin_to_skin = 'no' and
        # /data/bp2/immediate_breastfeeding = 'no' and
        # /data/bp2/cord_care = 'no'
        def _no_prep(case):
            for form in get_forms(case, action_filter=lambda a: visit_is(a, 'bp')):
                if form.xpath('form/bp2/wrapping') == 'no' and \
                        form.xpath('form/bp2/skin_To_skin') == 'no' and \
                        form.xpath('form/bp2/immediate_breastfeeding') == 'no' and \
                        form.xpath('form/bp2/cord_care') == 'no':
                    return True
            return False
        return due_next_month(case) and _no_prep(case)

class NoPostpartumCounseling(MotherPostDeliveryMixIn, MemoizingFilterCalculator,
                      IndicatorCalculator):
    def _filter(self, case):
        # filter by BP forms for cases with
        # /data/family_planning_group/counsel_accessible = 'no'
        def _no_counseling(case):
            for form in get_forms(case, action_filter=lambda a: visit_is(a, 'bp')):
                print "form"
                if form.xpath('form/bp2/counsel_accessible') == 'no':
                    return True
            return False
        return due_next_month(case) and _no_counseling(case)

class NoFamilyPlanning(MotherPostDeliveryMixIn, MemoizingFilterCalculator,
                       IndicatorCalculator):
    def _filter(self, case):
        return due_next_month(case) and getattr(case, 'couple_interested') == 'no'

