#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from rapidsms.webui.utils import render_to_response
from django.http import HttpResponse
from django.template.loader import render_to_string
from xformmanager.models import Case
from datetime import datetime, date, timedelta

'''Define custom reports in this file.  The rules are one module per
   domain and the module name must match _lowercase_ the domain name.  
   Each function in the module will then be listed as a custom report
   that should return html formatted text that will be displayed
   as the report. The doc string of the method is what will be 
   displayed in the UI (self documentation!).'''
   # This is still a bit of a work in progress.  

def monitoring(request):
    '''Safe Pregnancy Monitoring Report'''
    context = { }
    # use the cases we've put together for this
    safe_preg_case_name = "MVP Safe Pregnancies"
    try:
        case = Case.objects.get(name=safe_preg_case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    data_maps = case.get_all_data_maps()
    
    # allow a list of usernames whose submissions don't show up
    # in the report. 
    blacklist = ["teddy", "admin", "demo_user"]
    blacklist_columns = ["meta_username_1","meta_username_2",
                         "meta_username_3","meta_username_4",
                         "meta_username_5"]
        
    all_moms = []
    healthy_moms = []
    very_pregnant_moms = []
    moms_needing_followup = []
    moms_with_open_referrals = []
    for id, map in data_maps.items():
        # check blacklist
        if _is_blacklisted(map, blacklist, blacklist_columns):
            continue
        mom = Mother(id, map)
        if not mom.chw:
            # don't include submissions from non-users
            continue
        all_moms.append(mom)
        prev_list_size = len(moms_needing_followup) +\
                         len(very_pregnant_moms) +\
                         len(moms_with_open_referrals)
        if mom.needs_followup:
            moms_needing_followup.append(mom)
        if mom.months_pregnant >= 7:
            very_pregnant_moms.append(mom)
        if mom.has_open_referral:
            moms_with_open_referrals.append(mom)
        new_list_size = len(moms_needing_followup) +\
                        len(very_pregnant_moms) +\
                        len(moms_with_open_referrals)
        if new_list_size == prev_list_size:
            # we didn't add her to any lists so put her in
            # healthy moms
            healthy_moms.append(mom) 
        
        
        
    context["all_moms"] = all_moms
    context["healthy_moms"] = healthy_moms
    context["open_referrals"] = moms_with_open_referrals
    context["very_pregnant"] = very_pregnant_moms
    context["need_followup"] = moms_needing_followup
    context["empty_data_holder"] = "<b>???</b>"
    return render_to_string("reports/mvp/monitoring.html", context)

def _is_blacklisted(data, blacklist, blacklist_columns):
    '''Checks a set of columns and values, and if any of the
       columns contains one of the values, returns true'''
    for column in blacklist_columns:
        if data[column] in blacklist:
            return True
    return False

class Mother(object):
    
    def __init__(self, id, data_map):
        self.id = id
        self.data_map = data_map 
        # calculate some properties and set them for easy access
        # these are totally hard coded to the forms.  
        # most of these depend on registration and will not display
        # very well if there is no registration
        
        # czue - i don't like that the sequence ids are hard-coded, but using the form
        # ids would just be way too long.  we could key these again by form, but
        # leaving that as an open-ended possibility.  a triple dictionary might
        # be a bit too much to deal with.
        
        # check against the old registration form
        reg_seq = "1"
        if not data_map["meta_timestart_1"] and data_map["meta_timestart_5"]:
            # we found an old reg and no new reg
            reg_seq = "5"
        
        self.mother_name = data_map["sampledata_mother_name_%s" % reg_seq]
        chw_cols = ["meta_username_1","meta_username_2","meta_username_3",
                    "meta_username_4", "meta_username_5"]
        
        self.chw = None
        for item in chw_cols:
            self.chw = data_map[item]
            if self.chw:
                break
            
        self.date_of_reg = data_map["meta_timestart_%s" % reg_seq]
        self.months_preg_at_reg = data_map["sampledata_months_pregnant_%s" % reg_seq]
        if self.date_of_reg and self.months_preg_at_reg:
            days_pregnant_at_reg = self.months_preg_at_reg * 30
            self.months_pregnant = ((datetime.now() - self.date_of_reg) + 
                                    timedelta(days=days_pregnant_at_reg)).days / 30
        else:
            self.months_pregnant = None
        
        # Women Needing Followup 
        # > 1 month since last Followup if 1-6 Months, 
        # > 15 days since last Followup if 7-10 Months
        self.date_of_last_followup = data_map["meta_timestart_2"] 
        if self.date_of_last_followup:
            self.days_since_followup = (datetime.now() - self.date_of_last_followup).days
        # this is yucky but we don't want to include folks with no followups
        # and no new reg, since we're not checkign the old followups
        elif self.date_of_reg and reg_seq == "1":   
            self.days_since_followup = (datetime.now() - self.date_of_reg).days
        else:
            # no reg or follow-ups.  leave them out for now
            self.days_since_followup = None
            self.needs_followup = False
        if self.days_since_followup is not None:
            if self.days_since_followup > 30:
                self.needs_followup = True
            elif self.days_since_followup > 15 and\
                 self.months_pregnant and self.months_pregnant >= 7:
                self.needs_followup = True
            else:
                self.needs_followup = False
        
        # high risk factors
        hi_risk_cols = ["sampledata_hi_risk_info_old_%s" % reg_seq,
                        "sampledata_hi_risk_info_young_%s" % reg_seq,
                        "sampledata_hi_risk_info_education_%s" % reg_seq,
                        "sampledata_hi_risk_info_small_%s" % reg_seq,
                        "sampledata_hi_risk_info_10_years_%s" % reg_seq,
                        "sampledata_hi_risk_info_complications_%s" % reg_seq,
                        "sampledata_hi_risk_info_many_%s" % reg_seq,
                        "sampledata_hi_risk_info_health_%s" % reg_seq,
                        "sampledata_hi_risk_info_hiv_%s" % reg_seq,
                        "sampledata_hi_risk_info_syphilis_%s" % reg_seq]
        hi_risk_values = []
        for col in hi_risk_cols:
            if data_map[col]:
                risk_factor = self._clean(col, "sampledata_hi_risk_info_", "_%s" % reg_seq)
                hi_risk_values.append(risk_factor)
        self.high_risk_factors = ",".join(hi_risk_values)
        
        # referral
        self.date_referred = datetime.min
        self.most_recent_referral_id = None
        self.has_referral = False
        if data_map["safe_pregnancy_referred_2"] and\
           data_map["safe_pregnancy_referred_2"] == "yes":
            self.has_referral = True
            self.date_referred = self.date_of_last_followup
            self.most_recent_referral_id = data_map["safe_pregnancy_referral_id_2"]
        if data_map["safe_pregnancy_referred_3"] and\
           data_map["safe_pregnancy_referred_3"] == "yes":
            self.has_referral = True
            self.date_of_closure = data_map["meta_timestart_3"] 
            self.date_referred = max([self.date_referred,
                                      self.date_of_closure])
            if self.date_of_closure == self.date_referred:
                self.most_recent_referral_id = data_map["safe_pregnancy_referral_id_2"]
        
        if data_map["meta_timestart_4"]:
            # we found a referral
            self.date_of_referral = data_map["meta_timestart_4"]
            if data_map["safe_pregnancy_visited_clinic_4"] != "yes":
                # the referral is open no matter what if the referral 
                # is present but not completed
                self.has_open_referral = True
            elif self.date_of_referral > self.date_referred:
                # they completed it.  
                self.has_open_referral = False
            else:
                # they closed a referral but have a more recent one 
                # that's still open
                self.has_open_referral = True
        else:
            # no information about a referral.  if there was one it's open
            self.has_open_referral = self.has_referral
                    
        # danger signs
        # Followup form is referred:
        # if(/safe_pregnancy/feeling='not_well'
        # or /safe_pregnancy/pain_from_vagina='yes'
        # or /safe_pregnancy/headache_or_b_vision='yes'
        # or /safe_pregnancy/dark_urine='yes'
        # or /safe_pregnancy/swelling='yes'
        # or /safe_pregnancy/unusual_pain='yes'
        # or /safe_pregnancy/burn_urinate='yes'
        # or /safe_pregnancy/baby_not_moving='yes'
        # or /safe_pregnancy/fever='yes'
        # or /safe_pregnancy/other_illness='yes')
        followup_warnings = {"safe_pregnancy_feeling_2" : "not_well", 
                             "safe_pregnancy_pain_from_vagina_2": "yes",
                             "safe_pregnancy_headache_or_b_vision_2": "yes",
                             "safe_pregnancy_dark_urine_2": "yes",
                             "safe_pregnancy_swelling_2": "yes",
                             "safe_pregnancy_unusual_pain_2": "yes",
                             "safe_pregnancy_burn_urinate_2": "yes",
                             "safe_pregnancy_baby_not_moving_2": "yes",
                             "safe_pregnancy_fever_2": "yes",
                             "safe_pregnancy_other_illness_2" : "yes"}
        
        danger_signs = []
        for key, value in followup_warnings.items():
             if data_map[key] == value:
                 danger_signs.append("%s: %s" % (self._clean(key, "safe_pregnancy_", "_2"),
                                                 self._clean(value, "", "")))
        
        # Close form is referred:
        # if(/safe_pregnancy/mother_survived='yes' and 
        # (( /safe_pregnancy/why_not='skeptical_clinic' 
        #    or /safe_pregnancy/why_not='busy' 
        #    or /safe_pregnancy/why_not='transport' 
        #    or /safe_pregnancy/why_not='other') 
        #    or (/safe_pregnancy/treatment_why_not='no_medicine' 
        #    or /safe_pregnancy/treatment_why_not='too_many_patients' 
        #    or /safe_pregnancy/treatment_why_not='no_doctor' 
        #    or /safe_pregnancy/treatment_why_not='no_health_workers' 
        #    or /safe_pregnancy/treatment_why_not='other')))
        
        if data_map["safe_pregnancy_mother_survived_3"] == "yes":
            closure_warnings = {
                                "safe_pregnancy_why_not_3" : 'skeptical_clinic',
                                "safe_pregnancy_why_not_3" : 'busy',
                                "safe_pregnancy_why_not_3" : 'transport',
                                "safe_pregnancy_why_not_3" : 'other',
                                "safe_pregnancy_treatment_why_not_3" : 'no_medicine',
                                "safe_pregnancy_treatment_why_not_3" : 'too_many_patients',
                                "safe_pregnancy_treatment_why_not_3" : 'no_doctor',
                                "safe_pregnancy_treatment_why_not_3" : 'no_health_workers',
                                "safe_pregnancy_treatment_why_not_3" : 'other'
                                }
            for key, value in closure_warnings.items():
                 if data_map[key] == value:
                     danger_signs.append("%s: %s" % (self._clean(key, "safe_pregnancy_", "_3"),
                                                     self._clean(value, "", "")))
            
        self.danger_signs = ", ".join(danger_signs)
        
        # checklist
        checklist_items = ["safe_pregnancy_preg_actions_iron_folic_2",
                           "safe_pregnancy_preg_actions_start_tt_2",
                           "safe_pregnancy_preg_actions_finish_tt_2",
                           "safe_pregnancy_preg_actions_start_ipt_2",
                           "safe_pregnancy_preg_actions_finish_ipt_2",
                           "safe_pregnancy_preg_actions_deworm_2",
                           "safe_pregnancy_preg_actions_birth_plan_2",
                           "safe_pregnancy_preg_actions_test_hiv_2",
                           "safe_pregnancy_preg_actions_test_syphilis_2",
                           "safe_pregnancy_preg_actions_test_bp_2",
                           "safe_pregnancy_preg_actions_test_hb_2"]
        
        incomplete_checklist_items = []
        for item in checklist_items:
            if data_map[item] != 1:
                incomplete_checklist_items.append(self._clean(item, "safe_pregnancy_preg_actions_", "_2"))
                
        self.incomplete_checklist_items = ", ".join(incomplete_checklist_items)
                           
                                 
        
    def _clean(self, column, prefix, suffix):
        '''Cleans a column by removing a prefix and suffix, if they
           are present, and converting underscores to spaces.'''
        if column.startswith(prefix):
            column = column[len(prefix):]
        if column.endswith(suffix):
            column = column[0:len(column) - len(suffix)]
        return column.replace("_", " ")