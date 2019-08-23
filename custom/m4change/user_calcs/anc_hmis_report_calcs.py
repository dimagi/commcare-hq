import fluff
from custom.m4change.constants import BOOKING_FORMS, FOLLOW_UP_FORMS, BOOKING_AND_FOLLOW_UP_FORMS, \
    PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS, BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS
from custom.m4change.user_calcs import string_to_numeric


class AncAntenatalAttendanceCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
            yield [form.received_on.date(), 1]


class AncAntenatalVisitBefore20WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS and form.form.get("registered_early", "") == "yes":
            yield [form.received_on.date(), 1]


class AncAntenatalVisitAfter20WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS and form.form.get("registered_early", "") == "no":
            yield [form.received_on.date(), 1]


class AncAttendanceGreaterEqual4VisitsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in FOLLOW_UP_FORMS and string_to_numeric(form.form.get("visits", "0")) >= 4:
            yield [form.received_on.date(), 1]


class AncSyphilisTestDoneCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS \
                and "syphilis" in form.form.get("tests_conducted", ""):
            yield [form.received_on.date(), 1]


class AncSyphilisPositiveCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
            if form.xmlns in BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS \
                    and form.form.get("syphilis_result", "") == "positive":
                yield [form.received_on.date(), 1]


class AncSyphilisCaseTreatedCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS \
                and form.form.get("syphilis_result", "") == "positive" \
                and form.form.get("client_status", "") == "treated":
            yield [form.received_on.date(), 1]


class PregnantMothersReceivingIpt1Calculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "ipt_1" in form.form.get("items_given", ""):
            yield [form.received_on.date(), 1]


class PregnantMothersReceivingIpt2Calculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "ipt_2" in form.form.get("items_given", ""):
            yield [form.received_on.date(), 1]


class PregnantMothersReceivingLlinCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "llin" in form.form.get("items_given", ""):
            yield [form.received_on.date(), 1]


class PregnantMothersReceivingIfaCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS and "ifa" in form.form.get("items_given", ""):
            yield [form.received_on.date(), 1]


class PostnatalAttendanceCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS:
            pnc_visits = str(form.form.get("pnc_visits", 0))
            if pnc_visits is None or not pnc_visits.isdigit():
                pnc_visits = 0
            pnc_visits = int(pnc_visits)
            yield [form.received_on.date(), pnc_visits]


class PostnatalClinicVisitWithin1DayOfDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("date_delivery", None) is not None:
            days_after_delivery = (form.received_on.date() - form.form["date_delivery"]).days
            if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and days_after_delivery <= 1:
                yield [form.received_on.date(), 1]


class PostnatalClinicVisitWithin3DaysOfDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("date_delivery", None) is not None:
            days_after_delivery = (form.received_on.date() - form.form["date_delivery"]).days
            if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS \
                    and days_after_delivery > 1 and days_after_delivery <= 3:
                yield [form.received_on.date(), 1]


class PostnatalClinicVisitGreaterEqual7DaysOfDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.form.get("date_delivery", None) is not None:
            days_after_delivery = (form.received_on.date() - form.form["date_delivery"]).days
            if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and days_after_delivery >= 7:
                yield [form.received_on.date(), 1]
