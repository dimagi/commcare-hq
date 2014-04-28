import fluff
from custom.m4change.constants import BOOKED_AND_UNBOOKED_DELIVERY_FORMS, CHILD_CASE_TYPE, MOTHER_CASE_TYPE
from custom.m4change.user_calcs import get_date_delivery, get_date_modified, form_passes_filter_date_delivery
from operator import eq


class LdKeyValueDictCalculator(fluff.Calculator):

    def __init__(self, key_value_dict, namespaces, filter_function, case_type, *args, **kwargs):
        self.key_value_dict = key_value_dict
        self.namespaces = namespaces
        self.filter_function = filter_function
        self.case_type = case_type
        self.get_date_function = get_date_delivery if self.filter_function is form_passes_filter_date_delivery else get_date_modified
        super(LdKeyValueDictCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        if case.type == self.case_type:
            for form in case.get_forms():
                if self.filter_function(form, self.namespaces):
                    passed_all_filters = True
                    for key in self.key_value_dict:
                        filter_element = self.key_value_dict.get(key, "")
                        filter_value = filter_element.get("value", "")
                        filter_comparator = filter_element.get("comparator", eq)
                        form_value = form.form.get(key, None)
                        if not filter_comparator(form_value, filter_value):
                            passed_all_filters = False
                            break
                    if passed_all_filters:
                        yield [self.get_date_function(form), 1]


class DeliveriesComplicationsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if case.type == MOTHER_CASE_TYPE:
            for form in case.get_forms():
                if form_passes_filter_date_delivery(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS) and\
                                len(form.form.get("birth_complication", "")) > 0:
                    yield [get_date_delivery(form), 1]


class ChildSexWeightCalculator(fluff.Calculator):

    def __init__(self, key_value_dict, weight, comparison, namespaces, *args, **kwargs):
        self.key_value_dict = key_value_dict
        self.weight = weight
        self.comparison = comparison
        self.namespaces = namespaces
        super(ChildSexWeightCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        if case.type == CHILD_CASE_TYPE:
            for form in case.get_forms():
                if form_passes_filter_date_delivery(form, self.namespaces):
                    passed_all_filters = True
                    for key in self.key_value_dict:
                        value = self.key_value_dict.get(key, "")
                        if form.form.get(key, None) != value:
                            passed_all_filters = False
                            break

                    if (self.comparison == "<" and float(form.form.get("baby_weight", 0.0)) >= self.weight)\
                            or (self.comparison == '>=' and float(form.form.get("baby_weight", 0.0) < self.weight)):
                        passed_all_filters = False

                    if passed_all_filters:
                        yield [get_date_delivery(form), 1]
