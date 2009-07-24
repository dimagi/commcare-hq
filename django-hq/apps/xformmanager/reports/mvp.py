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
    blacklist_columns = ["meta_username"]
    
    final_list_of_maps = {}
    # do a once-through pruning by the blacklist, and reclassifying by 
    # both chw id and case id
    for id, map in data_maps.items():
        for form, list_of_forms in map.items():
            for form_instance in list_of_forms:
                # check blacklist and don't use this instance if it's in 
                # the blacklist
                if _is_blacklisted(form_instance, blacklist, blacklist_columns):
                    continue
                # make a new id that includes the 
                new_id = "%s-%s" % (form_instance["meta_username"], id) 
                if new_id not in final_list_of_maps:
                    # initialize the new id with an empty list for each form
                    this_id_map = {}
                    for form_all in map:
                        this_id_map[form_all] = []
                    final_list_of_maps[new_id] = this_id_map
                final_list_of_maps[new_id][form].append(form_instance)

    all_moms = []
    healthy_moms = []
    very_pregnant_moms = []
    moms_needing_followup = []
    moms_with_open_referrals = []
    for id, map in final_list_of_maps.items():
        mom = Mother(case, id, map)
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
    context["empty_data_holder"] = "<b></b>"
    return render_to_string("reports/mvp/monitoring.html", context)

def _is_blacklisted(data, blacklist, blacklist_columns):
    '''Checks a set of columns and values, and if any of the
       columns contains one of the values, returns true'''
    for column in blacklist_columns:
        if column in data and\
           data[column] in blacklist:
            return True
    return False

