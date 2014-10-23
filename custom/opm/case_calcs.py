"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers).
These are used in the Beneficiary Payment Report
"""
import datetime

import fluff

from .constants import *


def case_date_group(form):
    return form.received_on


def case_date(case):
    return case.opened_on


months = (('4', '1'), ('5', '2'), ('6', '3'), ('7', '4'), ('8', '5'), ('9', '6'),)


def is_equals(form, prop1, prop2, start=0, end=6, count=0):
    c = 0
    check = False
    for (k, v) in months[start:end]:
        p1 = prop1 % k
        p2 = prop2 % v
        if p1 in form.form and p2 in form.form[p1] and form.form[p1][p2] == '1':
            c += 1
            check = True
    return check if c > count else (None, False)


def num_of_children(form, prop1, prop2, num_in_condition, children):
    c = 0
    for num in children:
        p1 = prop1 % str(num)
        p2 = prop2 % str(num)
        if num_in_condition == 'exist':
            if p1 in form.form and p2 in form.form[p1] and form.form[p1][p2]:
                c += 1
        else:
            try:
                val = int(form.form[p1][p2])
            except (KeyError, ValueError):
                pass
            else:
                if val > num_in_condition:
                    c += 1
    return c


class MotherRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        if case.type.upper() == "PREGNANCY" and getattr(case, 'bank_account_number', None) is not None:
            yield case_date(case)


class VhndMonthly(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns == BIRTH_PREP_XMLNS and is_equals(form, "pregnancy_month_%s", "attendance_vhnd_%s"):
                yield case_date_group(form)
                break
            elif form.xmlns in CHILDREN_FORMS and form.form['child_1']['child1_attendance_vhnd'] == 1:
                yield case_date_group(form)
                break



def check_status(form, status):
    for prop in ['interpret_grade', 'interpret_grade_2', 'interpret_grade_3']:
        if prop in form.form and form.form[prop].upper() == status:
            return True
    return False


class Status(fluff.Calculator):
    def __init__(self, status, *args, **kwargs):
        self.status = status
        super(Status, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns in CHILDREN_FORMS and check_status(form, self.status):
                yield case_date_group(form)


class Weight(fluff.Calculator):
    def __init__(self, count=0, *args, **kwargs):
        self.count = count
        super(Weight, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns == BIRTH_PREP_XMLNS and is_equals(form, "pregnancy_month_%s", "mother_weight_%s", count=self.count):
                yield case_date_group(form)
                break


class BreastFed(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        birth_amount = None
        for form in case.get_forms():
            if form.xmlns == DELIVERY_XMLNS and 'live_birth_amount' in form.form:
                birth_amount = form.form['live_birth_amount']
        if birth_amount:
            for form in case.get_forms():
                if form.xmlns == CFU1_XMLNS:
                    yield {
                        'date': case_date_group(form),
                        'value': num_of_children(form, 'child_%s', 'child%s_child_excbreastfed', 0,
                                                 range(1, (int(birth_amount) + 1)))
                    }


class ChildrenInfo(fluff.Calculator):
    def __init__(self, prop, num_in_condition=0, forms=CHILDREN_FORMS, *args, **kwargs):
        self.num_in_condition = num_in_condition
        self.prop1 = 'child_%s'
        self.prop2 = prop
        self.forms = forms
        super(ChildrenInfo, self).__init__(*args, **kwargs)

    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns in self.forms:
                yield {
                    'date': case_date_group(form),
                    'value': num_of_children(form, self.prop1, self.prop2, self.num_in_condition, [1, 2, 3])
                }


class IfaTablets(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns == BIRTH_PREP_XMLNS and is_equals(form, "pregnancy_month_%s", "ifa_receive_%s", start=0, end=3):
                yield case_date_group(form)
                break


class Lactating(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns == DELIVERY_XMLNS:
                if form.form.get('mother_preg_outcome') == '1':
                    yield case_date(case)


class Lmp(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns == PREG_REG_XMLNS:
                if 'lmp_date' in form.form and form.form.get('lmp_date'):
                    yield case_date(case)


class LiveChildren(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns == DELIVERY_XMLNS:
                if 'live_birth_amount' in form.form and form.form.get('live_birth_amount'):
                    yield {
                        'date': case_date(case),
                        'value': form.form.get('live_birth_amount')
                    }


class VhndAvailabilityCalc(fluff.Calculator):

    def dates_from_forms(self, case, condition):
        """
        Condition should accept a form and return a boolean
        """
        available = False
        for form in case.get_forms():
            vhnd_date = form.form.get("date_vhnd_held")
            if isinstance(vhnd_date, (datetime.datetime, datetime.date)):
                if condition(form):
                    available = True
                    yield vhnd_date
        if not available:
            yield [datetime.date.min, 0]

    def dates_available(self, case, prop):
        return self.dates_from_forms(case, lambda form: form.form.get(prop) == '1')

    @fluff.date_emitter
    def available(self, case):
        return self.dates_from_forms(case, lambda form: True)

    @fluff.date_emitter
    def ifa_available(self, case):
        return self.dates_available(case, "stock_ifatab")

    @fluff.date_emitter
    def adult_scale_available(self, case):
        return self.dates_available(case, "func_bigweighmach")

    @fluff.date_emitter
    def child_scale_available(self, case):
        return self.dates_available(case, "func_childweighmach")

    @fluff.date_emitter
    def ors_available(self, case):
        return self.dates_available(case, "stock_ors")

    @fluff.date_emitter
    def zn_available(self, case):
        return self.dates_available(case, "stock_zntab")

    @fluff.date_emitter
    def measles_vacc_available(self, case):
        return self.dates_available(case, "stock_measlesvacc")
