#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.template.loader import render_to_string
from datetime import datetime, timedelta
from apps.reports.models import Case
from apps.hq.utils import get_dates
import logging
import calendar
from phone.models import PhoneUserInfo
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

def ward_summary(request):
    '''Ward Summary Report'''
    context = {}
    year = datetime.now().date().year
    years = []
    for i in range(0, 5):
        years.append(year-i)
    context["years"] = years
    
    wards = []
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            additional_data = pui.additional_data
            if additional_data != None and "ward" in additional_data:
                ward = additional_data["ward"]
                if ward != None and not ward in wards:
                    wards.append(ward)
    if len(wards) == 0:
        return '''Sorry, it doesn't look like there are any wards.'''
    context["wards"] = wards
    return render_to_string("custom/pathfinder/select_info_ward_summary.html", context)

class WardSummaryData(object):
    '''Contains the information for one row within the ward summary report'''
    
    # initialize all the fields 
    case = None
    chw_id = None
    hcbpid = None
    chw_name = None
    region = None
    district = None
    ward = None
    new_plha_m = 0
    new_plha_f = 0
    new_cip_m = 0
    new_cip_f = 0
    existing_plha_m = 0
    existing_plha_f = 0
    existing_cip_m = 0
    existing_cip_f = 0
    adult_m = 0
    adult_f = 0
    child_m = 0
    child_f = 0
    death_plha_m = 0
    death_plha_f = 0
    death_cip_m = 0
    death_cip_f = 0
    transfer_plha_m = 0
    transfer_plha_f = 0
    transfer_cip_m = 0
    transfer_cip_f = 0
    ref_vct = 0
    ref_ois = 0
    ref_ctc = 0
    ref_pmtct = 0
    ref_fp = 0
    ref_sg = 0
    ref_tb = 0
    conf_ref = 0
    data = []
    data_counter = 0
    
    def __iter__(self):
        return self

    def next(self):
        if self.data_counter == len(self.data):
            raise StopIteration
        else:
            item = self.data[self.data_counter]
            self.data_counter += 1
            return item
    
    def __init__(self, case, chw_id, data_map, startdate, enddate):
        self.case = case
        self.chw_id = chw_id
        self.startdate = startdate
        self.enddate = enddate
        
        #add ward, district, region for this chw
        puis = PhoneUserInfo.objects.all()
        userinfo = None
        if puis != None:
            for pui in puis:
                if chw_id == pui.username + pui.phone.device_id:
                    userinfo = pui
        if userinfo != None:
            additional_data = userinfo.additional_data
            if additional_data != None:
                if "region" in additional_data:
                    self.region = additional_data["region"]
                if "ward" in additional_data:
                    self.ward = additional_data["ward"]
                if "district" in additional_data:
                    self.district = additional_data["district"]
                if "hcbpid" in additional_data:
                    self.hcbpid = additional_data["hcbpid"]
        
        # go through all of this chw's clients
        for client_id, client_data in data_map.items():
            # use form_type?
            [reg_forms, followup_forms, ref_forms] = [client_data[form] for 
                                                      form in 
                                                      case.form_identifiers]

            birthdate = datetime.date(datetime(1000, 01, 01))
            matching_reg_forms = []
            sex = None
            # collect reg_forms matching the correct dates
            # get general data like birthdate, sex, chw_name. location info
            for reg in reg_forms:
                date = reg[COLS["timeend"]]
                if date and date.date() >= startdate and date.date() \
                    < enddate:
                    matching_reg_forms.append(reg)
                birthdate = reg[COLS["dob"]]
                sex = reg[COLS["sex"]]
                if not self.chw_name and reg[COLS["username"]]:
                    self.chw_name = reg[COLS["username"]]
                elif self.chw_name and reg[COLS["username"]]:
                    if self.chw_name != reg[COLS["username"]]:
                        logging.debug("Warning, multiple ids found for %s: %s and %s" %\
                            (self.chw_id, self.chw_name, 
                             reg[COLS["username"]]))
                    
            # collect followup forms matching the correct dates
            matching_followups = []
            for follow in followup_forms:
                date = follow[COLS["timeend"]]
                if date and date.date() >= startdate and date.date() \
                    < enddate:
                    matching_followups.append(follow)
                # if there will always be a registration form, could leave this out
                if not self.chw_name and follow[COLS["username"]]:
                    self.chw_name = follow[COLS["username"]]
                elif self.chw_name and follow[COLS["username"]]:
                    if self.chw_name != follow[COLS["username"]]:
                        logging.debug("Warning, multiple ids found for %s: %s and %s" %\
                            (self.chw_id, self.chw_name, 
                             follow[COLS["username"]]))
            
            # collect resolved referral forms matching the correct dates
            matching_refs = []
            for ref in ref_forms:
                date = ref[COLS["timeend"]]
                if date and date.date() >= startdate and date.date() \
                    < enddate:
                    matching_refs.append(ref)
                # if there will always be a registration form, could leave this out
                if not self.chw_name and ref[COLS["username"]]:
                    self.chw_name = ref[COLS["username"]]
                elif self.chw_name and ref[COLS["username"]]:
                    if self.chw_name != ref[COLS["username"]]:
                        logging.debug("Warning, multiple ids found for %s: %s and %s" %\
                            (self.chw_id, self.chw_name, 
                             ref[COLS["username"]]))
                        
            # collect counts for new clients
            reg_form = None
            if matching_reg_forms:
                if len(matching_reg_forms)!= 1:
                    logging.debug("Warning, multiple registration forms found for %s" %\
                                  client_id)
                reg_form = matching_reg_forms[0]
                if reg_form[COLS["reg_hiv"]] == 1:
                    if sex == "m":
                        self.new_plha_m += 1
                    elif sex == "f":
                        self.new_plha_f += 1
                else:
                    if sex == "m":
                        self.new_cip_m += 1
                    elif sex == "f":
                        self.new_cip_f += 1
                        
            # collect counts for existing clients
            first_follow = None
            if matching_followups:
                # collect counts for existing, death, transfer and referral categories
                # a single client could have multiple counts for any of these if multiple
                # followup forms were submitted for them in the last month
                for followup in matching_followups:
                    type_of_client = followup[COLS["type_client"]] 
                    if type_of_client == "hiv":
                        if sex == "m":
                            self.existing_plha_m += 1
                        elif sex == "f":
                            self.existing_plha_f += 1
                    else:
                        if sex == "m":
                            self.existing_cip_m += 1
                        elif sex == "f":
                            self.existing_cip_f += 1
                            
                    why_missing = followup[COLS["status"]]
                    if why_missing == "dead":
                        if type_of_client == "hiv":
                            if sex == "m":
                                self.death_plha_m += 1
                            elif sex == "f":
                                self.death_plha_f += 1
                        else:
                            if sex == "m":
                                self.death_cip_m += 1
                            elif sex == "f":
                                self.death_cip_f += 1
                    elif why_missing == "transferred":
                        if type_of_client == "hiv":
                            if sex == "m":
                                self.transfer_plha_m += 1
                            elif sex == "f":
                                self.transfer_plha_f += 1
                        else:
                            if sex == "m":
                                self.transfer_cip_m += 1
                            elif sex == "f":
                                self.transfer_cip_f += 1
                    if followup[COLS["VCT"]] == 1:
                        self.ref_vct += 1
                    if followup[COLS["OIS"]] == 1:
                        self.ref_ois += 1
                    if followup[COLS["CTC"]] == 1:
                        self.ref_ctc += 1
                    if followup[COLS["PMTCT"]] == 1:
                        self.ref_pmtct += 1
                    if followup[COLS["FP"]] == 1:
                        self.ref_fp += 1
                    if followup[COLS["SG"]] == 1:
                        self.ref_sg += 1 
                    if followup[COLS["TB"]] == 1:
                        self.ref_tb += 1
            
            # Counts for confirmed referrals this month
            if matching_refs:
                for ref in matching_refs:
                    if ref[COLS["ref_done"]] == "yes":
                        self.conf_ref += 1
                        
            # Get counts of adults and children
            if reg_form != None or first_follow != None and birthdate > \
                datetime.date(datetime(1000, 01, 01)):
                # at least one form was submitted for this client this month
                age = enddate - birthdate
                years = age.days/365
                if years > 18:
                    if sex == "m":
                        self.adult_m += 1
                    elif sex == "f":
                        self.adult_f += 1
                else:
                    if sex == "m":
                        self.child_m += 1
                    elif sex == "f":
                        self.child_f += 1
                        
        self.data = [self.region, self.district, self.ward, self.chw_name, 
                     self.hcbpid, self.new_plha_m, self.new_plha_f, 
                     self.new_cip_m, self.new_cip_f, self.existing_plha_m,
                     self.existing_plha_f, self.existing_cip_m, 
                     self.existing_cip_f, self.adult_m, self.adult_f, 
                     self.child_m, self.child_f, self.death_plha_m,
                     self.death_plha_f, self.death_cip_m, self.death_cip_f,
                     self.transfer_plha_m, self.transfer_plha_f, 
                     self.transfer_cip_m, self.transfer_cip_f, self.ref_vct,
                     self.ref_ois, self.ref_ctc, self.ref_pmtct, self.ref_fp,
                     self.ref_sg, self.ref_tb, self.conf_ref]

