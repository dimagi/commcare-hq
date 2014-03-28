import fluff
import operator
from custom.m4change.user_calcs import get_case_date_delivery, case_passes_filter_date_delivery, get_case_date_modified, \
    case_passes_filter_date_modified


def _get_comparison_results(field_value, comparison_operator, value):
    result = True
    is_contains_operator = (comparison_operator == operator.contains)
    if isinstance(value, list):
        for value_item in value:
            value_tuple = (value_item, field_value) if is_contains_operator else (field_value, value_item)
            if not comparison_operator(value_tuple[0], value_tuple[1]):
                result = False
                break
    else:
        value_tuple = (value, field_value) if is_contains_operator else (field_value, value)
        if not comparison_operator(value_tuple[0], value_tuple[1]):
            result = False
    return result


class CaseComparisonCalculator(fluff.Calculator):

    def __init__(self, comparisons, filter_function, *args, **kwargs):
        self.comparisons = comparisons
        self.filter_function = filter_function
        self.get_date_function = get_case_date_delivery if self.filter_function is case_passes_filter_date_delivery else get_case_date_modified
        super(CaseComparisonCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        if self.filter_function(case):
            all_filters_passed = True
            for comparison in self.comparisons:
                field_value = case[comparison[0]] if hasattr(case, comparison[0]) else ""
                if field_value is None:
                    field_value = ""
                if not _get_comparison_results(field_value, comparison[1], comparison[2]):
                    all_filters_passed = False
                    break
            if all_filters_passed:
                yield [self.get_date_function(case), 1]


class InfantsBornToHivInfectedWomenCotrimoxazoleLt2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "commenced_drugs") and case_passes_filter_date_delivery(case) and case_passes_filter_date_modified(case):
            commenced_drugs = case.get("commenced_drugs", "")
            if "infant_cotrimoxazole" in commenced_drugs:
                date_delivery = get_case_date_delivery(case)
                date_modified = get_case_date_modified(case)
                if (date_modified - date_delivery).days < 60:
                    yield [case.modified_on.date(), 1]


class InfantsBornToHivInfectedWomenCotrimoxazoleGte2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "commenced_drugs") and case_passes_filter_date_delivery(
                case) and case_passes_filter_date_modified(case):
            commenced_drugs = case.get("commenced_drugs", "")
            if "infant_cotrimoxazole" in commenced_drugs:
                date_delivery = get_case_date_delivery(case)
                date_modified = get_case_date_modified(case)
                if (date_modified - date_delivery).days >= 60:
                    yield [case.modified_on.date(), 1]


class InfantsBornToHivInfectedWomenReceivedHivTestLt2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "infant_dps") and case_passes_filter_date_delivery(
                case) and case_passes_filter_date_modified(case):
            infant_dps = case.get("infant_dps", "")
            if infant_dps in ["positive", "negative"]:
                date_delivery = get_case_date_delivery(case)
                date_modified = get_case_date_modified(case)
                if (date_modified - date_delivery).days < 60:
                    yield [case.modified_on.date(), 1]


class InfantsBornToHivInfectedWomenReceivedHivTestGte2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "infant_dps") and case_passes_filter_date_delivery(
                case) and case_passes_filter_date_modified(case):
            infant_dps = case.get("infant_dps", "")
            if infant_dps in ["positive", "negative"]:
                date_delivery = get_case_date_delivery(case)
                date_modified = get_case_date_modified(case)
                if (date_modified - date_delivery).days >= 60:
                    yield [case.modified_on.date(), 1]


class InfantsBornToHivInfectedWomenReceivedHivTestLt18Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "infant_rapid_test") and case_passes_filter_date_delivery(
                case) and case_passes_filter_date_modified(case):
            infant_rapid_test = case.get("infant_rapid_test", "")
            if infant_rapid_test in ["positive", "negative"]:
                date_delivery = get_case_date_delivery(case)
                date_modified = get_case_date_modified(case)
                if (date_modified - date_delivery).days / 30 < 18:
                    yield [case.modified_on.date(), 1]


class InfantsBornToHivInfectedWomenReceivedHivTestGte18Months(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "infant_rapid_test") and case_passes_filter_date_delivery(
                case) and case_passes_filter_date_modified(case):
            infant_rapid_test = case.get("infant_rapid_test", "")
            if infant_rapid_test in ["positive", "negative"]:
                date_delivery = get_case_date_delivery(case)
                date_modified = get_case_date_modified(case)
                if (date_modified - date_delivery).days / 30 >= 18:
                    yield [case.modified_on.date(), 1]

