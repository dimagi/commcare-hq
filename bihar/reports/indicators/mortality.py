from bihar.reports.indicators.calculations import MemoizingCalculatorMixIn,\
    MotherPostDeliverySummaryMixIn, IndicatorCalculator,\
    delivered_in_timeframe_with_status, delivered_in_timeframe, get_forms,\
    SummaryValueMixIn
from datetime import datetime, timedelta
from bihar.reports.indicators.visits import visit_is


def _still_birth(case):
    # birth_status = 'still_birth' on case
    # OR:
    # /data/child_info/child_cried='no' and
    # /data/child_info/child_breathing='no' and
    # /data/child_info/child_movement='no' and
    # /data/child_info/child_heartbeats='no' from delivery form
    status = getattr(case, 'birth_status', None)
    if status is not None:
        return status == 'still_birth'
    else:
        def filter_action(action):
            if visit_is(action, 'del'):
                now = datetime.now()
                return now - timedelta(days=30) <= action.date
            return False
        for f in get_forms(case, action_filter=filter_action):
            if f.xpath(' form/child_info/child_cried') == 'no' and \
                    f.xpath(' form/child_info/child_breathing') == 'no' and \
                    f.xpath(' form/child_info/child_movement') == 'no' and \
                    f.xpath(' form/child_info/child_heartbeats') == 'no':
                return True
            return False

class DeliveryCalculator(MotherPostDeliverySummaryMixIn, MemoizingCalculatorMixIn,
                         SummaryValueMixIn, IndicatorCalculator):

    def _denominator(self, case):
        return 1 if delivered_in_timeframe(case, 30) else 0

class StillAtPublicHospital(DeliveryCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_place', None) == 'public' and _still_birth(case)

class StillAtHome(DeliveryCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_place', None) == 'home' and _still_birth(case)

class LiveBirth(DeliveryCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_status', None) == 'live_birth'