def summary_by_provider_report(request):
    '''Summary by Provider Report'''
    context = {}
    wards = []
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            additional_data = pui.additional_data
            if additional_data != None and "ward" in additional_data:
                ward = additional_data["ward"]
                if ward != None and not ward in wards:
                    wards.append(ward)
    if len(wards) == 0:
        return '''Sorry, it doesn't look like there are any wards.'''
    context["wards"] = wards
    return render_to_string("custom/pathfinder/provider_select_ward.html", context)

class ProviderSummaryData(object):
    '''Contains the information for one row within the provider summary report'''
    
    # initialize all the fields 
    case = None
    client_id = None
    client_data = None
    startdate = None
    enddate = None
    patient_code = None
    age = 0
    sex = ""
    hbc_status = ""
    num_visits = 0
    hiv_status = ""
    functional_status = ""
    ctc_status = ""
    ctc_num = ""
    items_provided = ""
    services_provided = ""
    referrals_made = 0
    referrals_completed = 0
    data = []
    data_counter = 0
    
    def __iter__(self):
        return self

    def next(self):
        if self.data_counter == len(self.data):
            raise StopIteration
        else:
            item = self.data[self.data_counter]
            self.data_counter += 1
            return item
    
    def __init__(self, case, client_id, client_data, startdate, enddate):
        self.case = case
        self.client_id = client_id
        self.client_data = client_data
        self.startdate = startdate
        self.enddate = enddate
        # use form_type? 
        [reg_forms, followup_forms, ref_forms] = [client_data[form] for form 
                                                  in case.form_identifiers]
        for reg in reg_forms:
            date = reg[COLS["timeend"]]
            if date and date.date() >= startdate and date.date() < enddate:
                self.num_visits += 1
            diff = enddate - reg[COLS["dob"]]
            self.age = diff.days/365
            if reg[COLS["sex"]] == 'm':
                self.sex = "Male"
            elif reg[COLS["sex"]] == 'f':
                self.sex = "Female"
            self.patient_code = reg[COLS["patient_id"]]
            self.hiv_status = reg[COLS["hiv_status"]]
            self.ctc_num = reg[COLS["ctc_num"]]
        
        matching_follow_forms = []
        for follow in followup_forms:
            date = follow[COLS['timeend']]
            if date and date.date() >= startdate and date.date() < enddate:
                matching_follow_forms.append(follow)
        
        for ref in ref_forms:
            date = ref[COLS['timeend']]
            if date and date.date() >= startdate and date.date() < enddate:
                self.num_visits += 1
                if ref[COLS["ref_done"]] == "yes":
                        self.referrals_completed += 1
        
        for follow in matching_follow_forms:
            self.num_visits += 1
            self.hbc_status += follow[COLS['status']] +"; "
            self.functional_status += follow[COLS['func_status']] +"; "
            if follow[COLS['ctc_status']] == 'registered_no_arvs':
                self.ctc_status += 'registered no arvs; '
            if follow[COLS['ctc_status']] == 'registered_and_arvs':
                self.ctc_status += 'registered and arvs; '
            if follow[COLS['ctc_status']] == 'not_registered':
                self.ctc_status += 'not registered; '
            self.items_provided += follow[COLS['items']] +"; "
            if follow[COLS['services_nut']] == 1:
                self.services_provided += 'nutritional counselling; '
            if follow[COLS['services_infec']] == 1:
                self.services_provided += 'infectious education; '
            if follow[COLS['services_fp']] == 1:
                self.services_provided += 'family planning; '
            if follow[COLS['services_testing']] == 1:
                self.services_provided += 'testing; '
            if follow[COLS['services_counselling']] == 1:
                self.services_provided += 'counselling; '
            if follow[COLS['services_house']] == 1:
                self.services_provided += 'house; '
            if follow[COLS['services_health']] == 1:
                self.services_provided += 'health; '
            if follow[COLS['services_treatment']] == 1:
                self.services_provided += 'treatment; '
            if follow[COLS['services_delivery']] == 1:
                self.services_provided += 'delivery; '
            if follow[COLS['services_net']] == 1:
                self.services_provided += 'net; '
            if follow[COLS['services_std']] == 1:
                self.services_provided += 'std; '
            if follow[COLS['VCT']] == 1:
                self.referrals_made += 1
            if follow[COLS['OIS']] == 1:
                self.referrals_made +=1
            if follow[COLS['CTC']] == 1:
                self.referrals_made += 1
            if follow[COLS['PMTCT']] == 1:
                self.referrals_made +=1
            if follow[COLS['FP']] == 1:
                self.referrals_made += 1
            if follow[COLS['SG']] == 1:
                self.referrals_made +=1
            if follow[COLS['TB']] == 1:
                self.referrals_made += 1
        self.services_provided = self.services_provided.rsplit(';',1)[0]
        self.items_provided = self.items_provided.rsplit(';',1)[0]
        self.hbc_status = self.hbc_status.rsplit(';',1)[0]
        self.functional_status = self.functional_status.rsplit(';',1)[0]
        self.ctc_status = self.ctc_status.rsplit(';',1)[0]
        
        self.data = [self.patient_code, self.age, self.sex, self.hbc_status,
                     self.num_visits, self.hiv_status, self.functional_status,
                     self.ctc_status, self.ctc_num, self.items_provided, 
                     self.services_provided, self.referrals_made, 
                     self.referrals_completed]


