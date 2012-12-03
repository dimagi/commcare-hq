COMPOSITE_INDICATORS = dict(
    # Child Health
    under5_fever_rdt_proportion=dict(
        description="Proportion of Under-5s with uncomplicated fever who received RDT test",
        title="% Under-5s w/ uncomplicated fever who received RDT test",
        numerator_slug="under5_fever_rdt",
        denominator_slug="under5_fever"
    ),
    under5_fever_rdt_positive_proportion=dict(
        description="Proportion of Under-5s with uncomplicated fever who received RDT test and were RDT positive",
        title="% Under-5s with uncomplicated fever who received RDT test and were RDT positive",
        numerator_slug="under5_fever_rdt_positive",
        denominator_slug="under5_fever_rdt"
    ),
    under5_fever_rdt_positive_medicated_proportion=dict(
        description="Proportion of Under-5s with positive RDT result who received antimalarial/ADT medication",
        title="% Under-5s w/ Positive RDT result who received antimalarial/ADT medication",
        numerator_slug="under5_fever_rdt_positive_medicated",
        denominator_slug="under5_fever_rdt_positive"
    ),
    under5_fever_rdt_not_received_proportion=dict(
        description="Proportion of Under-5s with uncomplicated fever who did NOT receive RDT "
                    "test due to 'RDT not available' with CHW",
        title="% Under-5s w/ RDT Not Available",
        numerator_slug="under5_fever_rdt_not_received",
        denominator_slug="under5_fever"
    ),
    under5_diarrhea_ors_proportion=dict(
        description="Proportion of Under-5s with uncomplicated diarrhea who received ORS",
        title="% Under-5s with uncomplicated diarrhea who received ORS",
        numerator_slug="under5_diarrhea_ors",
        denominator_slug="under5_diarrhea"
    ),
    under5_diarrhea_zinc_proportion=dict(
        description="Proportion of Under-5s with uncomplicated diarrhea who received ZINC",
        title="% Under-5s with uncomplicated diarrhea who received ZINC",
        numerator_slug="under5_diarrhea_zinc",
        denominator_slug="under5_diarrhea"
    ),
    under5_complicated_fever_facility_followup_proportion=dict(
        description="Proportion of children who attended follow-up at facility after being referred"\
                    " for complicated fever",
        title="% Under-5 attending follow-up at facility after complicated fever referral",
        numerator_slug="under5_complicated_fever_facility_followup",
        denominator_slug="under5_complicated_fever",
    ),
    under5_complicated_fever_referred_proportion=dict(
        description="Proportion of children who attended follow-up at facility after being referred"\
                    " for complicated fever",
        title="% Under-5 attending follow-up at facility after complicated fever referral",
        numerator_slug="under5_complicated_fever_referred",
        denominator_slug="under5_complicated_fever",
    ),
    under1_check_ups_proportion=dict(
        description="Proportion of children Under-1 receiving on-time scheduled check-ups during the time period",
        title="% Under-1 receiving check-ups",
        numerator_slug="under1_visits",
        denominator_slug="under1_cases",
    ),
    under5_fever_rdt_negative_medicated_proportion=dict(
        description="Proportion of Under-5s with negative RDT result who received antimalarial/ADT medication",
        title="% Under-5s w/ Negative RDT result who received antimalarial/ADT medication",
        numerator_slug="under5_fever_rdt_negative_medicated",
        denominator_slug="under5_fever_rdt_negative"
    ),

    # Child Nutrition
    muac_wasting_proportion=dict(
        description="Proportion of children aged 6-59 months with moderate or severe wasting (MUAC < 125) "\
                    "at last MUAC reading this time period",
        title="% Under-5s with MUAC < 125",
        numerator_slug="child_muac_wasting",
        denominator_slug="child_muac_reading"
    ),
    muac_routine_proportion=dict(
        description="Proportion of children aged 6-59 months receiving on-time routine (every 90 days) MUAC "\
                    "readings during the time period",
        title="% Under-5s receiving on-time MUAC (90 days)",
        numerator_slug="child_muac_routine",
        denominator_slug="num_active_under5"
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
        numerator_slug="low_birth_weight_registration",
        denominator_slug="birth_weight_registration",
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
        description="Proportion of NEONATES (NEWBORN LESS THAN 30 DAYS OLD) receiving on-time" \
                    " routine visit within last 7 DAYS",
        title="% of NEONATES (NEWBORN LESS THAN 30 DAYS OLD) receiving on-time routine visit " \
              "within last 7 DAYS",
        numerator_slug="neonate_visited_past7days",
        denominator_slug="num_neonate_past7days"
    ),
    urgent_referrals_proportion=dict(
        description="Proportion of urgent referrals (codes A, E, B) or treatment receiving CHW "\
                    "follow-up within 2 days of referral / treatment during the time period",
        title="% Referred / Treated receiving on-time follow-up (within 2 days)",
        numerator_slug="urgent_referral_followups",
        denominator_slug="num_urgent_referrals"
    ),
    newborn_7day_visit_proportion=dict(
        description=" Proportion of newborns receiving first CHW check-up within 7 days of " \
                    "birth during the time period",
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
    on_time_followups_proportion=dict(
        description="Proportion of Referred / Treated receiving on-time follow-up (within 2 days)",
        title="% Referred / Treated receiving on-time follow-up (within 2 days)",
        numerator_slug="num_on_time_followups",
        denominator_slug="num_urgent_treatment_referral",
    ),
    late_followups_proportion=dict(
        description="Proportion of Referred / Treated receiving LATE follow-up (within 3-7 days)",
        title="% Referred / Treated receiving LATE follow-up (within 3-7 days)",
        numerator_slug="num_late_followups",
        denominator_slug="num_urgent_treatment_referral",
    ),
    no_followups_proportion=dict(
        description="Proportion of Referred / Treated receiving NO follow-up",
        title="% Referred / Treated receiving NO follow-up",
        numerator_slug="num_none_followups",
        denominator_slug="num_urgent_treatment_referral",
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
    facility_births_proportion=dict(
        description="Proportion of Births delivered in a Health Facility during the time period",
        title="% Births delivered in Health Facility",
        numerator_slug="num_births_registered_in_facility",
        denominator_slug="num_births_registered"
    ),
    pregnant_routine_checkup_proportion_6weeks=dict(
        description="Proportion of Pregnant women receiving on-time routine check-up (every 6 weeks)",
        title="% Pregnant receiving CHW visit in last 6 weeks",
        numerator_slug="pregnant_visited_past6weeks",
        denominator_slug="pregnancy_cases_6weeks",
    ),
)