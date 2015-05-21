from custom.world_vision.reports.child_report import ChildTTCReport
from custom.world_vision.reports.mixed_report import MixedTTCReport
from custom.world_vision.reports.mother_report import MotherTTCReport
from collections import OrderedDict

DEFAULT_REPORT_CLASS = MixedTTCReport

WORLD_VISION_DOMAINS = ('wvindia2', )

CUSTOM_REPORTS = (
    ('TTC App Reports', (
        MixedTTCReport,
        MotherTTCReport,
        ChildTTCReport
    )),
)

REASON_FOR_CLOSURE_MAPPING = OrderedDict((
    ('change_of_location', 'Migration'),
    ('end_of_pregnancy', 'End of care (PNC complete)'),
    ('not_pregnant', 'Not Pregnant (incorrect registration)'),
    ('abortion', 'Abortion'),
    ('death', 'Death'),
    ('unknown', 'Unknown')
))

CLOSED_CHILD_CASES_BREAKDOWN = {
    'death': 'Death',
    'change_of_location': 'Migration',
    'end_of_care': 'End of care'
}

MOTHER_DEATH_MAPPING = {
    'fever_or_infection_post_delivery': 'Fever/infection',
    'during_caeserian_surgery': 'Caeserian Surgery',
    'seizure': 'Seizure',
    'bleeding_postpartum': 'Excessive bleeding',
    'high_bp': 'High BP',
    'other': 'Other reason',
}

CHILD_DEATH_TYPE = {
    'newborn_death': 'Newborn deaths (< 1 month)',
    'infant_death': 'Infant deaths (< 1 year)',
    'child_death': 'Child deaths (> 1yr)'
}

CHILD_CAUSE_OF_DEATH = OrderedDict((
    ('ari', 'ARI'),
    ('fever', 'Fever'),
    ('dysentery', 'Dysentery or diarrhea'),
    ('injury', 'Injury or accident'),
    ('malnutrition', 'Malnutrition'),
    ('cholera', 'Cholera'),
    ('measles', 'Measles'),
    ('meningitis', 'Meningitis'),
    ('other', 'Other'),
    ('', 'Unknown')
))

FAMILY_PLANNING_METHODS = {
    'condom': 'Condom',
    'iud': 'IUD',
    'ocp': 'Contraceptive Pill',
    'injection': 'Depo-provera injection or implant',
    'permanent': 'Vasectomy or ligation',
    'natural': 'Natural methods',
    'other': 'Others',
    'not_wish_to_disclose': 'Does not wish to disclose'
}

MOTHER_INDICATOR_TOOLTIPS = {
    "mother_registration_details": {
        "total": "Includes cases that were opened or closed within the date range, or remained open throughout "
                 "the period",
        "total": "Total cases (both open and closed) irrespective of any date filters. Location filters "
                 "still apply.",
        "no_date_opened": "Total open cases irrespective of any date filters. Location filters still apply.",
        "no_date_closed": "Total closed cases irrespective of any date filters. Location filters still apply.",
        "new_registrations": "Cases open between today and 30 days from today"
    },
    "ante_natal_care_service_details": {
        "no_anc": "Pregnant mothers who didn't get a single ANC checkup",
        "anc_1": "Pregnant mothers who completed ANC1",
        "anc_2": "Pregnant mothers who completed ANC1 and ANC2",
        "anc_3": "Pregnant mothers who completed ANC1, ANC2 and ANC3",
        "anc_4": "Pregnant mothers who completed ANC1, ANC2, ANC3 and ANC4",
        "tt_1": "Pregnant mothers who got Tetanus 1 shot",
        "tt_2": "Pregnant mothers who got Tetanus 1 and Tetanus 2 shots",
        "tt_booster": "Pregnant mothers who got Tetanus Booster shot",
        "tt_completed": "Pregnant mothers who got Tetanus 2 or Tetanus Booster",
        "ifa_tablets": "Pregnant mothers who reported consuming IFA tablets currently",
        "100_tablets": "Mothers who completed 100 IFA tablets",
        "clinically_anemic": "Pregnant mothers who are currently identified as anemic by the Front Line Worker",
        "danger_signs": "Pregnant mothers who reported experiencing danger signs currently, "
                        "hence referred to health center",
        "knows_closest_facility": "Pregnant mothers who reported they know their nearest health facility",
        "no_anc_eligible": "Mothers more than 2.75 months pregnant (end of 1st Trimester)",
        "anc_1_eligible": "Mothers more than 2.75 months pregnant (end of 1st Trimester)",
        "anc_2_eligible": "Mothers currently more than 5.5 months pregnant (2nd Trimester) and completed ANC1",
        "anc_3_eligible": "Mothers currently more than 7.3 months pregnant (3rd Trimester) "
                          "and completed ANC1 and ANC2",
        "anc_4_eligible": "Mothers currently more than 8 months pregnant (end of 3rd Trimester) "
                          "and completed ANC1, ANC2 and ANC3",
        "tt_1_eligible": "Pregnant women who did not get 2 tetanus shots in the last 5 years",
        "tt_2_eligible": "Pregnant women who got Tetatnus 1 shots",
        "tt_booster_eligible": "Pregnant women who got 2 tetanus shots during previous pregnancy "
                               "in the last 5 years",
        "tt_completed_eligible": "Pregnant women eligible to get Tetanus 2 shot or Tetanus Booster shot",
        "ifa_tablets_eligible": "Women currently pregnant",
        "100_tablets_eligible": "Women who have delivered in the selected date range",
        "clinically_anemic_eligible": "Currently pregnant women",
        "danger_signs_eligible": "Currently pregnant women",
        "knows_closest_facility_eligible": "Currently pregnant women"
    },
    "pregnant_women_breakdown_by_trimester": {
        "total_pregnant": "Currently pregnant women",
        "trimester_1": "Women less than 2.75 months pregnant",
        "trimester_2": "Women more than 2.75 months and less than 6.4 months pregnant",
        "trimester_3": "Women more than 6.4 months pregnant"
    },
    "delivery_details": {
        "total_delivery": "Includes live births and still births",
        "trained_traditional_birth_attendant": "Deliveries at health center or done by trained birth attendant "
                                               "elsewhere",
        "institutional_deliveries": "Deliveries at health center or hospital",
        "home_deliveries": "Deliveries at home or on route",
        "abortions": "Number of reported abortions"
    },
    "postnatal_care_details": {
        "pnc_1": "Mothers visited by Front Line Worker within 48 hours of delivery",
        "pnc_2": "Mothers visited by Front Line Worker within 2-4 days of delivery",
        "pnc_3": "Mothers visited by Front Line Worker within 5-7 days of delivery",
        "pnc_4": "Mothers visited by Front Line Worker within 21-42 days of delivery",
        "pnc_1_eligible": "Mothers who have delivered",
        "pnc_2_eligible": "Mothers who have delivered 2 or more days ago",
        "pnc_3_eligible": "Mothers who have delivered 5 or more days ago",
        "pnc_4_eligible": "Mothers who have delivered 21 or more days ago"
    }
}

