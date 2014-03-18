import fluff
from custom.m4change.constants import BOOKED_AND_UNBOOKED_DELIVERY_FORMS, FOLLOW_UP_FORMS, BOOKING_FORMS, \
    IMMUNIZATION_FORMS, BOOKING_AND_FOLLOW_UP_FORMS

ALL_ELIGIBLE_CLIENTS_FORMS = BOOKING_FORMS + FOLLOW_UP_FORMS + BOOKED_AND_UNBOOKED_DELIVERY_FORMS + IMMUNIZATION_FORMS


class AllEligibleClientsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in ALL_ELIGIBLE_CLIENTS_FORMS:
            if form.xmlns in FOLLOW_UP_FORMS:
                if form.form.get("visits", 0) in range(1, 5):
                    yield [form.received_on, 1]
            else:
                yield [form.received_on, 1]


class EligibleDueToRegistrationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKING_FORMS:
            yield [form.received_on, 1]


class EligibleDueTo4thVisitCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in FOLLOW_UP_FORMS and form.form.get("visits", "") == "4":
            yield [form.received_on, 1]


class EligibleDueToDeliveryCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS:
            yield [form.received_on, 1]


class EligibleDueToImmunizationOrPncVisitCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns in IMMUNIZATION_FORMS:
            yield [form.received_on, 1]


class StatusCalculator(fluff.Calculator):
    form_ids = None

    def _get_total(self, form, namespaces, status):
        if self.form_ids is None:
            from custom.m4change.models import McctStatus
            self.form_ids = McctStatus.get_status_dict()
        if form.xmlns in namespaces and form._id in self.form_ids.get(status, []):
            return True
        return False

    def _get_total_4th_visit(self, form, namespaces, status):
        if self.form_ids is None:
            from custom.m4change.models import McctStatus
            self.form_ids = McctStatus.get_status_dict()
        if form.xmlns in namespaces and form._id in self.form_ids.get(status, []) and form.form.get("visits", "") == "4":
            return True
        return False

    @fluff.date_emitter
    def reviewed_due_to_registration(self, form):
        if self._get_total(form, BOOKING_FORMS, "reviewed") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def reviewed_due_to_4th_visit(self, form):
        if self._get_total_4th_visit(form, BOOKING_AND_FOLLOW_UP_FORMS, "reviewed") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def reviewed_due_to_delivery(self, form):
        if self._get_total(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, "reviewed") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def reviewed_due_to_immun_or_pnc_visit(self, form):
        if self._get_total(form, IMMUNIZATION_FORMS, "reviewed") == True:
            yield [form.received_on, 1]
    
    @fluff.date_emitter
    def approved_due_to_registration(self, form):
        if self._get_total(form, BOOKING_FORMS, "approved") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def approved_due_to_4th_visit(self, form):
        if self._get_total_4th_visit(form, BOOKING_AND_FOLLOW_UP_FORMS, "approved") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def approved_due_to_delivery(self, form):
        if self._get_total(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, "approved") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def approved_due_to_immun_or_pnc_visit(self, form):
        if self._get_total(form, IMMUNIZATION_FORMS, "approved") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_registration(self, form):
        if self._get_total(form, BOOKING_FORMS, "rejected") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_4th_visit(self, form):
        if self._get_total_4th_visit(form, BOOKING_AND_FOLLOW_UP_FORMS, "rejected") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_delivery(self, form):
        if self._get_total(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, "rejected") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_immun_or_pnc_visit(self, form):
        if self._get_total(form, IMMUNIZATION_FORMS, "rejected") == True:
            yield [form.received_on, 1]
