import fluff


class CaseCalculator(fluff.Calculator):

    @fluff.filter_by
    def case_open(self, case):
        return not case.closed


class DoneDueCalculator(CaseCalculator):
    primary = 'denominator'


class TotalCalculator(CaseCalculator):
    primary = 'total'
