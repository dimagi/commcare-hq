import fluff
from custom.m4change.constants import BOOKED_AND_UNBOOKED_DELIVERY_FORMS, FOLLOW_UP_FORMS, BOOKING_FORMS, \
    IMMUNIZATION_FORMS, BOOKING_AND_FOLLOW_UP_FORMS

ALL_ELIGIBLE_CLIENTS_FORMS = BOOKING_FORMS + FOLLOW_UP_FORMS + BOOKED_AND_UNBOOKED_DELIVERY_FORMS + IMMUNIZATION_FORMS


class StatusCalculator(fluff.Calculator):
    status_dict = None

    def _update_form_ids(self):
        if self.status_dict is None:
            from custom.m4change.models import McctStatus
            self.status_dict = McctStatus.get_status_dict()

    def _get_total(self, form, namespaces, status):
        self._update_form_ids()
        if form.xmlns not in namespaces:
            return False
        for status_element in self.status_dict.get(status, []):
            if form._id == status_element["form_id"]:
                return True
        return False

    def _get_total_4th_visit(self, form, namespaces, status):
        self._update_form_ids()
        if form.xmlns not in namespaces or form.form.get("visits", "") != "4":
            return False
        for status_element in self.status_dict.get(status, []):
            if form._id == status_element["form_id"]:
                return True
        return False

    def _get_total_eligible(self, form, namespaces, restrict_4th_visit=False):
        self._update_form_ids()
        if form.xmlns not in namespaces or (restrict_4th_visit and form.form.get("visits", "") != "4"):
            return False
        for status_element in self.status_dict.get("eligible", []):
            if form._id == status_element["form_id"] and (status_element["is_booking"] or status_element["immunized"]):
                return True
        return False

    def _get_total_rejected(self, form, reason):
        self._update_form_ids()
        for status_element in self.status_dict.get("rejected", []):
            if form._id == status_element["form_id"] and status_element["reason"] == reason:
                return True
        return False

    @fluff.date_emitter
    def eligible_due_to_registration(self, form):
        if self._get_total(form, BOOKING_FORMS, "eligible") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def eligible_due_to_4th_visit(self, form):
        if self._get_total_eligible(form, FOLLOW_UP_FORMS, True) == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def eligible_due_to_delivery(self, form):
        if self._get_total_eligible(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS) == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def eligible_due_to_immun_or_pnc_visit(self, form):
        if self._get_total(form, IMMUNIZATION_FORMS, "eligible") == True:
            yield [form.received_on, 1]

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
    def paid_due_to_registration(self, form):
        if self._get_total(form, BOOKING_FORMS, "paid") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def paid_due_to_4th_visit(self, form):
        if self._get_total_4th_visit(form, BOOKING_AND_FOLLOW_UP_FORMS, "paid") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def paid_due_to_delivery(self, form):
        if self._get_total(form, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, "paid") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def paid_due_to_immun_or_pnc_visit(self, form):
        if self._get_total(form, IMMUNIZATION_FORMS, "paid") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_incorrect_phone_number(self, form):
        if self._get_total_rejected(form, "phone_number") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_double_entry(self, form):
        if self._get_total_rejected(form, "double") == True:
            yield [form.received_on, 1]

    @fluff.date_emitter
    def rejected_due_to_other_errors(self, form):
        if self._get_total_rejected(form, "other") == True:
            yield [form.received_on, 1]
