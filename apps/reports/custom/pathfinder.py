#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.template.loader import render_to_string
from datetime import datetime, timedelta
from apps.reports.models import Case
from apps.hq.utils import get_dates
import logging
'''Report file for custom Pathfinder reports'''
# see mvp.py for an explanation of how these are used.


def government(request):
    '''Government Report'''
    context = {}
    case_name = "Pathfinder CHBCP"
    startdate, enddate = get_dates(request, 30)
    maxrows = 10
    show_test = False
    if "showtest" in request.GET:
        show_test = True
    if "maxrows" in request.GET:
        try:
            maxrows = int(request.GET["maxrows"])
        except Exception:
            # just default to the above if we couldn't 
            # parse it
            pass
    if enddate < startdate:
        return '''<p><b><font color="red">The date range you selected is not valid.  
                  End date of %s must fall after start date of %s.</font></b></p>'''\
                  % (enddate, startdate)

    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    all_data = case.get_all_data_maps()
    # the case ids come back as chwid|case
    # we want to bucketize them by chw first
    data_by_chw = {}
    for id, map in all_data.items():
        chw_id = id.split("|")[0]
        if not chw_id in data_by_chw:
            data_by_chw[chw_id] = {}
        data_by_chw[chw_id][id] = map
    chw_data_list = []
    for chw_id, chw_data in data_by_chw.items():
        chw_obj = PathfinderCHWData(case, chw_id, chw_data, startdate, enddate)
        chw_data_list.append(chw_obj)
    context["all_data"] = chw_data_list[:maxrows]
    context["startdate"] = startdate
    context["enddate"] = enddate
    context["showtest"] = show_test
    # todo: stop hard coding these
    context["supervisor_name"] = "Neal Lesh"
    context["supervisor_code"] = 1234
    context["ward"] = "A Ward"
    context["district"] = "A District"
    return render_to_string("custom/pathfinder/government_report.html", context)

