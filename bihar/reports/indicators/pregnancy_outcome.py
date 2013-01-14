from bihar.reports.indicators.calculations import MemoizingCalculatorMixIn,\
    MotherPostDeliverySummaryMixIn, IndicatorCalculator,\
    delivered_in_timeframe_with_status


class LiveBirthCalculator(MotherPostDeliverySummaryMixIn, MemoizingCalculatorMixIn,
                          IndicatorCalculator):

    def _denominator(self, case):
        return 1 if delivered_in_timeframe_with_status(case, 30, 'live_birth') else 0

class BornAtHomeCalculator(LiveBirthCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_place', None) == 'home'

class BornAtPublicHospital(LiveBirthCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_place', None) == 'public'

class BornInTransit(LiveBirthCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_place', None) == 'transit'

class BornInPrivateHospital(LiveBirthCalculator):
    def _numerator(self, case):
        return getattr(case, 'birth_place', None) == 'private'
