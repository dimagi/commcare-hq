import datetime
from bihar.calculations.types import DoneDueCalculator
from bihar.calculations.utils.filters import get_add, is_pregnant_mother, A_MONTH
from bihar.reports.indicators.calculations import _get_time_of_visit_after_birth, _get_tob
import fluff


class HDDayCalculator(DoneDueCalculator):
    offsets = {
        '_numerator': (datetime.timedelta(days=0), datetime.timedelta(days=1)),
        'denominator': (-A_MONTH, datetime.timedelta(days=0)),
    }
    window = A_MONTH
    at = ['home']

    def __init__(self, at, window=None):
        super(HDDayCalculator, self).__init__(window=window)
        self.at = at

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.filter_by
    def correct_birthplace(self, case):
        return getattr(case, 'birth_place', None) in self.at

    @fluff.date_emitter
    def _numerator(self, case):
        visit_time = _get_time_of_visit_after_birth(case)
        time_birth = _get_tob(case)
        if visit_time and time_birth:
            yield visit_time

    @fluff.post_process
    def numerator(self, result):
        if result.get('_numerator') and result.get('denominator'):
            return result.get_ids('_numerator') & result.get_ids('denominator')
        else:
            return set()

    @fluff.date_emitter
    def denominator(self, case):
        yield case.add


# class IDDayCalculator(HDDayCalculator):
#
#     def _denominator(self, case):
#         return 1 if delivered_at_in_timeframe(case, ['private', 'public'], 30) else 0
