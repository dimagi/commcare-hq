import fluff
import operator
from custom.m4change.user_calcs import get_date_delivery, form_passes_filter_date_delivery, get_received_on


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


class FormComparisonCalculator(fluff.Calculator):

    def __init__(self, comparisons, namespaces, filter_function = None, *args, **kwargs):
        self.comparisons = comparisons
        self.namespaces = namespaces
        self.filter_function = filter_function
        self.get_date_function = get_date_delivery if self.filter_function is form_passes_filter_date_delivery else get_received_on
        super(FormComparisonCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if self.filter_function is None or self.filter_function(form, self.namespaces):
            all_filters_passed = True
            for comparison in self.comparisons:
                field_value = form.form.get(comparison[0], "")
                if field_value is None:
                    field_value = ""
                if not _get_comparison_results(field_value, comparison[1], comparison[2]):
                    all_filters_passed = False
                    break
            if all_filters_passed:
                yield [self.get_date_function(form), 1]


class InfantsBornToHivInfectedWomenCotrimoxazoleLt2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("commenced_drugs", None) is not None:
            commenced_drugs = form.form.get("commenced_drugs", "")
            if "infant_cotrimoxazole" in commenced_drugs:
                date_delivery = get_date_delivery(form)
                received_on = get_received_on(form)
                if (received_on - date_delivery).days < 60:
                    yield [received_on, 1]


class InfantsBornToHivInfectedWomenCotrimoxazoleGte2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("commenced_drugs", None) is not None:
            commenced_drugs = form.form.get("commenced_drugs", "")
            if "infant_cotrimoxazole" in commenced_drugs:
                date_delivery = get_date_delivery(form)
                received_on = get_received_on(form)
                if (received_on - date_delivery).days >= 60:
                    yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestLt2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("infant_dps", None) is not None:
            infant_dps = form.form.get("infant_dps", "")
            if infant_dps in ["positive", "negative"]:
                date_delivery = get_date_delivery(form)
                received_on = get_received_on(form)
                if (received_on - date_delivery).days < 60:
                    yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestGte2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("infant_dps", None) is not None:
            infant_dps = form.form.get("infant_dps", "")
            if infant_dps in ["positive", "negative"]:
                date_delivery = get_date_delivery(form)
                received_on = get_received_on(form)
                if (received_on - date_delivery).days >= 60:
                    yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestLt18Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("infant_rapid_test", None) is not None:
            infant_rapid_test = form.form.get("infant_rapid_test", "")
            if infant_rapid_test in ["positive", "negative"]:
                date_delivery = get_date_delivery(form)
                received_on = get_received_on(form)
                if (received_on - date_delivery).days / 30 < 18:
                    yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestGte18Months(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if form.form.get("infant_rapid_test", None) is not None:
            infant_rapid_test = form.form.get("infant_rapid_test", "")
            if infant_rapid_test in ["positive", "negative"]:
                date_delivery = get_date_delivery(form)
                received_on = get_received_on(form)
                if (received_on - date_delivery).days / 30 >= 18:
                    yield [received_on, 1]
