import fluff
from custom.m4change.constants import BOOKED_AND_UNBOOKED_DELIVERY_FORMS


def _get_date_delivery(form):
    return form.form.get("date_delivery", None)

def _get_date_modified(form):
    return form.form.get("case", {}).get("@date_modified", None)

def form_passes_filter_date_delivery(form, namespaces):
    return (form.xmlns in namespaces and _get_date_delivery(form) is not None)

def form_passes_filter_date_modified(form, namespaces):
    return (form.xmlns in namespaces and _get_date_modified(form) is not None)


class LdKeyValueDictCalculator(fluff.Calculator):

    def __init__(self, key_value_dict, namespaces, filter_function, *args, **kwargs):
        self.key_value_dict = key_value_dict
        self.namespaces = namespaces
        self.filter_function = filter_function
        self.get_date_function = _get_date_delivery if self.filter_function is _get_date_delivery else _get_date_modified
        super(LdKeyValueDictCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if self.filter_function(form, self.namespaces):
                passed_all_filters = True
                for key in self.key_value_dict:
                    value = self.key_value_dict.get(key, "")
                    if form.form.get(key, None) != value:
                        passed_all_filters = False
                        break
                if passed_all_filters:
                    yield [self.get_date_function(form), 1]


class DeliveriesComplicationsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form_passes_filter_date_delivery(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS) and\
                            len(form.form.get("delivery_type", "")) > 0:
                yield [_get_date_delivery(form), 1]


class ChildSexWeightCalculator(fluff.Calculator):

    def __init__(self, key_value_dict, weight, comparison, namespaces, *args, **kwargs):
        self.key_value_dict = key_value_dict
        self.weight = weight
        self.comparison = comparison
        self.namespaces = namespaces
        super(ChildSexWeightCalculator, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form_passes_filter_date_delivery(form, self.namespaces):
                passed_all_filters = True
                for key in self.key_value_dict:
                    value = self.key_value_dict.get(key, "")
                    if form.form.get(key, None) != value:
                        passed_all_filters = False
                        break
                if (self.comparison == "<" and float(form.form.get("baby_weight", 0.0)) >= self.weight)\
                        or (float(form.form.get("baby_weight", 0.0) < self.weight)):
                    passed_all_filters = False
                if passed_all_filters:
                    yield [_get_date_delivery(form), 1]
