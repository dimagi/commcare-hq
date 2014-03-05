from datetime import datetime
import fluff
from corehq.apps.users.models import CommCareUser
from custom.m4change.constants import BOOKING_FORMS, FOLLOW_UP_FORMS, BOOKING_AND_FOLLOW_UP_FORMS,\
    PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS, IMMUNIZATION_FORMS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS


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
            if case.get_case_property("immunization_given") is not None and self.immunization_given_value in case.get_case_property("immunization_given"):
                yield[case.modified_on, 1]
            else:
                for form in case.get_forms():
                    if form.xmlns in PNC_CHILD_IMMUNIZATION_AND_REG_HOME_DELIVERED_FORMS and self.immunization_given_value in form.form.get("immunization_given", ""):
                        yield[case.modified_on, 1]


class PncFullImmunizationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if case.type == "child" and case.get_case_property("immunization_given") is not None:
            full_immunization_values = ['opv_0', 'hep_b_0', 'bcg', 'opv_1', 'hep_b_1', 'penta_1', 'dpt_1',
                                        'pcv_1', 'opv_2', 'hep_b_2', 'penta_2', 'dpt_2', 'pcv_2', 'opv_3', 'penta_3',
                                        'dpt_3', 'pcv_3', 'measles_1', 'yellow_fever', 'measles_2', 'conjugate_csm']
            if all(value in case.get_case_property("immunization_given") for value in full_immunization_values):
                yield[case.modified_on, 1]


class AncRegistrationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        # ignoring user_id == "demo_user", because it causes errors to show up in the logs
        if case.type == "pregnant_mother" and hasattr(case, "user_id") and case.user_id != "demo_user":
            for form in case.get_forms():
                if form.xmlns in BOOKING_FORMS:
                    user = CommCareUser.get(case.user_id) or None
                    if user is not None and hasattr(user, "user_data") and user.user_data.get("CCT", None) == "true":
                        yield [case.modified_on.date(), 1]


class Anc4VisitsCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if hasattr(case, "user_id") and case.user_id != "demo_user":
            visits = []
            for form in case.get_forms():
                if form.xmlns in BOOKING_AND_FOLLOW_UP_FORMS:
                    user = CommCareUser.get(case.user_id) or None
                    if user is not None and hasattr(user, "user_data") and user.user_data.get("CCT", None) == "true"\
                            and form.received_on not in visits:
                        visits.append(form.received_on)
            if len(visits) >= 4:
                yield [case.modified_on.date(), 1]


class FacilityDeliveryCctCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        # ignoring user_id == "demo_user", because it causes errors to show up in the logs
        if case.type == "pregnant_mother" and hasattr(case, "user_id") and case.user_id != "demo_user":
            form_filled = False
            for form in case.get_forms():
                if form.xmlns in BOOKED_AND_UNBOOKED_DELIVERY_FORMS:
                    user = CommCareUser.get(case.user_id) or None
                    if user is not None and hasattr(user, "user_data") and user.user_data.get("CCT", None) == "true":
                        form_filled = True
                        break
            if form_filled:
                yield [case.modified_on.date(), 1]


class PncAttendanceWithin6WeeksCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if case.type == "child":
            date_delivery = case.date_delivery
            filled_forms = dict((xmlns, False) for xmlns in IMMUNIZATION_FORMS)
            all_forms_filled = True
            for form in case.get_forms():
                if form.xmlns in IMMUNIZATION_FORMS and (form.received_on.date() - date_delivery).days < 42:
                    filled_forms[form.xmlns] = True
            for key in filled_forms:
                if filled_forms.get(key, False) is False:
                    all_forms_filled = False
            if all_forms_filled:
                yield [case.modified_on.date(), 1]


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
