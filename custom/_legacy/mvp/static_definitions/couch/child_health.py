APP_NAME = "mvp_child_health"

CHILD_HEALTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        under5_child_health=dict(
            num_under5_visits=dict(
                description="No. of Under-5s Visited",
                title="# Under-5s Visited",
                indicator_key="under5"
            ),
            under5_danger_signs=dict(
                description="No. of Under-5s with Danger Signs",
                title="# Under-5s with Danger Signs",
                indicator_key="under5_danger_signs"
            ),
            under5_danger_signs_referred=dict(
                description="No. of Under-5s Referred for Danger Signs",
                title="# Under-5s Referred for Danger Signs",
                indicator_key="under5_danger_signs_referred"
            ),
            under5_fever=dict(
                description="No. of Under-5s with uncomplicated Fever",
                title="# Under-5s w/ Uncomplicated Fever",
                indicator_key="under5_fever"
            ),
            under5_fever_rdt=dict(
                description="No. of Under-5s with uncomplicated fever who received RDT test",
                title="# Under-5s w/ Uncomplicated Fever receiving RDT Test",
                indicator_key="under5_fever rdt_test_received"
            ),
            under5_fever_rdt_positive=dict(
                description="No. of Under-5s with uncomplicated fever who received RDT test and were RDT positive",
                title="# Under-5s w/ Positive RDT Result",
                indicator_key="under5_fever rdt_test_received rdt_test_positive"
            ),
            under5_fever_rdt_negative=dict(
                description="No. of Under-5s with negative RDT result",
                title="# Under-5s w/ Negative RDT Result",
                indicator_key="under5_fever rdt_test_received rdt_test_negative"
            ),
            under5_fever_rdt_positive_medicated=dict(
                description="No. of Under-5s with positive RDT result who received antimalarial/ADT medication",
                title="# Under-5s w/ Positive RDT Receiving Antimalarial/ADT",
                indicator_key="under5_fever rdt_test_received rdt_test_positive anti_malarial"
            ),
            under5_fever_rdt_negative_medicated=dict(
                description="No. of Under-5s with negative RDT result who received antimalarial/ADT medication",
                title="# Under-5s w/ Negative RDT Receiving Antimalarial/ADT",
                indicator_key="under5_fever rdt_test_negative anti_malarial"
            ),
            under5_fever_rdt_not_received=dict(
                description="No. of Under-5s with uncomplicated fever who did NOT receive RDT "
                            "test due to 'RDT not available' with CHW",
                title="# Under-5s w/ 'RDT not available",
                indicator_key="under5_fever rdt_not_available"
            ),
            under5_diarrhea=dict(
                description="No. of Under-5s with uncomplicated Diarrhea",
                title="# Under-5s w/ Uncomplicated Diarrhea",
                indicator_key="under5_diarrhea"
            ),
            under5_diarrhea_ors=dict(
                description="No. Under-5s with uncomplicated diarrhea who received ORS",
                title="# Under-5s w/ Uncomplicated Diarrhea Receiving ORS",
                indicator_key="under5_diarrhea ors"
            ),
            under5_diarrhea_zinc=dict(
                description="No. Under-5s with uncomplicated diarrhea who received zinc treatment",
                title="# Under-5s w/ Uncomplicated Diarrhea Receiving ZINC",
                indicator_key="under5_diarrhea zinc"
            ),
            under5_complicated_fever=dict(
                description="No. of Under-5s with Complicated Fever",
                title="# Under-5s w/ Complicated Fever",
                indicator_key="under5_complicated_fever"
            ),
            under5_complicated_fever_referred=dict(
                description="No. of Under-5s with complicated fever who were referred to clinic or hospital",
                title="# Under-5s with complicated fever referred to clinic/hospital",
                indicator_key="under5_complicated_fever referred"
            )
        ),
        child_case_indicators=dict(
            under5_complicated_fever_facility_followup=dict(
                description="No. of children who attended follow-up at facility after being referred"\
                            " for complicated fever",
                title="# Under-5 who attended follow-up at facility, referred for complicated fever",
                indicator_key="under5_complicated_fever facility_followup"
            ),
            under5_complicated_fever_case=dict(
                description="No. of Under-5s with Complicated Fever",
                title="# Under-5s w/ Complicated Fever",
                indicator_key="under5_complicated_fever"
            ),
        ),
    )
)

COUNT_UNIQUE_CHILD_HEALTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        child_muac=dict(
            child_muac_routine=dict(
                description="No. of children aged 6-59 months receiving on-time routine (every 90 days)"
                            " MUAC readings during the time period",
                title="# Under5s receiving on-time MUAC (90 days)",
                indicator_key="routine_muac"
            ),
            child_moderate_muac_wasting=dict(
                description="No. children aged 6-59 months with moderate wasting (MUAC 115<125)"
                            " at last MUAC reading this time period",
                title="# 6-59 month Children with moderate MUAC (115<125)",
                indicator_key="moderate_muac_wasting"
            ),
            child_severe_muac_wasting=dict(
                description="No. children aged 6-59 months with moderate or severe wasting (MUAC < 125)"
                            " at last MUAC reading this time period",
                title="# 6-59 month Children with severe MUAC < 115",
                indicator_key="severe_muac_wasting"
            ),
            child_muac_wasting=dict(
                description="No. children aged 6-59 months with moderate or severe wasting (MUAC < 125)"
                            " at last MUAC reading this time period",
                title="# 6-59 month Children with MUAC < 125",
                indicator_key="muac_wasting"
            ),
            child_muac_reading=dict(
                description="No. children aged 6-59 months with MUAC reading this time period",
                title="# 6-59 month Children with MUAC reading",
                indicator_key="muac_reading"
            ),
            child_length_reading=dict(
                description="No. children aged 3-24 months receiving on-time "
                            "routine length measurement (every 90 days) "
                            "during the time period",
                title="# 3-24 month Children receiving on-time Length (90 days)",
                indicator_key="length_reading"
            ),
        ),
    )
)

SUM_LAST_UNIQUE_CHILD_HEALTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        child_muac=dict(
            active_gam_cases=dict(
                description="No. of Active GAM cases within time period",
                title="# of Active GAM Cases",
                indicator_key="active_gam"
            )
        )
    )
)