CHILD_INDICATOR_TOOLTIPS = {
    "child_registration_details": {
        "total": "Includes cases that were opened or closed within the date range, or remained open "
                 "throughout the period",
        "total": "Total cases (both open and closed) irrespective of any date filters. Location filters "
                 "still apply.",
        "no_date_opened": "Total open cases irrespective of any date filters. Location filters still apply.",
        "no_date_closed": "Total closed cases irrespective of any date filters. Location filters still apply.",
        "new_registration": "Cases open between today and 30 days from today"
    },
    "immunization_details": {
        "bcg_eligible": "All children in date range",
        "opv0_eligible": "All children in date range",
        "hep0_eligible": "All children in date range",
        "opv1_eligible": "Children more than  1.3 months old",
        "hep1_eligible": "Children more than  1.3 months old",
        "dpt1_eligible": "Children more than  1.3 months old",
        "opv2_eligible": "Children more than  2.5 months old",
        "hep2_eligible": "Children more than  2.5 months old",
        "dpt2_eligible": "Children more than  2.5 months old",
        "opv3_eligible": "Children more than  3.5 months old",
        "hep3_eligible": "Children more than  3.5 months old",
        "dpt3_eligible": "Children more than  3.5 months old",
        "measles_eligible": "Children more than  9 months old",
        "vita1_eligible": "Children more than  9 months old",
        "vita2_eligible": "Children more than  18 months old",
        "dpt_opv_booster_eligible": "Children more than  18 months old",
        "vita3_eligible": "Children more than  23 months old",
        "fully_immunized": "Children who received all vaccines from BCG to Measles",
        "fully_immunized_eligible": "Children more than 9 months old"
    },
    "nutrition_details": {
        "colostrum_feeding": "Children who had colostrum milk within 1 hour of birth",
        "exclusive_breastfeeding": "Children currently less than 6 months old and exclusively breastfed",
        "complementary_feeding": "Children between 6-24 months old who are receiving complementary feeding",
        "supplementary_feeding": "Children currently less than 6 months old who are receiving supplementary "
                                 "feeding in addition to breast milk",
        "colostrum_feeding_total_eligible": "Children who reported about colostrum feeding (both yes and no)",
        "exclusive_breastfeeding_total_eligible": "Children currently less than 6 months old",
        "complementary_feeding_total_eligible": "Children currently between 6-24 months old",
        "supplementary_feeding_total_eligible": "Children currently less than 6 months old"
    },
    "ebf_stopping_details": {
        "stopped_0_1": "Children currently less than 6 months old who stopped EBF when they were less than "
                       "1 month old",
        "stopped_1_3": "Children currently less than 6 months old who stopped EBF when they were between "
                       "1-3 months old",
        "stopped_3_5": "Children currently less than 6 months old who stopped EBF when they were between "
                       "3-5 months old",
        "stopped_5_6": "Children currently less than 6 months old who stopped EBF when they were between "
                       "5-6 months old"
    },
    "child_health_indicators": {
        "ari_cases": "Children who reported Penumonia between the last two visits by Front Line Worker",
        "diarrhea_cases": "Children who reported Diarrhoea between the last two visits by Front Line Worker",
        "ors": "Children who reported having ORS when they had Diarrhoea the last time",
        "zinc": "Children who reported having Zinc when they had Diarrhoea the last time",
        "deworming": "Children who got deworming does in the last 6 months",
        "deworming_total_eligible": "Children more than 1 year old"
    }
}