def hbc_monthly_summary_report(request):
    '''Home based care monthly summary report'''
    context = {}
    year = datetime.now().date().year
    years = []
    for i in range(0, 5):
        years.append(year-i)
    context["years"] = years
    
    wards = []
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            additional_data = pui.additional_data
            if additional_data != None and "ward" in additional_data:
                ward = additional_data["ward"]
                if ward != None and not ward in wards:
                    wards.append(ward)
    if len(wards) == 0:
        return '''Sorry, it doesn't look like there are any wards.'''
    context["wards"] = wards
    return render_to_string("custom/pathfinder/select_info_hbc_summary.html", 
                            context)

class HBCMonthlySummaryData(object):
    '''Contains the information for one row within the provider summary report'''
    
    # initialize all the fields 
    case = None
    data_by_chw = None
    startdate = None
    enddate = None
    ward = None
    providers_reporting = 0
    providers_not_reporting = 0
    new_total_m = 0
    new_total_f = 0
    new_0_14_m = 0
    new_0_14_f = 0
    new_15_24_m = 0
    new_15_24_f = 0
    new_25_49_m = 0
    new_25_49_f = 0
    new_50_m = 0
    new_50_f = 0
    all_total_m = 0
    all_total_f = 0
    positive_m = 0
    positive_f = 0
    negative_m = 0
    negative_f = 0
    unknown_m = 0
    unknown_f = 0
    ctc_m = 0
    ctc_f = 0
    ctc_arv_m = 0
    ctc_arv_f = 0
    no_ctc_m = 0
    no_ctc_f = 0
    enrolled_m = 0
    enrolled_f = 0
    died = 0
    lost = 0
    transferred = 0
    migrated = 0
    no_need = 0
    opt_out = 0
    total_no_services = 0
    
    def __init__(self, case, data_by_chw, startdate, enddate, ward):
        self.case = case
        self.data_by_chw = data_by_chw
        self.startdate = startdate
        self.enddate = enddate
        self.ward = ward
        puis = PhoneUserInfo.objects.all()
        for chw_id, chw_data in data_by_chw.items():
            form_this_month = False
            in_ward = False
            if puis != None:
                for pui in puis:
                    if chw_id == pui.username + pui.phone.device_id:
                        ad_data = pui.additional_data
                        if ad_data != None and "ward" in ad_data and \
                            ad_data["ward"] == ward:
                            in_ward = True
            if in_ward:
                for client_data in chw_data.values():
                    # use form_type? 
                    [reg_forms, followup_forms, ref_forms] = [client_data[form] 
                                                              for form in 
                                                              case.form_identifiers]
                    sex = None
                    years = 0
                    client_new = False
                    client_new_cont = False
                    client_ever = False
                    match_reg_forms = []
                    for reg in reg_forms:
                        date = reg[COLS["timeend"]]
                        if date and date.date() >= startdate and date.date() \
                            < enddate:
                            match_reg_forms.append(reg)
                        sex = reg[COLS["sex"]]
                        diff = enddate - reg[COLS["dob"]]
                        years = diff.days/365
                    
                    match_follow_forms = []
                    for follow in followup_forms:
                        date = follow[COLS['timeend']]
                        if date and date.date() >= startdate and date.date() \
                            < enddate:
                            match_follow_forms.append(follow)
                    
                    match_ref_forms = []
                    for ref in ref_forms:
                        date = ref[COLS['timeend']]
                        if date and date.date() >= startdate and date.date() \
                            < enddate:
                            match_ref_forms.append(ref)
                    
                    if match_reg_forms or match_follow_forms or match_ref_forms:
                        form_this_month = True
                    
                    if match_reg_forms:
                        reg = match_reg_forms[0]
                        client_new = True
                        client_new_cont = True
                        client_ever = True
                        
                        # Count HIV status
                        hiv = reg[COLS['hiv_status']]
                        if hiv == 'Positive':
                            if sex == 'm':
                                self.positive_m += 1
                            elif sex == 'f':
                                self.positive_f += 1
                        elif hiv == 'Negative':
                            if sex == 'm':
                                self.negative_m += 1
                            elif sex == 'f':
                                self.negative_f += 1
                        elif hiv == 'Not_sure':
                            if sex == 'm':
                                self.unknown_m += 1
                            elif sex == 'f':
                                self.unknown_f += 1
    
                    ctc_no_arv = False
                    ctc_and_arv = False
                    no_ctc = False
                    lost = False
                    died = False
                    transferred = False
                    migrated = False
                    no_need = False
                    opted_out = False
                    if match_follow_forms:
                        for follow in match_follow_forms:
                            status = follow[COLS['status']]
                            if status == 'new':
                                client_new = True
                            if status  == 'new' or status == 'continuing':
                                client_new_cont = True
                            ctc = follow[COLS['ctc_status']]
                            if ctc == 'registered_no_arvs':
                                ctc_no_arv = True
                            elif ctc == 'registered_and_arvs':
                                ctc_and_arv = True
                            elif ctc == 'not_registered':
                                no_ctc = True
                            
                            if status == 'new' or status == 'continuing' or \
                                status == 'dead' or status == 'lost' or status ==\
                                'transferred' or status == 'migrated' or \
                                status == 'no_need' or status == 'opted_out':
                                client_ever = True
                            if status == 'dead':
                                died = True
                            if status == 'lost':
                                lost = True
                            if status == 'transferred':
                                transferred = True
                            if status == 'migrated':
                                migrated = True
                            if status == 'no_need':
                                no_need = True
                            if status == 'opted_out':
                                opted_out = True
                    
                    # Count all new clients enrolled this month
                    if client_new:
                        if sex == 'm':
                            self.new_total_m += 1
                            if years < 15:
                                self.new_0_14_m += 1
                            elif years < 25:
                                self.new_15_24_m += 1
                            elif years < 50:
                                self.new_25_49_m += 1
                            else:
                                self.new_50_m += 1
                        elif sex == 'f':
                            self.new_total_f += 1
                            if years < 15:
                                self.new_0_14_f += 1
                            elif years < 25:
                                self.new_15_24_f += 1
                            elif years < 50:
                                self.new_25_49_f += 1
                            else:
                                self.new_50_f += 1
                    
                    # Count all new or continuing clients            
                    if client_new_cont and sex == 'm':
                        self.all_total_m += 1
                    elif client_new_cont and sex == 'f':
                        self.all_total_f += 1
                    
                    # Count CTC enrollment status    
                    if ctc_no_arv and sex == 'm':
                        self.ctc_m += 1
                    elif ctc_no_arv and sex == 'f':
                        self.ctc_f += 1
                    elif ctc_and_arv and sex == 'm':
                        self.ctc_arv_m += 1
                    elif ctc_and_arv and sex == 'f':
                        self.ctc_arv_f += 1
                    elif no_ctc and sex == 'm':
                        self.no_ctc_m += 1
                    elif no_ctc and sex == 'f':
                        self.no_ctc_f += 1
                    
                    # Count all clients ever enrolled this month    
                    if client_ever and sex == 'm':
                        self.enrolled_m += 1
                    elif client_ever and sex == 'f':
                        self.enrolled_f += 1
                    
                    # Count clients no longer receiving services    
                    if died:
                        self.died += 1
                    if lost:
                        self.lost += 1
                    if transferred:
                        self.transferred += 1
                    if migrated:
                        self.migrated += 1
                    if no_need:
                        self.no_need += 1
                    if opted_out:
                        self.opt_out += 1
                
                # Count the number of providers reporting this month
                if form_this_month:
                    self.providers_reporting += 1
                else:
                    self.providers_not_reporting += 1
            
        self.total_no_services = self.died + self.lost + self.transferred + \
            self.migrated + self.no_need + self.opt_out
            
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

