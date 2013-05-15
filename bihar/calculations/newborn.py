from bihar.calculations.types import DoneDueCalculator
from bihar.calculations.utils.filters import is_pregnant_mother, get_add
from bihar.reports.indicators.calculations import _newborn, _get_form
from bihar.reports.indicators.visits import get_related_prop


class PTLBCalculator(DoneDueCalculator):

    def _preterm(self, case):
        return getattr(case, 'term', None) == "pre_term"

    def _recently_delivered(self, case):
        return _get_form(case, action_filter=af, form_filter=lambda f: f.form.get('recently_delivered', "") == 'yes')

    def filter(self, case):
        return is_pregnant_mother(case) and (
            self._recently_delivered(case) or get_related_prop(case, 'birth_status') == "live_birth")

    def _numerator(self, case):
        if self._preterm(case):
            yield get_add(case)

    def _denominator(self, case):
        yield get_add(case)

#
# class LT2KGLBCalculator(PTLBCalculator): # should change name probs
#
#     def _lt2(self, case):
#         w = _get_xpath_from_forms(case, "child_info/weight")
#         fw = _get_xpath_from_forms(case, "child_info/first_weight")
#         return True if (w is not None and w < 2.0) or (fw is not None and fw < 2.0) else False
#
#     def _numerator(self, case):
#         return 1 if self._lt2(case) else 0
#
# class VWOCalculator(LT2KGLBCalculator):
#
#     def _weak_baby(self, case):
#         return True if _newborn(case, 30) and (self._preterm(case) or self._lt2(case)) else False
#
#     def _denominator(self, case):
#         return 1 if self._weak_baby(case) else 0
#
#     def _numerator(self, case):
#         return 1 if _visited_in_timeframe_of_birth(case, 1) else 0
#
# class SimpleListMixin(object):
#     def _render(self, num, denom):
#         return str(denom)
#
#     def _numerator(self, case):
#         return 0
#
# class S2SCalculator(FilterOnlyCalculator, VWOCalculator):
#
#     def _denominator(self, case):
#         return 1 if self._weak_baby(case) and _get_xpath_from_forms(case, "child_info/skin_to_skin") == 'no' else 0
#
# class FVCalculator(S2SCalculator):
#
#     def _denominator(self, case):
#         return 1 if self._weak_baby(case) and _get_xpath_from_forms(case, "child_info/feed_vigour") == 'no' else 0