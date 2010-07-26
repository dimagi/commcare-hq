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
    if (mom.sampledata_mother_age >= 35):              factors.append(HI_RISK_INDICATORS["age_over_34"]["long"]) 
    if (mom.sampledata_mother_age <= 18):              factors.append(HI_RISK_INDICATORS["age_under_19"]["long"]) 
    if (mom.sampledata_mother_height == 'under_150'):  factors.append(HI_RISK_INDICATORS["small_frame"]["long"]) 
    if (mom.sampledata_previous_csection == 'yes'):    factors.append(HI_RISK_INDICATORS["previous_c_section"]["long"]) 
    if (mom.sampledata_over_5_years == 'yes'):         factors.append(HI_RISK_INDICATORS["time_since_last"]["long"]) 
    if (mom.sampledata_previous_bleeding == 'yes'):    factors.append(HI_RISK_INDICATORS["previous_bleeding"]["long"]) 
    if (mom.sampledata_previous_terminations >= 3):    factors.append(HI_RISK_INDICATORS["over_3_terminations"]["long"]) 
    if (mom.sampledata_previous_pregnancies >= 5):     factors.append(HI_RISK_INDICATORS["over_5_pregs"]["long"]) 
    if (mom.sampledata_heart_problems == 'yes'):       factors.append(HI_RISK_INDICATORS["heart_problems"]["long"]) 
    if (mom.sampledata_diabetes == 'yes'):             factors.append(HI_RISK_INDICATORS["diabetes"]["long"]) 
    if (mom.sampledata_hip_problems == 'yes'):         factors.append(HI_RISK_INDICATORS["hip_problems"]["long"]) 
    if (mom.sampledata_previous_newborn_death == 'yes'):           factors.append(HI_RISK_INDICATORS["previous_newborn_death"]["long"]) 
    if (mom.sampledata_card_results_hb_test == 'below_normal'):    factors.append(HI_RISK_INDICATORS["low_hemoglobin"]["long"]) 
    if (mom.sampledata_card_results_syphilis_result == 'positive'):    factors.append(HI_RISK_INDICATORS["hebp"]["long"]) 
    return factors