COLS = {"timeend":"meta_timeend", 
        "dob":"pathfinder_registration_patient_date_of_birth", 
        "sex":"pathfinder_registration_patient_sex", 
        "username":"meta_username", 
        "region":"pathfinder_registration_patient_region", #ask joachim -- definitely wrong
        "district":"pathfinder_registration_patient_district", #ask joachim -- definitely wrong
        "ward":"pathfinder_registration_patient_ward", #ask joachim -- definitely wrong
        "reg_hiv":"pathfinder_registration_patient_registration_cause_hiv", 
        "type_client":"pathfinder_followup_patient_type_of_client",
        "status":"pathfinder_followup_patient_registration_and_followup_hiv",
        "VCT":"pathfinder_followup_patient_referrals_hiv_counselling_and_testin",
        "OIS":"pathfinder_followup_patient_referrals_hiv_opportunistic_infectio", 
        "CTC":"pathfinder_followup_patient_referrals_hiv_referred_to_ctc", 
        "PMTCT":"pathfinder_followup_patient_referrals_hiv_pmtct", 
        "FP":"pathfinder_followup_patient_referrals_hiv_ref_fp", 
        "SG":"pathfinder_followup_patient_referrals_hiv_other_services", 
        "TB":"pathfinder_followup_patient_referrals_hiv_tb_clinic", 
        "ref_done":"pathfinder_referral_client_referral", 
        "patient_id":"pathfinder_registration_patient_patient_id",
        "hiv_status":"inder_registration_patient_hiv_status_during_registration",
        "func_status":"pathfinder_followup_patient_client_condition",
        "ctc_status":"pathfinder_followup_patient_ctc",
        "ctc_num":"pathfinder_registration_patient_number_given_at_ctc",
        "items":"pathfinder_followup_patient_medication_given",
        "services_nut":"pathfinder_followup_patient_services_given_nutritional_counselli",
        "services_infec":"pathfinder_followup_patient_services_given_infectious_education",
        "services_fp":"pathfinder_followup_patient_services_given_fp",
        "services_testing":"pathfinder_followup_patient_services_given_testing",
        "services_counselling":"pathfinder_followup_patient_services_given_counselling",
        "services_house":"pathfinder_followup_patient_services_given_house",
        "services_health":"pathfinder_followup_patient_services_given_health",
        "services_treatment":"pathfinder_followup_patient_services_given_treatment",
        "services_delivery":"pathfinder_followup_patient_services_given_safe_delivery",
        "services_net":"pathfinder_followup_patient_services_given_net",
        "services_std":"pathfinder_followup_patient_services_given_std"}