from datetime import date, timedelta, datetime
import re
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.standard.inspect import CaseDisplay
from casexml.apps.case.models import CommCareCase
from django.utils.translation import ugettext as _


def get_property(dict_obj, name):
    if name in dict_obj:
        return dict_obj[name]
    else:
        return "---"


class MCHDisplay(CaseDisplay):

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
    def village(self):
        return get_property(self.case, "village")


class MCHMotherDisplay(MCHDisplay):
    _asha_name = "---"
    _asha_number = "---"
    _awc_code_name = "---"
    _aww_name = "---"
    _aww_number = "---"

    _caste = "---"
    _jsy_beneficiary = "---"
    _home_sba_assist = "---"
    _delivery_nature = "---"
    _discharge_date = "---"
    _jsy_money_date = "---"
    _delivery_complications = "---"
    _family_planning_type = "---"
    _anemia = "---"
    _complications = "---"
    _rti_sti = "---"
    _abortion_type = "---"
    _blood_pressure_1 = "---"
    _blood_pressure_2 = "---"
    _blood_pressure_3 = "---"
    _blood_pressure_4 = "---"
    _weight_1 = "---"
    _weight_2 = "---"
    _weight_3 = "---"
    _weight_4 = "---"
    _hemoglobin = "---"
    _all_pnc_on_time = "---"
    _num_children = "---"
    _case_name_1 = "---"
    _case_name_2 = "---"
    _case_name_3 = "---"
    _case_name_4 = "---"
    _gender_1 = "---"
    _gender_2 = "---"
    _gender_3 = "---"
    _gender_4 = "---"
    _first_weight_1 = "---"
    _first_weight_2 = "---"
    _first_weight_3 = "---"
    _first_weight_4 = "---"
    _breastfed_hour_1 = "---"
    _breastfed_hour_2 = "---"
    _breastfed_hour_3 = "---"
    _breastfed_hour_4 = "---"

    def __init__(self, report, case_dict):
        case = CommCareCase.get(case_dict["_id"])
        forms = case.get_forms()

        for form in forms:
            form_dict = form.get_form
            form_xmlns = form_dict["@xmlns"]
            if re.search("new$", form_xmlns):
                self._caste = get_property(form_dict, "caste")
            elif re.search("del$", form_xmlns):
                self._jsy_beneficiary = get_property(form_dict, "jsy_beneficiary")
                self._home_sba_assist = get_property(form_dict, "home_sba_assist")
                self._delivery_nature = get_property(form_dict, "delivery_nature")
                self._discharge_date = get_property(form_dict, "discharge_date")
                self._jsy_money_date = get_property(form_dict, "jsy_money_date")
                self._delivery_complications = get_property(form_dict, "delivery_complications")
                self._family_planning_type = get_property(form_dict, "family_planing_type")
                self._all_pnc_on_time = get_property(form_dict, "all_pnc_on_time")
                children_count = get_property(form_dict, "cast_num_children")
                child_list = []

                if int(children_count) == 1 and "child_info" in form_dict:
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

            elif re.search("bp$", form_xmlns):
                if "bp1" in form_dict:
                    bp = form_dict["bp1"]
                    for i in range(1, 5):
                        if "anc%s" % i in bp:
                            anc = bp["anc%s" % i]
                            if "anc%s_blood_pressure" % i in anc:
                                setattr(self, "_blood_pressure_%s" % i, anc["anc%s_blood_pressure" % i])
                            if "anc%s_weight" % i in anc:
                                setattr(self, "_weight_%s" % i, anc["anc%s_weight" % i])
                            if "anc%s_hemoglobin" % i in anc and i == 1:
                                setattr(self, "_hemoglobin" % i, anc["anc%s_hemoglobin" % i])
                self._anemia = get_property(form_dict, "anemia")
                self._complications = get_property(form_dict, "bp_complications")
                self._rti_sti = get_property(form_dict, "rti_sti")
            elif re.search("mtb_abort$", form_xmlns):
                self._abortion_type = get_property(form_dict, "abortion_type")

        super(MCHMotherDisplay, self).__init__(report, case_dict)

    @property
    def chw_name(self):
        return self.owner_display

    @property
    def mcts_id(self):
        return get_property(self.case, "mcts_id")

    @property
    def mobile_number(self):
        return get_property(self.case, "mobile_number")

    @property
    def mobile_number_whose(self):
        return get_property(self.case, "mobile_number_whose")

    @property
    def dob_age(self):
        if "mother_dob" in self.case and self.case["mother_dob"]:
            mother_dob = self.case["mother_dob"]
            days = (date.today() - self.parse_date(mother_dob).date()).days
            return "%s, %s" % (mother_dob, days/365)
        else:
            return "---"

    @property
    def lmp(self):
        return get_property(self.case, "lmp")

    @property
    def edd(self):
        return get_property(self.case, "edd")

    @property
    def anc_date_1(self):
        return get_property(self.case, "anc_1_date")

    @property
    def anc_date_2(self):
        return get_property(self.case, "anc_2_date")

    @property
    def anc_date_3(self):
        return get_property(self.case, "anc_3_date")

    @property
    def anc_date_4(self):
        return get_property(self.case, "anc_4_date")

    @property
    def tt1_date(self):
        return get_property(self.case, "tt_1_date")

    @property
    def tt2_date(self):
        return get_property(self.case, "tt_2_date")

    @property
    def tt_booster(self):
        return get_property(self.case, "tt_booster")

    @property
    def ifa_tablets(self):
        return get_property(self.case, "ifa_tablets_100")

    @property
    def add(self):
        return get_property(self.case, "add")

    @property
    def first_pnc_time(self):
        return get_property(self.case, "first_pnc_time")

    @property
    def status(self):
        return get_property(self.case, "status")

    @property
    def asha_name(self):
        return self._asha_name

    @property
    def asha_number(self):
        return self._asha_number

    @property
    def awc_code_name(self):
        return self._awc_code_name

    @property
    def aww_name(self):
        return self._aww_name

    @property
    def aww_number(self):
        return self._aww_number


    @property
    def caste(self):
        return self._caste

    @property
    def jsy_beneficiary(self):
        return self._jsy_beneficiary

    @property
    def home_sba_assist(self):
        return self._home_sba_assist

    @property
    def delivery_nature(self):
        return self._delivery_nature

    @property
    def discharge_date(self):
        return self._discharge_date

    @property
    def jsy_money_date(self):
        return self._jsy_money_date

    @property
    def delivery_complications(self):
        return self._delivery_complications

    @property
    def family_planning_type(self):
        return self._family_planning_type

    @property
    def anemia(self):
        return self._anemia

    @property
    def complications(self):
        return self._complications

    @property
    def rti_sti(self):
        return self._rti_sti

    @property
    def abortion_type(self):
        return self._abortion_type

    @property
    def blood_pressure_1(self):
        return self._blood_pressure_1

    @property
    def blood_pressure_2(self):
        return self._blood_pressure_2

    @property
    def blood_pressure_3(self):
        return self._blood_pressure_3

    @property
    def blood_pressure_4(self):
        return self._blood_pressure_4

    @property
    def weight_1(self):
        return self._weight_1

    @property
    def weight_2(self):
        return self._weight_2

    @property
    def weight_3(self):
        return self._weight_3

    @property
    def weight_4(self):
        return self._weight_4

    @property
    def hemoglobin(self):
        return self._hemoglobin

    @property
    def anc_completed(self):
        lmp = self.lmp
        anc_date_1 = self.anc_date_1
        if lmp != "---" and anc_date_1 != "---":
            return _("yes") if self.parse_date(self.anc_date_1) < (self.parse_date(self.lmp) + timedelta(days=12*7)) else _("no")
        else:
            return "---"

    @property
    def all_pnc_on_time(self):
        return self._all_pnc_on_time

    @property
    def num_children(self):
        return self._num_children

    @property
    def case_name_1(self):
        return self._case_name_1

    @property
    def case_name_2(self):
        return self._case_name_2

    @property
    def case_name_3(self):
        return self._case_name_3

    @property
    def case_name_4(self):
        return self._case_name_4

    @property
    def gender_1(self):
        return self._gender_1

    @property
    def gender_2(self):
        return self._gender_2

    @property
    def gender_3(self):
        return self._gender_3

    @property
    def gender_4(self):
        return self._gender_4

    @property
    def first_weight_1(self):
        return self._first_weight_1

    @property
    def first_weight_2(self):
        return self._first_weight_2

    @property
    def first_weight_3(self):
        return self._first_weight_3

    @property
    def first_weight_4(self):
        return self._first_weight_4

    @property
    def breastfed_hour_1(self):
        return self._breastfed_hour_1

    @property
    def breastfed_hour_2(self):
        return self._breastfed_hour_2

    @property
    def breastfed_hour_3(self):
        return self._breastfed_hour_3

    @property
    def breastfed_hour_4(self):
        return self._breastfed_hour_4