class Mother(object):
    
    def __init__(self, case, id, data_map):
        self.case = case
        self.id = id
        self.data_map = data_map 
        # calculate some properties and set them for easy access
        # these are totally hard coded to the forms.  
        # most of these depend on registration and will not display
        # very well if there is no registration
        forms = case.form_identifiers
        [new_reg_forms, followup_forms, close_forms, referrals, old_reg_forms] =\
            [data_map[form] for form in forms]
        
        # check against the new and old registration form, in that order
        if new_reg_forms:
            reg_form_data = new_reg_forms[0]
        elif old_reg_forms:
            reg_form_data = old_reg_forms[0]
        else:
            reg_form_data = None
            
        # set the registration data, if present
        if reg_form_data: 
            self.mother_name = reg_form_data["sampledata_mother_name"]
            self.date_of_reg = reg_form_data["meta_timestart"]
            self.months_preg_at_reg = reg_form_data["sampledata_months_pregnant"]
            if self.date_of_reg and self.months_preg_at_reg:
                days_pregnant_at_reg = self.months_preg_at_reg * 30
                self.months_pregnant = ((datetime.now() - self.date_of_reg) + 
                                        timedelta(days=days_pregnant_at_reg)).days / 30
            else:
                self.months_pregnant = None
            # high risk factors
            hi_risk_cols = ["sampledata_hi_risk_info_old",
                            "sampledata_hi_risk_info_young",
                            "sampledata_hi_risk_info_education",
                            "sampledata_hi_risk_info_small",
                            "sampledata_hi_risk_info_10_years",
                            "sampledata_hi_risk_info_complications",
                            "sampledata_hi_risk_info_many",
                            "sampledata_hi_risk_info_health",
                            "sampledata_hi_risk_info_hiv",
                            "sampledata_hi_risk_info_syphilis"]
            hi_risk_values = []
            for col in hi_risk_cols:
                if reg_form_data[col]:
                    risk_factor = self._clean(col, "sampledata_hi_risk_info_", "")
                    hi_risk_values.append(risk_factor)
            self.high_risk_factors = ",".join(hi_risk_values)
        else:
            self.months_pregnant = None
        chw_col = "meta_username"
        # loop through all forms searching for this.
        self.chw = None
        for form in forms:
            if data_map[form]:
                for sub_map in data_map[form]:
                    if sub_map[chw_col]:
                        self.chw = sub_map[chw_col]
                        break
            if self.chw:
                break
        
        # set followup data
        if followup_forms:
            self.has_followup = True
            self.date_of_last_followup = followup_forms[0]["meta_timestart"] 
            
            # checklist items come from the most recent followup
            checklist_items = ["safe_pregnancy_preg_actions_iron_folic",
                               "safe_pregnancy_preg_actions_start_tt",
                               "safe_pregnancy_preg_actions_finish_tt",
                               "safe_pregnancy_preg_actions_start_ipt",
                               "safe_pregnancy_preg_actions_finish_ipt",
                               "safe_pregnancy_preg_actions_deworm",
                               "safe_pregnancy_preg_actions_birth_plan",
                               "safe_pregnancy_preg_actions_test_hiv",
                               "safe_pregnancy_preg_actions_test_syphilis",
                               "safe_pregnancy_preg_actions_test_bp",
                               "safe_pregnancy_preg_actions_test_hb"]
            
            incomplete_checklist_items = []
            for item in checklist_items:
                if followup_forms[0][item] != 1:
                    incomplete_checklist_items.append(self._clean(item, "safe_pregnancy_preg_actions_", ""))
                    
            self.incomplete_checklist_items = ", ".join(incomplete_checklist_items)
        else:
            self.incomplete_checklist_items = "No followup visits found."
            
        # Women Needing Followup 
        # > 1 month since last Followup if 1-6 Months, 
        # > 15 days since last Followup if 7-10 Months
        if followup_forms and self.date_of_last_followup:
            self.days_since_followup = (datetime.now() - self.date_of_last_followup).days
        # this is yucky but we don't want to include folks with no followups
        # and no new reg, since we're not checkign the old followups
        elif new_reg_forms:
            self.days_since_followup = (datetime.now() - self.date_of_reg).days
        else:
            # no reg or follow-ups.  leave them out for now
            self.days_since_followup = None
            self.needs_followup = False
        if self.days_since_followup is not None:
            if self.days_since_followup > 30:
                self.needs_followup = True
            elif self.days_since_followup > 15\
                 and self.months_pregnant and self.months_pregnant >= 7:
                self.needs_followup = True
            else:
                self.needs_followup = False
        
        # referrals
        self.has_followup_referral = False
        if followup_forms:
            # referrals from followup
            for followup in followup_forms:
                if not self.has_followup_referral:
                    if followup["safe_pregnancy_referred"] == "yes":
                        self.has_followup_referral = True
                        self.most_recent_followup_referral_id = followup["safe_pregnancy_referral_id"]
                        self.followup_referred = followup
                elif followup["safe_pregnancy_referral_id"] == self.most_recent_followup_referral_id:
                    # older instance of the same referral.  Use this as the instance 
                    # they were referred
                    self.followup_referred = followup
                    
                    
        self.has_close_referral = False
        if close_forms:
            # referrals from close forms
            for close in close_forms:
                if not self.has_close_referral:
                    if close["safe_pregnancy_referred"] == "yes":
                        self.has_close_referral = True
                        self.most_recent_close_referral_id = close["safe_pregnancy_referral_id"]
                        self.close_referred = close
                elif close["safe_pregnancy_referral_id"] == self.most_recent_close_referral_id:
                    # older instance of the same referral.  Use this as the instance 
                    # they were referred
                    self.close_referred = close
        
        self.has_referral = self.has_followup_referral or self.has_close_referral 
        if self.has_referral:
            self.date_referred = datetime.min
            if self.has_followup_referral:
                self.date_referred = self.followup_referred["meta_timeend"]
                self.most_recent_referral_id = self.most_recent_followup_referral_id 
                followup_wins = True
            if self.has_close_referral:
                self.date_referred = max(self.date_referred, self.close_referred["meta_timeend"])
                if self.date_referred == self.close_referred["meta_timeend"]:
                    followup_wins = False
                    self.most_recent_referral_id = self.most_recent_close_referral_id 
            
            # danger signs for the referral - pull from the visit that generated
            # it
            danger_signs = []
            if followup_wins:
                # These are the values that can be set in the followup form
                # to generate a referral
                followup_warnings = {"safe_pregnancy_feeling" : "not_well", 
                                     "safe_pregnancy_pain_from_vagina": "yes",
                                     "safe_pregnancy_headache_or_b_vision": "yes",
                                     "safe_pregnancy_dark_urine": "yes",
                                     "safe_pregnancy_swelling": "yes",
                                     "safe_pregnancy_unusual_pain": "yes",
                                     "safe_pregnancy_burn_urinate": "yes",
                                     "safe_pregnancy_baby_not_moving": "yes",
                                     "safe_pregnancy_fever": "yes",
                                     "safe_pregnancy_other_illness" : "yes"}
                
                for key, value in followup_warnings.items():
                     if self.followup_referred[key] == value:
                         danger_signs.append("%s: %s" % (self._clean(key, "safe_pregnancy_", ""),
                                                         self._clean(value, "", "")))
                # add which illness
                if "other illness: yes" in danger_signs and self.followup_referred["safe_pregnancy_which_illness"]:
                    danger_signs.remove("other illness: yes")
                    danger_signs.append("other illness: yes (%s)" % self.followup_referred["safe_pregnancy_which_illness"])
                    
            else: 
                # Close form is referred:
                if self.close_referred["safe_pregnancy_mother_survived"] == "yes":
                    closure_warnings = {
                                        "safe_pregnancy_why_not" : 'skeptical_clinic',
                                        "safe_pregnancy_why_not" : 'busy',
                                        "safe_pregnancy_why_not" : 'transport',
                                        "safe_pregnancy_why_not" : 'other',
                                        "safe_pregnancy_treatment_why_not" : 'no_medicine',
                                        "safe_pregnancy_treatment_why_not" : 'too_many_patients',
                                        "safe_pregnancy_treatment_why_not" : 'no_doctor',
                                        "safe_pregnancy_treatment_why_not" : 'no_health_workers',
                                        "safe_pregnancy_treatment_why_not" : 'other'
                                        }
                    for key, value in closure_warnings.items():
                         if self.close_referred[key] == value:
                             danger_signs.append("%s: %s" % (self._clean(key, "safe_pregnancy_", ""),
                                                             self._clean(value, "", "")))
            
            self.danger_signs = ", ".join(danger_signs)
        
        else:
            self.date_referred = None
            
        if referrals:
            # we found a referral
            self.date_of_last_referral = referrals[0]["meta_timestart"] 
            if referrals[0]["safe_pregnancy_why_not"] != "feeling_better" and\
               referrals[0]["safe_pregnancy_treatment"] != "yes":
                # the referral is open no matter what if the referral 
                # is present but not completed 
                self.has_open_referral = True
            elif self.date_referred is None or self.date_of_last_referral > self.date_referred:
                # they completed it.  
                self.has_open_referral = False
            else:
                # they closed a referral but have a more recent one 
                # that's still open
                self.has_open_referral = True
        else:
            # no information about a referral.  if there was one it's open
            self.has_open_referral = self.has_referral


    def _clean(self, column, prefix, suffix):
        '''Cleans a column by removing a prefix and suffix, if they
           are present, and converting underscores to spaces.'''
        if column.startswith(prefix):
            column = column[len(prefix):]
        if column.endswith(suffix):
            column = column[0:len(column) - len(suffix)]
        return column.replace("_", " ")