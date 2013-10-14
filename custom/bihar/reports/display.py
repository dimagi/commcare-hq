from datetime import date, timedelta
from mx.DateTime import today
from corehq.apps.reports.standard.inspect import CaseDisplay
from casexml.apps.case.models import CommCareCase
from django.utils.translation import ugettext as _


class MCHDisplay(CaseDisplay):

    def mother_name(self):
        if "mother_name" in self.case:
            return self.case["mother_name"]
        else:
            return "---"

    def husband_name(self):
        if "husband_name" in self.case:
            return self.case["husband_name"]
        else: 
            return "---"

    def ward_number(self):
        if "ward_number" in self.case:
            return self.case["ward_number"]
        else: 
            return "---"

    def village(self):
        if "village" in self.case:
            return self.case["village"]
        else: 
            return "---"

class MCHMotherDisplay(MCHDisplay):

    caste = ""

    def __init__(self, case_dict):
        print case_dict
        case = CommCareCase.get(case_dict["_id"])
        forms = case.get_forms()
        for form in forms:
            form_dict = form.get_form
            form_name = form_dict["@name"]
            if form_name is "New Beneficiary":
                self.caste = form_dict["caste"]
            elif form_name is "Delivery Update":
                self.jsy_beneficiary = form_dict["jsy_beneficiary"]
                self.home_sba_assist = form_dict["home_sba_assist"]
                self.delivery_nature = form_dict["delivery_nature"]
                self.discharge_date = form_dict["discharge_date"]
                self.jsy_money_date = form_dict["jsy_money_date"]
            elif form_name is "Birth Preparedness":
                self.anc_completed = "yes" if self.anc_date_1 < (self.lmp + timedelta(days=12*7)) else "no"
                if "bp1" in form_dict:
                    bp = form_dict["bp1"]
                    for i in range(1, 5):
                        if "anc%s" % i in bp:
                            anc = bp["anc%s" % i]
                            if "anc%s_blood_pressure" % i in anc:
                                setattr(self, "blood_pressure_%s" % i, anc["anc%s_blood_pressure" % i])
                            if "anc%s_weight" % i in anc:
                                setattr(self, "weight_%s" % i, anc["anc%s_weight" % i])
                            if "anc%s_hemoglobin" % i in anc and i == 1:
                                setattr(self, "hemoglobin" % i, anc["anc%s_hemoglobin" % i])
                self.anemia = form_dict["anemia"]
                self.complications = form_dict["bp_complications"]
                self.rti_sti = form_dict["rti_sti"]
            elif form_name is "MTB Abort":
                self.abortion_type = form_dict["abortion_type"]

        super(MCHMotherDisplay, self).__init__(self, case_dict)

    def mcts_id(self):
        if "mcts_id" in self.case:
            return self.case["mcts_id"]
        else:
            return "---"

    def mobile_number(self):
        if "mobile_number" in self.case:
            return self.case["mobile_number"]
        else: 
            return "---"

    def mobile_number_whose(self):
        if "mobile_number_whose" in self.case:
            return self.case["mobile_number_whose"]
        else:
            return "---"

    def dob_age(self):
        if "mother_dob" in self.case:
            mother_dob = self.case["mother_dob"]
            return "%s, %s" % (mother_dob, today() - self.parse_date(mother_dob) / 365)
        else:
            return "---"

    def lmp(self):
        if "lmp" in self.case:
            return self.parse_date(self.case["lmp"])
        else:
            return "---"

    def edd(self):
        if "edd" in self.case:
            return self.parse_date(self.case["edd"])
        else:
            return "---"

    def anc_date_1(self):
        if "anc_1_date" in self.case:
            return self.parse_date(self.case["anc_1_date"])
        else:
            return "---"

    def anc_date_2(self):
        if "anc_2_date" in self.case:
            return self.parse_date(self.case["anc_2_date"])
        else:
            return "---"

    def anc_date_3(self):
        if "anc_3_date" in self.case:
            return self.parse_date(self.case["anc_3_date"])
        else:
            return "---"

    def anc_date_4(self):
        if "anc_4_date" in self.case:
            return self.parse_date(self.case["anc_4_date"])
        else:
            return "---"

    def tt1_date(self):
        if "tt_1_date" in self.case:
            return self.case["tt_1_date"]
        else: 
            return "---"

    def tt2_date(self):
        if "tt_2_date" in self.case:
            return self.case["tt_2_date"]
        else: 
            return "---"

    def tt_booster(self):
        if "tt_booster" in self.case:
            return self.parse_date(self.case["tt_booster"])
        else:
            return "---"

    def ifa_tablets(self):
        if "ifa_tablets_100" in self.case:
            return self.parse_date(self.case["ifa_tablets_100"])
        else:
            return "---"

    def add(self):
        if "add" in self.case:
            return self.parse_date(self.case["add"])
        else:
            return "---"

    def first_pnc_time(self):
        if "first_pnc_time" in self.case:
            return self.case["first_pnc_time"]
        else:
            return "---"

    def status(self):
        if "status" in self.case:
            return self.case["status"]
        else:
            return "---"

