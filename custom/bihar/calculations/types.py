from __future__ import absolute_import
from custom.bihar.calculations.utils.filters import is_pregnant_mother, get_add
import fluff


class CaseCalculator(fluff.Calculator):
    include_closed = False

    @fluff.filter_by
    def case_open(self, case):
        return self.include_closed or not case.closed


class DoneDueCalculator(CaseCalculator):
    primary = 'total'


class TotalCalculator(CaseCalculator):
    primary = 'total'


# the following are commonly shared across all indicators


class AddCalculator(CaseCalculator):

    @fluff.filter_by
    def has_add(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)
