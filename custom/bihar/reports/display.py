from datetime import date, timedelta
import re
import dateutil
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from casexml.apps.case.models import CommCareCase
from django.utils.translation import ugettext as _
import logging
from custom.bihar.calculations.utils.xmlns import BP, NEW, MTB_ABORT, DELIVERY, REGISTRATION
from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.users.models import CommCareUser, CouchUser

EMPTY_FIELD = "---"

def get_property(dict_obj, name, default=None):
    if name in dict_obj:
        if type(dict_obj[name]) is dict:
            return dict_obj[name]["#value"]
        return dict_obj[name]
    else:
        return default if default is not None else EMPTY_FIELD


class MCHDisplay(CaseDisplay):

    def __init__(self, report, case):

        try:
            self.user = CommCareUser.get_by_user_id(case["user_id"])
            if self.user is None:
                self.user = CommCareUser.get_by_user_id(case["opened_by"])
        except CouchUser.AccountTypeError:
            # if we have web users submitting forms (e.g. via cloudcare) just don't bother
            # with the rest of this data.
            self.user = None

        if self.user:
            setattr(self, "_village", get_property(self.user.user_data, "village"))
            setattr(self, "_asha_name", self.user.full_name if get_property(self.user.user_data, "role").upper() == "ASHA" else get_property(self.user.user_data, "partner_name"))
            if get_property(self.user.user_data, "role").upper() == "ASHA":
                setattr(self, "_asha_number", self.user.default_phone_number if self.user.default_phone_number else EMPTY_FIELD)
            else:
                setattr(self, "_asha_number", get_property(self.user.user_data, "partner_phone"))

            setattr(self, "_awc_code_name", "%s, %s" % (get_property(self.user.user_data, "awc-code"), get_property(self.user.user_data, "village")))
            setattr(self, "_aww_name", self.user.full_name if get_property(self.user.user_data, "role").upper() == "AWW" else get_property(self.user.user_data, "partner_name"))

            if get_property(self.user.user_data, "role").upper() == "AWW":
                setattr(self, "_aww_number", self.user.phone_numbers[0] if len(self.user.phone_numbers) > 0 else EMPTY_FIELD)
            else:
                setattr(self, "_aww_number", get_property(self.user.user_data, "partner_phone"))

        super(MCHDisplay, self).__init__(report, case)

    @property
    def village(self):
        return getattr(self, "_village", EMPTY_FIELD)

    @property
    def asha_name(self):
        return getattr(self, "_asha_name", EMPTY_FIELD)

    @property
    def asha_number(self):
        return getattr(self, "_asha_number", EMPTY_FIELD)

    @property
    def awc_code_name(self):
        return getattr(self, "_awc_code_name", EMPTY_FIELD)

    @property
    def aww_name(self):
        return getattr(self, "_aww_name", EMPTY_FIELD)

    @property
    def aww_number(self):
        return getattr(self, "_aww_number", EMPTY_FIELD)

    @property
    def chw_name(self):
        if self.user:
            return "%s, \"%s\"" % (self.user.username, self.user.full_name)
        else:
            return _("Unknown user")

    @property
    def home_sba_assist(self):
        return getattr(self, "_home_sba_assist", EMPTY_FIELD)

    @property
    def caste(self):
        return getattr(self, "_caste", EMPTY_FIELD)

    def parse_date(self, date_string):
        if date_string != EMPTY_FIELD and date_string != '' and date_string is not None:
            try:
                return str(self.report.date_to_json(CaseDisplay.parse_date(self, date_string)))
            except AttributeError:
                return _("Bad date format!")
            except TypeError:
                return _("Bad date format!")
        else:
            return EMPTY_FIELD


