import fluff
from custom.m4change.constants import PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS, BOOKING_AND_FOLLOW_UP_FORMS, \
    BOOKING_FORMS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS
from custom.m4change.user_calcs import is_user_in_CCT_by_case


class AncRegistrationCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        if is_user_in_CCT_by_case(case):
            for form in case.get_forms():
                if form.xmlns in BOOKING_FORMS:
                    yield [case.modified_on.date(), 1]


class Anc4VisitsCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        if is_user_in_CCT_by_case(case):
            visits = []
            for form in case.get_forms():
                if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
                    if form.received_on not in visits:
                        visits.append(form.received_on)
            if len(visits) >= 4:
                yield [case.modified_on.date(), 1]


class FacilityDeliveryCctCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if case.type == "pregnant_mother" and is_user_in_CCT_by_case(case):
            form_filled = False
            for form in case.get_forms():
                if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS:
                    form_filled = True
                    break
            if form_filled:
                yield [case.modified_on.date(), 1]


class PncAttendanceWithin6WeeksCalculator(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        if case.type == "child" and is_user_in_CCT_by_case(case):
            date_delivery = case.date_delivery
            for form in case.get_forms():
                date_received_on = form.received_on.date()
                if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS:
                    if (date_received_on - date_delivery).days < 42:
                        yield [date_received_on, 1]
