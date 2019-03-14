from __future__ import absolute_import
from __future__ import unicode_literals
import fluff

from corehq.util.python_compatibility import soft_assert_type_text
from custom.m4change.constants import PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS, \
    BOOKED_AND_UNBOOKED_DELIVERY_FORMS
import six


FULL_IMMUNIZATION_VALUES = [
    'bcg',
    'hep_b_0',
    'hep_b_1',
    'hep_b_2',
    'measles_1',
    'opv_0',
    'opv_1',
    'opv_2',
    'opv_3',
    'pcv_1',
    'pcv_2',
    'pcv_3',
    ('penta_1', 'dpt_1'),
    ('penta_2', 'dpt_2'),
    ('penta_3', 'dpt_3'),
]


def _check_immunization_value_tuple(form, field_name, values):
    for value in values:
        if str(value) in form.form.get(field_name, ""):
            return True
    return False


class PncImmunizationCalculator(fluff.Calculator):

    def __init__(self, value):
        super(PncImmunizationCalculator, self).__init__()
        self.immunization_given_value = value

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS or \
                                form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS and \
                                self.immunization_given_value in form.form.get("immunization_given", ""):
            yield [form.received_on.date(), 1]


class PncFullImmunizationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS:
            all_passed = True
            for value in FULL_IMMUNIZATION_VALUES:
                if isinstance(value, six.string_types):
                    soft_assert_type_text(value)
                passed = value in form.form.get("immunization_given", "") if isinstance(value, six.string_types)\
                    else _check_immunization_value_tuple(form, "immunization_given", value)
                if not passed:
                    all_passed = False
                    break
            if all_passed:
                yield [form.received_on.date(), 1]
