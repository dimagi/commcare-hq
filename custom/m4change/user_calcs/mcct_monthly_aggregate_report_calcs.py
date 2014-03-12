import fluff
from custom.m4change.constants import BOOKED_AND_UNBOOKED_DELIVERY_FORMS, FOLLOW_UP_FORMS, BOOKING_FORMS, \
    IMMUNIZATION_FORMS

ALL_ELIGIBLE_CLIENTS_FORMS = BOOKING_FORMS + FOLLOW_UP_FORMS + BOOKED_AND_UNBOOKED_DELIVERY_FORMS + IMMUNIZATION_FORMS


class AllEligibleClientsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in ALL_ELIGIBLE_CLIENTS_FORMS:
            if form.xmlns in FOLLOW_UP_FORMS:
                if form.form.get("visits", "") == "4":
                    yield [form.received_on, 1]
            else:
                yield [form.received_on, 1]


class EligibleDueToRegistrationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS:
            yield [form.received_on, 1]


class EligibleDueTo4thVisit(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in FOLLOW_UP_FORMS and form.form.get("visits", "") == "4":
            yield [form.received_on, 1]


class EligibleDueToDelivery(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS:
            yield [form.received_on, 1]


class EligibleDueToImmunizationOrPncVisit(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in IMMUNIZATION_FORMS:
            yield [form.received_on, 1]
