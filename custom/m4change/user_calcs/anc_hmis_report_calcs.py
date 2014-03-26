from . import update_value_for_date
from datetime import datetime
import fluff
from custom.m4change.constants import BOOKING_FORMS, FOLLOW_UP_FORMS, BOOKING_AND_FOLLOW_UP_FORMS, \
    PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS


class AncAntenatalAttendanceCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
                received_on = form.received_on.date()
                if dates.get(received_on, None) is None:
                    dates[received_on] = set()
                if form.xmlns not in dates[received_on]:
                    dates[received_on].add(form.xmlns)
        for date in dates:
            for xmlns in dates[date]:
                yield [date, 1]

class AncAntenatalVisitBefore20WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_FORMS and form.form.get("registered_early", "") == "yes":
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncAntenatalVisitAfter20WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_FORMS and form.form.get("registered_early", "") == "no":
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncAttendanceGreaterEqual4VisitsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and form.form.get("visits", 0) >= 4:
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncSyphilisTestDoneCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and "syphilis" in form.form.get("tests_conducted", ""):
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncSyphilisPositiveCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and form.form.get("syphilis_result", "") == "positive":
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class AncSyphilisCaseTreatedCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and form.form.get("syphilis_result", "") == "positive"\
                    and form.form.get("client_diagnosis", "") == "treated":
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingIpt1Calculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
                if "IPT" in form.form.get("drugs_given", ""):
                    update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingIpt2Calculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in FOLLOW_UP_FORMS and "ipt" in form.form.get("drugs_given", ""):
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingLlinCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "llin" in form.form.get("drugs_given", ""):
                update_value_for_date(form.received_on, dates)
        for date in dates:
            yield [date, dates[date]]


class PregnantMothersReceivingIfaCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        dates = dict()
        for form in case.get_forms():
            if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "ifa" in form.form.get("drugs_given", ""):
                update_value_for_date(form.received_on, dates)
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
                    update_value_for_date(form.received_on, dates)
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
                    update_value_for_date(form.received_on, dates)
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
                    update_value_for_date(form.received_on, dates)
            for date in dates:
                yield [date, dates[date]]