class MCHMotherDisplay(MCHDisplay):

    def __init__(self, report, case_dict):
        case = CommCareCase.get(case_dict["_id"])
        forms = case.get_forms()

        jsy_beneficiary = None
        jsy_money = None

        for form in forms:
            form_dict = form.get_form
            form_xmlns = form_dict["@xmlns"]

            if NEW in form_xmlns:
                setattr(self, "_caste", get_property(form_dict, "caste"))
            elif DELIVERY in form_xmlns:
                setattr(self, "_home_sba_assist", get_property(form_dict, "home_sba_assist"))
                setattr(self, "_delivery_nature", get_property(form_dict, "delivery_nature"))
                setattr(self, "_discharge_date", get_property(form_dict, "discharge_date"))
                setattr(self, "_jsy_money_date", get_property(form_dict, "jsy_money_date"))
                setattr(self, "_delivery_complications", get_property(form_dict, "delivery_complications"))
                setattr(self, "_family_planning_type", get_property(form_dict, "family_planing_type"))
                setattr(self, "_all_pnc_on_time", get_property(form_dict, "all_pnc_on_time"))
                jsy_money = get_property(form_dict, "jsy_money")
                children_count = int(get_property(form_dict, "cast_num_children", 0))
                child_list = []
                if children_count == 1 and "child_info" in form_dict:
                    child_list.append(form_dict["child_info"])
                elif children_count > 1 and "child_info" in form_dict:
                    child_list = form_dict["child_info"]

                for idx,child in enumerate(child_list):
                    case_child = {}
                    if "case" in child:
                        case_child = CommCareCase.get(child["case"]["@case_id"])
                    setattr(self, "_first_weight_%s" % (idx+1), str(get_property(child, "first_weight")))
                    setattr(self, "_breastfed_hour_%s" % (idx+1), get_property(child, "breastfed_hour"))
                    if case_child:
                        setattr(self, "_case_name_%s" % (idx+1), get_property(case_child, "name"))
                        setattr(self, " _gender_%s" % (idx+1), get_property(case_child, "gender"))
            elif REGISTRATION in form_xmlns:
                jsy_beneficiary = get_property(form_dict, "jsy_beneficiary")

            elif BP in form_xmlns:
                if "bp1" in form_dict:
                    bp = form_dict["bp1"]
                    for i in range(1, 5):
                        if "anc%s" % i in bp:
                            anc = bp["anc%s" % i]
                            if "anc%s_blood_pressure" % i in anc:
                                setattr(self, "_blood_pressure_%s" % i, anc["anc%s_blood_pressure" % i])
                            if "anc%s_weight" % i in anc:
                                setattr(self, "_weight_%s" % i, str(anc["anc%s_weight" % i]))
                            if "anc%s_hemoglobin" % i in anc and i == 1:
                                setattr(self, "_hemoglobin", anc["anc%s_hemoglobin" % i])
                setattr(self, "_anemia", get_property(form_dict, "anemia"))
                setattr(self, "_complications", get_property(form_dict, "bp_complications"))
                setattr(self, "_rti_sti", get_property(form_dict, "rti_sti"))
            elif MTB_ABORT in form_xmlns:
                setattr(self, "_abortion_type", get_property(form_dict, "abortion_type"))

        if jsy_beneficiary is not None and jsy_beneficiary != EMPTY_FIELD:
            setattr(self, "_jsy_beneficiary", jsy_beneficiary)
        else:
            setattr(self, "_jsy_beneficiary", jsy_money)
        super(MCHMotherDisplay, self).__init__(report, case_dict)

    @property
    def mother_name(self):
        return get_property(self.case, "mother_name")

    @property
    def husband_name(self):
        return get_property(self.case, "husband_name")

    @property
    def ward_number(self):
        return get_property(self.case, "ward_number")

    @property
    def mobile_number(self):
        return get_property(self.case, "mobile_number")

    @property
    def mobile_number_whose(self):
        number = get_property(self.case, "mobile_number_whose")
        if re.match(r"^mobile_", number):
            r = re.compile(r"^mobile_", re.IGNORECASE)
            return r.sub("", number)
        else:
            return number

    @property
    def mcts_id(self):
        return get_property(self.case, "full_mcts_id")

    @property
    def dob_age(self):
        if "mother_dob" in self.case and self.case["mother_dob"]:
            try:
                mother_dob = self.case["mother_dob"]

                if type(mother_dob) is dict:
                    mother_dob = mother_dob["#value"]
                days = (date.today() - CaseDisplay.parse_date(self, mother_dob).date()).days
                mother_dob = self.parse_date(mother_dob)
                return "%s, %s" % (mother_dob, days/365)
            except AttributeError:
                return _("Bad date format!")
        else:
            return EMPTY_FIELD

    @property
    def lmp(self):
        return self.parse_date(get_property(self.case, "lmp"))

    @property
    def edd(self):
        return self.parse_date(get_property(self.case, "edd"))

    @property
    def anc_date_1(self):
        return self.parse_date(get_property(self.case, "anc_1_date"))

    @property
    def anc_date_2(self):
        return self.parse_date(get_property(self.case, "anc_2_date"))

    @property
    def anc_date_3(self):
        return self.parse_date(get_property(self.case, "anc_3_date"))

    @property
    def anc_date_4(self):
        return self.parse_date(get_property(self.case, "anc_4_date"))

    @property
    def tt1_date(self):
        return self.parse_date(get_property(self.case, "tt_1_date"))

    @property
    def tt2_date(self):
        return self.parse_date(get_property(self.case, "tt_2_date"))

    @property
    def tt_booster(self):
        return self.parse_date(get_property(self.case, "tt_booster"))

    @property
    def ifa_tablets(self):
        return self.parse_date(get_property(self.case, "ifa_tablets_100"))

    @property
    def add(self):
        return self.parse_date(get_property(self.case, "add"))

    @property
    def first_pnc_time(self):
        return get_property(self.case, "first_pnc_time")

    @property
    def status(self):
        return get_property(self.case, "status")

    @property
    def jsy_beneficiary(self):
        return getattr(self, "_jsy_beneficiary", EMPTY_FIELD)

    @property
    def delivery_nature(self):
        return getattr(self, "_delivery_nature", EMPTY_FIELD)

    @property
    def discharge_date(self):
        return getattr(self, "_discharge_date", EMPTY_FIELD)

    @property
    def jsy_money_date(self):
        return getattr(self, "_jsy_money_date", EMPTY_FIELD)

    @property
    def delivery_complications(self):
        return getattr(self, "_delivery_complications", EMPTY_FIELD)

    @property
    def family_planning_type(self):
        return getattr(self, "_family_planning_type", EMPTY_FIELD)

    @property
    def anemia(self):
        return getattr(self, "_anemia", EMPTY_FIELD)

    @property
    def complications(self):
        return getattr(self, "_complications", EMPTY_FIELD)

    @property
    def rti_sti(self):
        return getattr(self, "_rti_sti", EMPTY_FIELD)

    @property
    def abortion_type(self):
        return getattr(self, "_abortion_type", EMPTY_FIELD)

    @property
    def blood_pressure_1(self):
        return getattr(self, "_blood_pressure_1", EMPTY_FIELD)

    @property
    def blood_pressure_2(self):
        return getattr(self, "_blood_pressure_2", EMPTY_FIELD)

    @property
    def blood_pressure_3(self):
        return getattr(self, "_blood_pressure_3", EMPTY_FIELD)

    @property
    def blood_pressure_4(self):
        return getattr(self, "_blood_pressure_4", EMPTY_FIELD)

    @property
    def weight_1(self):
        return getattr(self, "_weight_1", EMPTY_FIELD)

    @property
    def weight_2(self):
        return getattr(self, "_weight_2", EMPTY_FIELD)

    @property
    def weight_3(self):
        return getattr(self, "_weight_3", EMPTY_FIELD)

    @property
    def weight_4(self):
        return getattr(self, "_weight_4", EMPTY_FIELD)

    @property
    def hemoglobin(self):
        return getattr(self, "_hemoglobin", EMPTY_FIELD)

    @property
    def anc_completed(self):
        lmp = self.lmp
        anc_date_1 = self.anc_date_1
        if lmp != EMPTY_FIELD and anc_date_1 != EMPTY_FIELD:
            try:
                return _("yes") if CaseDisplay.parse_date(self, self.anc_date_1) < (CaseDisplay.parse_date(self, self.lmp) + timedelta(days=12*7)) else _("no")
            except AttributeError:
                return _("Bad date format!")
        else:
            return EMPTY_FIELD

    @property
    def all_pnc_on_time(self):
        return getattr(self, "_all_pnc_on_time", EMPTY_FIELD)

    @property
    def num_children(self):
        return getattr(self, "_num_children", EMPTY_FIELD)

    @property
    def case_name_1(self):
        return getattr(self, "_case_name_1", EMPTY_FIELD)

    @property
    def case_name_2(self):
        return getattr(self, "_case_name_2", EMPTY_FIELD)

    @property
    def case_name_3(self):
        return getattr(self, "_case_name_3", EMPTY_FIELD)

    @property
    def case_name_4(self):
        return getattr(self, "_case_name_4", EMPTY_FIELD)

    @property
    def gender_1(self):
        return getattr(self, "_gender_1", EMPTY_FIELD)

    @property
    def gender_2(self):
        return getattr(self, "_gender_2", EMPTY_FIELD)

    @property
    def gender_3(self):
        return getattr(self, "_gender_3", EMPTY_FIELD)

    @property
    def gender_4(self):
        return getattr(self, "_gender_4", EMPTY_FIELD)

    @property
    def first_weight_1(self):
        return getattr(self, "_first_weight_1", EMPTY_FIELD)

    @property
    def first_weight_2(self):
        return getattr(self, "_first_weight_2", EMPTY_FIELD)

    @property
    def first_weight_3(self):
        return getattr(self, "_first_weight_3", EMPTY_FIELD)

    @property
    def first_weight_4(self):
        return getattr(self, "_first_weight_4", EMPTY_FIELD)

    @property
    def breastfed_hour_1(self):
        return getattr(self, "_breastfed_hour_1", EMPTY_FIELD)

    @property
    def breastfed_hour_2(self):
        return getattr(self, "_breastfed_hour_2", EMPTY_FIELD)

    @property
    def breastfed_hour_3(self):
        return getattr(self, "_breastfed_hour_3", EMPTY_FIELD)

    @property
    def breastfed_hour_4(self):
        return getattr(self, "_breastfed_hour_4", EMPTY_FIELD)


