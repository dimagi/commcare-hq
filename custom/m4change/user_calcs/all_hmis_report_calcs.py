from __future__ import absolute_import
import fluff
from custom.m4change.constants import PMTCT_CLIENTS_FORM
from custom.m4change.user_calcs import get_date_delivery, form_passes_filter_date_delivery, get_received_on


def _get_comparison_results(field_value, comparison_operator, expected_value):
    result = True
    if isinstance(expected_value, list):
        for expected_value_item in expected_value:
            if not comparison_operator(field_value, expected_value_item):
                result = False
                break
    elif not comparison_operator(field_value, expected_value):
        result = False
    return result


class FormComparisonCalculator(fluff.Calculator):

    def __init__(self, comparisons, namespaces, filter_function=None, joint=True, *args, **kwargs):
        self.comparisons = comparisons
        self.namespaces = namespaces
        self.filter_function = filter_function
        self.get_date_function = get_date_delivery if self.filter_function is form_passes_filter_date_delivery else get_received_on
        self.joint = joint
        super(FormComparisonCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in self.namespaces and (self.filter_function is None or self.filter_function(form)):
            all_filters_passed = True
            if self.joint:
                for c in self.comparisons:
                    field_value = form.form.get(c[0], "")
                    if field_value is None:
                        field_value = ""
                    if not _get_comparison_results(field_value, c[1], c[2]):
                        all_filters_passed = False
                        break
                if all_filters_passed:
                    yield [self.get_date_function(form), 1]
            else:
                all_filters_passed = False
                for c in self.comparisons:
                    field_value = form.form.get(c[0], "")
                    if field_value is None:
                        field_value = ""
                    if _get_comparison_results(field_value, c[1], c[2]):
                        all_filters_passed = True
                        break
                if all_filters_passed:
                    yield [self.get_date_function(form), 1]


def _get_child_date_delivery(form):
    child_date_delivery = form.form.get("child_date_delivery", None)
    return child_date_delivery if child_date_delivery else None


class InfantsBornToHivInfectedWomenCotrimoxazoleLt2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == PMTCT_CLIENTS_FORM and form.form.get("commenced_drugs", None) is not None:
            commenced_drugs = form.form.get("commenced_drugs", "")
            if "infant_cotrimoxazole" in commenced_drugs:
                date_delivery = _get_child_date_delivery(form)
                if date_delivery is not None:
                    received_on = get_received_on(form)
                    if (received_on - date_delivery).days < 60:
                        yield [received_on, 1]


class InfantsBornToHivInfectedWomenCotrimoxazoleGte2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == PMTCT_CLIENTS_FORM and form.form.get("commenced_drugs", None) is not None:
            commenced_drugs = form.form.get("commenced_drugs", "")
            if "infant_cotrimoxazole" in commenced_drugs:
                date_delivery = _get_child_date_delivery(form)
                if date_delivery is not None:
                    received_on = get_received_on(form)
                    if (received_on - date_delivery).days >= 60:
                        yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestLt2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == PMTCT_CLIENTS_FORM and form.form.get("infant_dps", None) is not None:
            infant_dps = form.form.get("infant_dps", "")
            if infant_dps in ["positive", "negative"]:
                date_delivery = _get_child_date_delivery(form)
                if date_delivery is not None:
                    received_on = get_received_on(form)
                    if (received_on - date_delivery).days < 60:
                        yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestGte2Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == PMTCT_CLIENTS_FORM and form.form.get("infant_dps", None) is not None:
            infant_dps = form.form.get("infant_dps", "")
            if infant_dps in ["positive", "negative"]:
                date_delivery = _get_child_date_delivery(form)
                if date_delivery is not None:
                    received_on = get_received_on(form)
                    if (received_on - date_delivery).days >= 60:
                        yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestLt18Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == PMTCT_CLIENTS_FORM and form.form.get("infant_rapid_test", None) is not None:
            infant_rapid_test = form.form.get("infant_rapid_test", "")
            if infant_rapid_test in ["positive", "negative"]:
                date_delivery = _get_child_date_delivery(form)
                if date_delivery is not None:
                    received_on = get_received_on(form)
                    if (received_on - date_delivery).days / 30 < 18:
                        yield [received_on, 1]


class InfantsBornToHivInfectedWomenReceivedHivTestGte18Months(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == PMTCT_CLIENTS_FORM and form.form.get("infant_rapid_test", None) is not None:
            infant_rapid_test = form.form.get("infant_rapid_test", "")
            if infant_rapid_test in ["positive", "negative"]:
                date_delivery = _get_child_date_delivery(form)
                if date_delivery is not None:
                    received_on = get_received_on(form)
                    if (received_on - date_delivery).days / 30 >= 18:
                        yield [received_on, 1]