class PathfinderCHWData(object):
    '''Class to store all the data we need to access in a single
       row of the government report'''
    
    # initialize all the fields 
    case = None
    chw_id = None
    chw_name = None
    deaths = 0
    transfers = 0
    not_at_home = 0
    new_plha = 0
    new_chron = 0
    first_visit_plha = 0
    first_visit_chron = 0
    freq_visits_plha = 0
    freq_visits_chron = 0
    male = 0
    female = 0
    ref_vct = 0
    ref_oi = 0
    ref_ctc = 0
    ref_ctc_arv = 0
    ref_pmtct = 0
    ref_fp = 0
    ref_sg = 0
    ref_ovc = 0
    ref_tb = 0
    drug_counts = {}
    itns_waterguard_supplied = {}
    pcg_new_male = 0
    pcg_new_female = 0
    pcg_existing_male = 0
    pcg_existing_female = 0
    reg_forms = 0
    followup_forms = 0
    clients = 0
    reg_forms_in_period = 0
    followup_forms_in_period = 0
    clients_in_period = 0
    
    def __init__(self, case, chw_id, data_map, startdate, enddate):
        self.case = case
        self.chw_id = chw_id
        self.startdate = startdate
        self.enddate = enddate
        
        self.drug_counts = { 1:0, 2:0, 3:0, 4:0, 5:0, 6:0 }
        self.itns_waterguard_supplied = { 1:0, 2:0 }
        for client_id, client_data in data_map.items():
            self.clients += 1
            
            [reg_forms, followup_forms] =\
                [client_data[form] for form in case.form_identifiers]
            
            self.reg_forms += len(reg_forms)
            self.followup_forms += len(followup_forms)
            matching_reg_forms = []
            matching_followups = []
            # filter on dates, set usernames
            for reg in reg_forms:
                date = reg['meta_timeend']
                if date and date.date() >= startdate and date.date() <= enddate:
                    matching_reg_forms.append(reg)

                if not self.chw_name and reg["meta_username"]:
                    self.chw_name = reg["meta_username"]
                elif self.chw_name and reg["meta_username"]:
                    if self.chw_name != reg["meta_username"]:
                        logging.debug("Warning, multiple ids found for %s: %s and %s" %\
                            (self.chw_id, self.chw_name, reg["meta_username"]))
            for follow in followup_forms:
                date = follow['meta_timeend']
                if date and date.date() >= startdate and date.date() <= enddate:
                    matching_followups.append(follow)
            
                if not self.chw_name and follow["meta_username"]:
                    self.chw_name = follow["meta_username"]
                elif self.chw_name and follow["meta_username"]:
                    if self.chw_name != follow["meta_username"]:
                        logging.debug("Warning, multiple ids found for %s: %s and %s" %\
                            (self.chw_id, self.chw_name, follow["meta_username"]))

            self.reg_forms_in_period += len(matching_reg_forms)
            self.followup_forms_in_period += len(matching_followups)
            if matching_reg_forms or matching_followups:
                self.clients_in_period += 1

            reg_form = None
            if matching_reg_forms:
                if len(matching_reg_forms)!= 1:
                    logging.debug("Warning, multiple registration forms found for %s" %\
                                  client_id)
                reg_form = matching_reg_forms[0]
                status = reg_form["pathfinder_registration_patient_status"]
                if status == "People_living_with_HIV_(PLHA)":
                    self.new_plha += 1
                # should we explicitly check?  these could be empty
                #elif status == "Chronic_Ill":
                else:
                    self.new_chron += 1
                
                
                if reg_form["pathfinder_registration_patient_existing_female_pcg"]:
                    self.pcg_new_female += reg_form["pathfinder_registration_patient_existing_female_pcg"]
                if reg_form["pathfinder_registration_patient_existing_male_pcg"]:
                    self.pcg_new_male += reg_form["pathfinder_registration_patient_existing_male_pcg"]
                
            elif reg_forms:
                if len(reg_forms)!= 1:
                    logging.debug("Warning, multiple registration forms found for %s" %\
                                  client_id)
                reg_form = reg_forms[0]
            
            if matching_followups:
                first_followup = followup_forms[len(followup_forms)- 1]
                
                matching_follow = matching_followups[0]
                # use this one to do counts for pcgs
                if matching_follow["pathfinder_followup_new_male_pcg"]:
                    self.pcg_existing_male += matching_follow["pathfinder_followup_new_male_pcg"]
                if matching_follow["pathfinder_followup_existing_male_pcg"]:
                    self.pcg_existing_male += matching_follow["pathfinder_followup_existing_male_pcg"]
                if matching_follow["pathfinder_followup_new_female_pcg"]:
                    self.pcg_existing_female += matching_follow["pathfinder_followup_new_female_pcg"]
                if matching_follow["pathfinder_followup_existing_female_pcg"]:
                    self.pcg_existing_female += matching_follow["pathfinder_followup_existing_female_pcg"]
        
                count = 0
                if reg_form:
                    sex = reg_form["pathfinder_registration_patient_sex"]
                    if sex == "M":
                        self.male += 1
                    elif sex == "F":
                        self.female += 1
                for followup in matching_followups:
                    count += 1
                    counted_second_followup = False
                    type = followup["pathfinder_followup_type_of_client"]
                    if followup == first_followup:
                        # first followup ever, and it was in the report period
                        if type == "HIV":
                            self.first_visit_plha += 1
                        else:
                            self.first_visit_chron += 1
                    elif not counted_second_followup:
                        # second or later followup
                        if type == "HIV":
                            self.freq_visits_plha += 1
                        else:
                            self.freq_visits_chron += 1
                        counted_second_followup = True
                            
                    found_not_home = False
                    
                    # why missing?
                    why_missing = followup["pathfinder_followup_why_missing"]
                    if why_missing == "dead":
                        self.deaths += 1
                    elif why_missing == "moved":
                        self.transfers += 1
                    elif not found_not_home and why_missing == "not_home":
                        # only count the first instance of this
                        self.not_at_home += 1
                        found_not_home = True
                        
                    # referrals
                    for key, property_name in REFERRAL_MAPPING:
                        if follow[key]:
                            prev_val = getattr(self, property_name)
                            setattr(self, property_name, prev_val + 1)
                    
                    for key, code in MED_MAPPING:
                        if follow[key]:
                            self.drug_counts[code] += 1
                    
                    for key, code in WATER_ITN_MAPPING:
                        if follow[key]:
                            self.itns_waterguard_supplied[code] += 1
             
    
    def get_drug_counts_string(self):
        """Gets the drug counts as a displayable string, showing only
           those values with counts"""
        return self._get_map_string(self.drug_counts)
    
    def get_water_itn_counts_string(self):
        """Gets the water/itn counts as a displayable string, showing only
           those values with counts"""
        return self._get_map_string(self.itns_waterguard_supplied)
               
        
    def _get_map_string(self, dict, delim="<br>"):
        keys = dict.keys()
        keys.sort()
        vals = []
        for key in keys:
            if dict[key]:
                vals.append("%s=%s" % (key, dict[key]))
        return delim.join(vals)

# maps fields in the xform to properties on the model
REFERRAL_MAPPING = (("pathfinder_followup_referral_hiv_test", "ref_vct"),
                    ("pathfinder_followup_referral_hiv_other_illness", "ref_oi"),
                    ("pathfinder_followup_referral_health_facility", "ref_ctc"),
                    ("pathfinder_followup_referral_prevention_from_mother_to_child", "ref_pmtct"),
                    ("pathfinder_followup_referral_aid_from_other_groups", "ref_sg"),
                    ("pathfinder_followup_referral_family_planning", "ref_fp"),
                    ("pathfinder_followup_referral_tb", "ref_tb"),
                    ("pathfinder_followup_referral_ophans", "ref_ovc"))

# maps meds to their number codes
MED_MAPPING = (("pathfinder_followup_type_med_septrini", 1),
               ("pathfinder_followup_type_med_arv", 2),
               ("pathfinder_followup_type_med_anti_tb", 3),
               ("pathfinder_followup_type_med_kinga_ya_tb", 4),
               ("pathfinder_followup_type_med_local_medicine", 5),
               ("pathfinder_followup_type_med_other", 6))

# maps meds to their number codes
WATER_ITN_MAPPING = (("pathfinder_followup_mosquito_net", 1),
                     ("pathfinder_followup_water_guard", 2))
               