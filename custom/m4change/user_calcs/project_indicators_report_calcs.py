import fluff
from custom.m4change.constants import PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS, \
    BOOKING_FORMS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS


class AncRegistrationCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS:
            yield [form.received_on.date(), 1]


class Anc4VisitsCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS:
            visits = form.form.get("visits", "")
            if len(visits) > 0 and visits.isdigit() and int(visits) == 4:
                yield [form.received_on.date(), 1]


class FacilityDeliveryCctCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS:
            yield [form.received_on.date(), 1]


class PncAttendanceWithin6WeeksCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if form.form.get("date_delivery", None) is not None:
            date_received_on = form.received_on.date()
            if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS \
                    and (date_received_on - form.form["date_delivery"]).days < 42:
                yield [date_received_on, 1]


class NumberOfFreeSimsGivenCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS and form.form.get("free_sim", "") == 'yes':
                yield [form.received_on.date(), 1]


class MnoCalculator(fluff.Calculator):
    def __init__(self, value):
        super(MnoCalculator, self).__init__()
        self.mno_type_value = value

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS and self.mno_type_value == form.form.get("mno", ""):
            yield [form.received_on.date(), 1]
