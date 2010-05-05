from reports.custom.shared import Mother

HI_RISK_INDICATORS = {
    'high_risk':
        {'short' : "Tot.",          'long' : "All High Risk",   'where' : "sampledata_hi_risk = 'yes'"},
    'hebp': 
        {'short' : "Hep B",         'long' : "Positive for Hepatitis B",'where' : "sampledata_card_results_hepb_result = 'yes"},
    'previous_newborn_death': 
        {'short' : "Pr. NB Death",  'long' : "Previous Newborn Death",  'where' : "sampledata_previous_newborn_death = 'yes'"},
    'low_hemoglobin': 
        {'short' : "Lo Hmg",        'long' : "Low Hemoglobin",          'where' : "sampledata_card_results_hb_test = 'yes'"},
    'syphilis': 
        {'short' : "Syph.",         'long' : "Positive for Syphilis",   'where' : "sampledata_card_results_syphilis_result = 'yes'"},
    'rare_blood': 
        {'short' : "Blood",         'long' : "Rare Blood Type",         'where' : "sampledata_card_results_blood_group <> 'opositive' AND sampledata_card_results_blood_group <> 'apositive' AND sampledata_card_results_blood_group <> 'bpositive' AND sampledata_card_results_blood_group<>'abpositive' AND sampledata_card_results_blood_group IS NOT NULL"},
    'age_over_34': 
        {'short' : ">34",           'long' : "35 or Older",             'where' : 'sampledata_mother_age >= 34'},
    'previous_bleeding': 
        {'short' : "Bleed",         'long' : "Previous Bleeding",       'where' : "sampledata_previous_bleeding = 'yes'"},
    'over_5_pregs': 
        {'short' : ">5 pr",         'long' : "5+ Previous Pregnanices", 'where' : 'sampledata_previous_pregnancies >= 5'},
    'heart_problems': 
        {'short' : "Heart",         'long' : "Heart Problems",          'where' : "sampledata_heart_problems = 'yes'"},
    'previous_c_section':
        {'short' : "Pr. C",         'long' : "Previous C-Section",      'where' : "sampledata_previous_csection = 'yes'"},
    'time_since_last':
        {'short' : "Time",          'long' : "Over 5 years since last pregnancy",'where' : "sampledata_over_5_years = 'yes'"},
    'age_under_19': 
        {'short' : "<19",           'long' : "18 or Younger",           'where' : "sampledata_mother_age <= 18"},
    'small_frame': 
        {'short' : "Small",         'long' : "Height 150cm or Less",    'where' : "sampledata_mother_height = 'under_150'"},
    'over_3_terminations': 
        {'short' : "3+ Term",       'long' : "Over 3 Past Terminations",'where' : 'sampledata_previous_terminations >= 3'},
    'hip_problems':
        {'short' : "Hip",           'long' : "Hip Problems",            'where' : "sampledata_hip_problems = 'yes'"},
    'diabetes':
        {'short' : "Diab.",         'long' : "Diabetes",                'where' : "sampledata_diabetes = 'yes'"}
}

def get_hi_risk_factors_for(mom):
    factors = []
    if (mom.mother_age >= 35):              factors.append(HI_RISK_INDICATORS["age_over_34"]["long"]) 
    if (mom.mother_age <= 18):              factors.append(HI_RISK_INDICATORS["age_under_19"]["long"]) 
    if (mom.mother_height == 'under_150'):  factors.append(HI_RISK_INDICATORS["small_frame"]["long"]) 
    if (mom.previous_csection == 'yes'):    factors.append(HI_RISK_INDICATORS["previous_c_section"]["long"]) 
    if (mom.over_5_years == 'yes'):         factors.append(HI_RISK_INDICATORS["time_since_last"]["long"]) 
    if (mom.previous_bleeding == 'yes'):    factors.append(HI_RISK_INDICATORS["previous_bleeding"]["long"]) 
    if (mom.previous_terminations >= 3):    factors.append(HI_RISK_INDICATORS["over_3_terminations"]["long"]) 
    if (mom.previous_pregnancies >= 5):     factors.append(HI_RISK_INDICATORS["over_5_pregs"]["long"]) 
    if (mom.heart_problems == 'yes'):       factors.append(HI_RISK_INDICATORS["heart_problems"]["long"]) 
    if (mom.diabetes == 'yes'):             factors.append(HI_RISK_INDICATORS["diabetes"]["long"]) 
    if (mom.hip_problems == 'yes'):         factors.append(HI_RISK_INDICATORS["hip_problems"]["long"]) 
    if (mom.previous_newborn_death == 'yes'):           factors.append(HI_RISK_INDICATORS["previous_newborn_death"]["long"]) 
    if (mom.card_results_hb_test == 'below_normal'):    factors.append(HI_RISK_INDICATORS["low_hemoglobin"]["long"]) 
    if (mom.card_results_syphilis_result == 'positive'):    factors.append(HI_RISK_INDICATORS["hebp"]["long"]) 
    return factors
    # 
    # 
    # reasons = []
    # if (mom.mother_age >= 35):              reasons.append("35 or older") 
    # if (mom.mother_age <= 18):              reasons.append("18 or younger")
    # if (mom.mother_height == 'under_150'):  reasons.append("Mother height under 150cm")
    # if (mom.previous_csection == 'yes'):    reasons.append("Previous C-section")
    # if (mom.over_5_years == 'yes'):         reasons.append("Over 5 years since last pregnancy")
    # if (mom.previous_bleeding == 'yes'):    reasons.append("Previous bleeding")
    # if (mom.previous_terminations >= 3):    reasons.append("%s previous terminations" % mom.previous_terminations)
    # if (mom.previous_pregnancies >= 5):     reasons.append("%s previous pregnancies" % mom.previous_pregnancies)
    # if (mom.heart_problems == 'yes'):       reasons.append("Heart problems")
    # if (mom.diabetes == 'yes'):             reasons.append("Diabetes")
    # if (mom.hip_problems == 'yes'):         reasons.append("Hip problems")
    # if (mom.previous_newborn_death == 'yes'):           reasons.append("Previous newborn death")
    # if (mom.card_results_hb_test == 'below_normal'):    reasons.append("Low hb test")
    # if (mom.card_results_blood_group == 'onegative'):   reasons.append("O-negative blood group")
    # if (mom.card_results_blood_group == 'anegative'):   reasons.append("A-negative blood group")
    # if (mom.card_results_blood_group == 'abnegative'):  reasons.append("AB-negative blood group")
    # if (mom.card_results_blood_group == 'bnegative'):   reasons.append("B-negative blood group")
    # if (mom.card_results_hepb_result == 'positive'):    reasons.append("Positive for hepb")
    # if (mom.card_results_syphilis_result == 'positive'):    reasons.append("Positive for syphilis")
