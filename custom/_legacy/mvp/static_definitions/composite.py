COMPOSITE_INDICATORS = dict(
    # Child Health
    under5_fever_rdt_proportion=dict(
        description="Proportion of children aged 6-59 months with "
                    "uncomplicated fever who received RDT test",
        title="% Under-5s w/ uncomplicated fever who received RDT test",
        numerator_slug="under5_fever_rdt",
        denominator_slug="under5_fever"
    ),
    under5_fever_rdt_positive_proportion=dict(
        description="Proportion of children aged 6-59 months with uncomplicated"
                    " fever who received RDT test and were RDT positive",
        title="% Under-5s with uncomplicated fever who received RDT test and were RDT positive",
        numerator_slug="under5_fever_rdt_positive",
        denominator_slug="under5_fever_rdt"
    ),
    under5_fever_rdt_positive_medicated_proportion=dict(
        description="Proportion of children aged 6-59 months with positive RDT"
                    " result who received antimalarial/ADT medication",
        title="% Under-5s w/ Positive RDT result who received antimalarial/ADT medication",
        numerator_slug="under5_fever_rdt_positive_medicated",
        denominator_slug="under5_fever_rdt_positive"
    ),
    under5_fever_rdt_not_received_proportion=dict(
        description="Proportion of children aged 6-59 months with uncomplicated"
                    " fever who did NOT receive RDT test due to 'RDT not available' with CHW",
        title="% Under-5s w/ RDT Not Available",
        numerator_slug="under5_fever_rdt_not_received",
        denominator_slug="under5_fever"
    ),
    under5_diarrhea_ors_proportion=dict(
        description="Proportion of children aged 2-59 months with "
                    "uncomplicated diarrhea who received ORS",
        title="% Under-5s with uncomplicated diarrhea who received ORS",
        numerator_slug="under5_diarrhea_ors",
        denominator_slug="under5_diarrhea"
    ),
    under5_diarrhea_zinc_proportion=dict(
        description="Proportion of children aged 2-59 months with "
                    "uncomplicated diarrhea who received ZINC",
        title="% Under-5s with uncomplicated diarrhea who received ZINC",
        numerator_slug="under5_diarrhea_zinc",
        denominator_slug="under5_diarrhea"
    ),
    under5_complicated_fever_facility_followup_proportion=dict(
        description="Proportion of children who attended follow-up at facility after being referred"\
                    " for complicated fever",
        title="% Under-5 attending follow-up at facility after complicated fever referral",
        numerator_slug="under5_complicated_fever_facility_followup",
        denominator_slug="under5_complicated_fever_case",
    ),
    under5_complicated_fever_referred_proportion=dict(
        description="Proportion of Under-5s with complicated fever who were referred to clinic or hospital",
        title="% of Under-5s with complicated fever referred to clinic/hospital",
        numerator_slug="under5_complicated_fever_referred",
        denominator_slug="under5_complicated_fever",
    ),
    under1_check_ups_proportion=dict(
        description="Proportion of children Under-1 receiving on-time scheduled check-ups during the time period",
        title="% Under-1 receiving check-ups",
        numerator_slug="under1_visits_6weeks",
        denominator_slug="under1_cases_6weeks",
    ),
    under1_immunized_proportion=dict(
        description="Proportion of children under-1 reported as up-to-date on immunizations at " \
                    "last visit during the time period",
        title="% of Under-1 with up-to-date immunization",
        numerator_slug="under1_immunization_up_to_date",
        denominator_slug="under1_visits",
    ),
    under5_fever_rdt_negative_medicated_proportion=dict(
        description="Proportion of children aged 6-59 months with negative RDT"
                    " result who received antimalarial/ADT medication",
        title="% Under-5s w/ Negative RDT result who received antimalarial/ADT medication",
        numerator_slug="under5_fever_rdt_negative_medicated",
        denominator_slug="under5_fever_rdt_negative"
    ),

    # Child Nutrition
    moderate_muac_wasting_proportion=dict(
        description="Proportion of children aged 6-59 months with moderate wasting (MUAC 115<125) "\
                    "at last MUAC reading this time period",
        title="% 6-59 month Children with moderate MUAC (115<125)",
        numerator_slug="child_moderate_muac_wasting",
        denominator_slug="child_muac_reading"
    ),
    severe_muac_wasting_proportion=dict(
        description="Proportion of children aged 6-59 months with severe wasting (MUAC <115) "\
                    "at last MUAC reading this time period",
        title="% 6-59 month Children with severe MUAC < 115",
        numerator_slug="child_severe_muac_wasting",
        denominator_slug="child_muac_reading"
    ),
    muac_wasting_proportion=dict(
        description="Proportion of children aged 6-59 months with moderate or severe wasting (MUAC < 125) "\
                    "at last MUAC reading this time period",
        title="% Under-5s with MUAC < 125",
        numerator_slug="child_muac_wasting",
        denominator_slug="child_muac_reading"
    ),
    muac_routine_proportion=dict(
        description="Proportion of children aged 6-59 months receiving on-time routine (every 30 days) MUAC "\
                    "readings during the time period",
        title="% Under-5s receiving on-time MUAC (30 days)",
        numerator_slug="child_muac_routine",
        denominator_slug="num_children_6to59months"
    ),
    under6month_exclusive_breastfeeding_proportion=dict(
        description="Proportion of children under 6 months reported as exclusively breast-fed at last " \
                    "visit during the time period",
        title="% Under-6-Months reported as exclusively breast-fed",
        numerator_slug="under6month_exclusive_breastfeeding",
        denominator_slug="under6month_visits",
    ),
    low_birth_weight_proportion=dict(
        description="Proportion of low birth weight (<2.5 kg) babies born during the time period",
        title="% low birth weight (<2.5 kg) babies born during the time period",
        numerator_slug="low_birth_weight",
        denominator_slug="birth_weight_registration",
    ),
    length_reading_proportion=dict(
        description="Proportion of children aged 3-24 months receiving on-time routine length measurement "
                    "(every 90 days) during the time period",
        title="% children aged 3-24 months receiving on-time length measurement (every 90 days)",
        numerator_slug="child_length_reading",
        denominator_slug="num_children_3to24months",
    ),

    # CHW Visits
    households_routine_visit_past90days=dict(
        description="Proportion of Households receiving on-time routine visit within last 90 DAYS",
        title="% of HHs receiving visit in last 90 DAYS",
        numerator_slug="household_visits_90days",
        denominator_slug="household_cases_90days"
    ),
    households_routine_visit_past30days=dict(
        description="Proportion of Households receiving on-time routine visit within last 30 DAYS",
        title="% of HHs receiving visit in last 30 DAYS",
        numerator_slug="household_visits_30days",
        denominator_slug="household_cases_30days"
    ),
    under5_routine_visit_past30days=dict(
        description="Proportion of UNDER-5 CHILDREN receiving on-time routine visit within last 30 DAYS",
        title="% of UNDER-5 CHILDREN receiving on-time routine visit within last 30 DAYS",
        numerator_slug="under5_visits_30days",
        denominator_slug="under5_cases_30days"
    ),
    pregnant_routine_visit_past30days=dict(
        description="Proportion of PREGNANT WOMEN receiving on-time routine visit within last 30 DAYS",
        title="% of PREGNANT WOMEN receiving on-time routine visit within last 30 DAYS",
        numerator_slug="pregnancy_visits_30days",
        denominator_slug="pregnancy_cases_30days"
    ),
    neonate_routine_visit_past7days=dict(
        description="Proportion of Neonates (less than 29 days old) receiving "
                    "on-time routine visit in the past 7 days "
                    "(from end of reporting period)",
        title="% of Neonates (less than 29 days old) receiving on-time routine"
              " visit in the past 7 days (from end of reporting period)",
        numerator_slug="neonate_visits_7days",
        denominator_slug="neonate_cases_7days"
    ),
    newborn_7day_visit_proportion=dict(
        description=" Proportion of children (LESS THAN 8 DAYS OLD) receiving first CHW check-up" \
		    "within 7 days of birth during the time period",
        title="% Newborns checked within 7 days of birth",
        numerator_slug="newborn_visits",
        denominator_slug="num_newborns"
    ),
    pregnancy_visit_danger_sign_referral_proportion=dict(
        description="Proportion of Pregnant Women Referred for Danger Signs",
        title="% Pregnant Women Referred for Danger Signs",
        numerator_slug="pregnancy_visit_danger_sign_referral",
        denominator_slug="pregnancy_visit_danger_sign",
    ),

    # Followups
    under5_danger_signs_referral_proportion=dict(
        description="Proportion of Under-5s Referred for Danger Signs",
        title="% Under-5s Referred for Danger Signs",
        numerator_slug="under5_danger_signs_referred",
        denominator_slug="under5_danger_signs",
    ),
    urgent_referrals_proportion=dict(
        description="Proportion of urgent referrals (emergency, take to clinic,"\
                    " basic) or treatment receiving CHW follow-up within "\
                    "2 days of referral / treatment during the time period",
        title="% Referred / Treated receiving on-time follow-up (within 2 days)",
        numerator_slug="urgent_referral_followups",
        denominator_slug="num_urgent_referrals"
    ),
    late_followups_proportion=dict(
        description="Proportion of Referred / Treated receiving LATE follow-up (within 3-7 days)",
        title="% Referred / Treated receiving LATE follow-up (within 3-7 days)",
        numerator_slug="num_late_followups",
        denominator_slug="num_urgent_referrals",
    ),
    no_followups_proportion=dict(
        description="Proportion of Referred / Treated receiving NO follow-up",
        title="% Referred / Treated receiving NO follow-up",
        numerator_slug="num_none_followups",
        denominator_slug="num_urgent_referrals",
    ),

    # Maternal Health
    family_planning_proportion=dict(
        description="Proportion of women 15-49 years old reporting use of " \
                    "modern family planning method at last visit this time period",
        title="% women 15-49 years old reporting use of modern family planning method",
        numerator_slug="household_num_fp",
        denominator_slug="household_num_ec"
    ),
    anc4_proportion=dict(
        description="Proportion of Pregnant women reporting at least four (4) Antenatal Care " \
                    "visit by 8 months of gestation this time period",
        title="% of Pregnant receiving 4 ANC visits to facility by 8 months gestation",
        numerator_slug="edd_soon_anc4",
        denominator_slug="edd_soon_visit"
    ),
    no_anc_proportion=dict(
        description="Proportion of Pregnant women reporting no Antenatal Care visit by " \
                    "4 months of gestation this time period",
        title="% Pregnant women reporting no Antenatal Care visit by 4 months of gestation",
        numerator_slug="no_anc",
        denominator_slug="anc_visit_120"
    ),
    facility_births_proportion=dict(
        description="Proportion of Births delivered in a Health Facility during the time period",
        title="% Births delivered in Health Facility",
        numerator_slug="num_births_registered_in_facility",
        denominator_slug="num_births_registered"
    ),
    pregnant_routine_checkup_proportion_6weeks=dict(
        description="Proportion of Pregnant women receiving on-time routine check-up (every 6 weeks)",
        title="% Pregnant receiving CHW visit in last 6 weeks",
        numerator_slug="pregnancy_visits_6weeks",
        denominator_slug="pregnancy_cases_6weeks",
    ),

    # Over5 Health
    over5_positive_rdt_medicated_proportion=dict(
        description="Proportion of Over-5s with positive RDT result who received antimalarial/ADT medication",
        title="% of Over-5s with positive RDT result who received antimalarial/ADT medication",
        numerator_slug="over5_positive_rdt_medicated",
        denominator_slug="over5_positive_rdt",
    ),

    #Functioning Bednet
    functioning_bednet_proportion=dict(
        description="Proportion of households ASSESSED with at least one functioning bednet"\
                    "per sleeping site during the time period",
        title="% of households ASSESSED with at least one functioning bednet per sleeping site",
        numerator_slug="household_num_func_bednets",
        denominator_slug="household_num_bednets",
    ),

    #Handwashing
    handwashing_near_latrine_proportion=dict(
        description="Proportion of households ASSESSED with handwashing station within 10m"\
                    " of the latrine during the time period",
        title="% of households ASSESSED with handwashing station within 10m of the latrine",
        numerator_slug="num_handwashing_latrine",
        denominator_slug="num_handwashing",
    ),
)
