import fluff
from custom.m4change.constants import PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS, \
    BOOKING_FORMS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS


class AncRegistrationCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        for form in case.get_forms():
            if form.xmlns in BOOKING_FORMS:
                yield [form.received_on.date(), 1]


class Anc4VisitsCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        visits = []
        for form in case.get_forms():
            received_on_date = form.received_on.date()
            if form.xmlns in BOOKING_FOLLOW_UP_AND_LAB_RESULTS_FORMS \
                    and [received_on_date, form.xmlns] not in visits:
                visits.append([received_on_date, form.xmlns])
                if len(visits) == 4:
                    yield [received_on_date, 1]


class FacilityDeliveryCctCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        delivery_dates = []
        for form in case.get_forms():
            received_on_date = form.received_on.date()
            if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS and received_on_date not in delivery_dates:
                delivery_dates.append(received_on_date)
                yield [received_on_date, 1]


class PncAttendanceWithin6WeeksCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "date_delivery"):
            date_delivery = case.date_delivery
            for form in case.get_forms():
                date_received_on = form.received_on.date()
                if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS \
                        and (date_received_on - date_delivery).days < 42:
                    yield [date_received_on, 1]
