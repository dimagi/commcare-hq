from datetime import datetime
import fluff
from custom.m4change.constants import BOOKING_FORMS, FOLLOW_UP_FORMS, BOOKING_AND_FOLLOW_UP_FORMS,\
    PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS


def __update_value_for_date__(date, dates):
    if date not in dates:
        dates[date] = 1
    else:
        dates[date] += 1


class PncImmunizationCalculator(fluff.Calculator):
    def __init__(self, value):
        super(PncImmunizationCalculator, self).__init__()
        self.immunization_given_value = value

    @fluff.date_emitter
    def total(self, case):
        if case.type == "child":
            if self.immunization_given_value in case.immunization_given:
                return[case.date_modified, 1]
            for form in case.get_forms():
                if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and self.immunization_given_value in form.form.get("immunization_given", ""):
                    return[case.date_modified, 1]
            return[case.date_modified, 0]

class PncFullImmunizationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if case.type == "child":
            full_immunization_values = ['opv_0', 'hep_b_0', 'bcg', 'opv_1', 'hep_b_1', 'penta_1', 'dpt_1',
                                        'pcv_1', 'opv_2','hep_b_2', 'penta_2', 'dpt_2', 'pcv_2', 'opv_3', 'penta_3',
                                        'dpt_3', 'pcv_3', 'measles_1', 'yellow_fever', 'measles_2', 'conjugate_csm']
            if all(value in case.immunization_given for value in full_immunization_values):
                return[case.date_modified, 1]
            return[case.date_modified, 0]


class AncAntenatalAttendanceCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
                visits = str(form.form.get("visits", 0))
                if not visits.isdigit():
                    visits = 0
                visits = int(visits)
                if form.received_on not in dates:
                    dates[form.received_on] = visits
                else:
                    dates[form.received_on] += visits
        for date in dates:
            yield [date, dates[date]]


class AncAntenatalVisitBefore20WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_FORMS and form.form.get("registered_early", "") == "yes":
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncAntenatalVisitAfter20WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_FORMS and form.form.get("registered_early", "") == "no":
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncAttendanceGreaterEqual4VisitsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and form.form.get("visits", 0) >= 4:
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncSyphilisTestDoneCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and "syphilis" in form.form.get("tests_conducted", ""):
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncSyphilisPositiveCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and form.form.get("syphilis_result", "") == "positive":
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncSyphilisCaseTreatedCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and form.form.get("syphilis_result", "") == "positive"\
                    and form.form.get("client_diagnosis", "") == "treated":
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingIpt1Calculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
                if "IPT" in form.form.get("drugs_given", ""):
                    __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingIpt2Calculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and "ipt" in form.form.get("drugs_given", ""):
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingLlinCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "llin" in form.form.get("drugs_given", ""):
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingIfaCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "ifa" in form.form.get("drugs_given", ""):
                __update_value_for_date__(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PostnatalAttendanceCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS:
                pnc_visits = str(form.form.get("pnc_visits", 0))
                if pnc_visits is None or not pnc_visits.isdigit():
                    pnc_visits = 0
                pnc_visits = int(pnc_visits)
                if form.received_on not in dates:
                    dates[form.received_on] = pnc_visits
                else:
                    dates[form.received_on] += pnc_visits
        for date in dates:
            yield [date, dates[date]]


class PostnatalClinicVisitWithin1DayOfDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        if case.type == "child":
            date_modified = case.modified_on
            date_delivery = case.date_delivery
            dt = date_modified - datetime.combine(date_delivery, datetime.min.time())
            for form in case.get_forms():
                if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and dt.days <= 1:
                    __update_value_for_date__(form.received_on, dates)
            for date in dates:
                yield [date, dates[date]]


class PostnatalClinicVisitWithin3DaysOfDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        if case.type == "child":
            date_modified = case.modified_on
            date_delivery = case.date_delivery
            dt = date_modified - datetime.combine(date_delivery, datetime.min.time())
            for form in case.get_forms():
                if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and dt.days <= 3:
                    __update_value_for_date__(form.received_on, dates)
            for date in dates:
                yield [date, dates[date]]


class PostnatalClinicVisitGreaterEqual7DaysOfDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        if case.type == "child":
            date_modified = case.modified_on
            date_delivery = case.date_delivery
            dt = date_modified - datetime.combine(date_delivery, datetime.min.time())
            for form in case.get_forms():
                if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and dt.days >= 7:
                    __update_value_for_date__(form.received_on, dates)
            for date in dates:
                yield [date, dates[date]]
