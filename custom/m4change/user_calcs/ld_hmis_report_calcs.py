import fluff
from custom.m4change.constants import BOOKED_AND_UNBOOKED_DELIVERY_FORMS
from custom.m4change.user_calcs import get_date_delivery, get_received_on, form_passes_filter_date_delivery, \
    string_to_numeric
from operator import eq


class LdKeyValueDictCalculator(fluff.Calculator):

    def __init__(self, key_value_dict, namespaces, filter_function = None, *args, **kwargs):
        self.key_value_dict = key_value_dict
        self.namespaces = namespaces
        self.filter_function = filter_function
        self.get_date_function = get_date_delivery if self.filter_function is form_passes_filter_date_delivery else get_received_on
        super(LdKeyValueDictCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in self.namespaces and (self.filter_function is None or self.filter_function(form)):
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
    def total(self, form):
        if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS and form_passes_filter_date_delivery(form) and\
                        len(form.form.get("birth_complication", "")) > 0:
            yield [get_date_delivery(form), 1]


class ChildSexWeightCalculator(fluff.Calculator):

    def __init__(self, key_value_dict, weight, comparison, namespaces, filter_function=None, *args, **kwargs):
        self.key_value_dict = key_value_dict
        self.weight = weight
        self.comparison = comparison
        self.namespaces = namespaces
        self.filter_function = filter_function
        self.get_date_function = get_date_delivery if self.filter_function is form_passes_filter_date_delivery else get_received_on
        super(ChildSexWeightCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in self.namespaces and self.filter_function(form):
            passed_all_filters = True
            for key in self.key_value_dict:
                value = self.key_value_dict.get(key, "")
                if form.form.get(key, None) != value:
                    passed_all_filters = False
                    break
            if (self.comparison == "<" and string_to_numeric(form.form.get("baby_weight", 0.0), float) >= self.weight)\
                    or (self.comparison == '>=' and string_to_numeric(form.form.get("baby_weight", 0.0), float) < self.weight):
                passed_all_filters = False
            if passed_all_filters:
                yield [self.get_date_function(form), 1]