class MCHChildDisplay(MCHDisplay):
    def __init__(self, report, case_dict):

        # get mother case
        if len(case_dict["indices"]) > 0:
            try:
                parent_case = CommCareCase.get(case_dict["indices"][0]["referenced_id"])
                forms = parent_case.get_forms()

                parent_json = parent_case.case_properties()

                setattr(self, "_father_mother_name", "%s, %s" %(get_property(parent_json,"husband_name"), get_property(parent_json, "mother_name")))
                setattr(self, "_full_mcts_id", get_property(parent_json, "full_mcts_id"))
                setattr(self, "_ward_number", get_property(parent_json, "ward_number"))
                setattr(self, "_mobile_number", get_property(parent_case, 'mobile_number'))

                number = get_property(parent_case, "mobile_number_whose")
                if re.match(r"^mobile_", number):
                    r = re.compile(r"^mobile_", re.IGNORECASE)
                    setattr(self, "_mobile_number_whose", r.sub("", number))
                else:
                    setattr(self, "_mobile_number_whose", number)

                for form in forms:
                    form_dict = form.get_form
                    form_xmlns = form_dict["@xmlns"]

                    if NEW in form_xmlns:
                        setattr(self, "_caste", get_property(form_dict, "caste"))
                    elif DELIVERY in form_xmlns:
                        setattr(self, "_home_sba_assist", get_property(form_dict, "home_sba_assist"))

            except ResourceNotFound:
                logging.error("ResourceNotFound: " + case_dict["indices"][0]["referenced_id"])

        super(MCHChildDisplay, self).__init__(report, case_dict)

    @property
    def child_name(self):
        return get_property(self.case, "name")

    @property
    def father_mother_name(self):
        return getattr(self, "_father_mother_name", EMPTY_FIELD)

    @property
    def mcts_id(self):
        return getattr(self, "_full_mcts_id", EMPTY_FIELD)

    @property
    def ward_number(self):
        return getattr(self, "_ward_number", EMPTY_FIELD)

    @property
    def gender(self):
        return get_property(self.case, "gender")

    @property
    def mobile_number(self):
        return getattr(self, "_mobile_number", EMPTY_FIELD)

    @property
    def mobile_number_whose(self):
        return getattr(self, "_mobile_number_whose", EMPTY_FIELD)

    @property
    def bcg_date(self):
        return self.parse_date(get_property(self.case, "bcg_date"))

    @property
    def opv_0_date(self):
        return self.parse_date(get_property(self.case, "opv_0_date"))

    @property
    def hep_b_0_date(self):
        return self.parse_date(get_property(self.case, "hep_b_0_date"))

    @property
    def dpt_1_date(self):
        return self.parse_date(get_property(self.case, "dpt_1_date"))

    @property
    def opv_1_date(self):
        return self.parse_date(get_property(self.case, "opv_1_date"))

    @property
    def hep_b_1_date(self):
        return self.parse_date(get_property(self.case, "hep_b_1_date"))

    @property
    def dpt_2_date(self):
        return self.parse_date(get_property(self.case, "dpt_2_date"))

    @property
    def opv_2_date(self):
        return self.parse_date(get_property(self.case, "opv_2_date"))

    @property
    def hep_b_2_date(self):
        return self.parse_date(get_property(self.case, "hep_b_2_date"))

    @property
    def dpt_3_date(self):
        return self.parse_date(get_property(self.case, "dpt_3_date"))

    @property
    def opv_3_date(self):
        return self.parse_date(get_property(self.case, "opv_3_date"))

    @property
    def hep_b_3_date(self):
        return self.parse_date(get_property(self.case, "hep_b_3_date"))

    @property
    def measles_date(self):
        return self.parse_date(get_property(self.case, "measles_date"))

    @property
    def vit_a_1_date(self):
        return self.parse_date(get_property(self.case, "vit_a_1_date"))

    @property
    def date_measles_booster(self):
        return self.parse_date(get_property(self.case, "date_measles_booster"))

    @property
    def dpt_booster_date(self):
        return self.parse_date(get_property(self.case, "dpt_booster_date"))

    @property
    def opv_booster_date(self):
        return self.parse_date(get_property(self.case, "opv_booster_date"))

    @property
    def vit_a_2_date(self):
        return self.parse_date(get_property(self.case, "vit_a_2_date"))

    @property
    def vit_a_3_date(self):
        return self.parse_date(get_property(self.case, "vit_a_3_date"))

    @property
    def date_je(self):
        return self.parse_date(get_property(self.case, "date_je"))

    @property
    def dob_age(self):
        if "dob" in self.case and self.case["dob"]:
            try:
                dob = self.case["dob"]

                if type(dob) is dict:
                    dob = dob["#value"]
                days = (date.today() - CaseDisplay.parse_date(self, dob).date()).days
                dob = self.parse_date(dob)
                return "%s, %s" % (dob, int(days/365.25))
            except AttributeError:
                return _("Bad date format!")
        else:
            return EMPTY_FIELD
