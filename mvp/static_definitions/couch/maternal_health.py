APP_NAME = "mvp_maternal_health"

MATERNAL_HEALTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        pregnancy_danger_signs=dict(
            pregnancy_visit_danger_sign=dict(
                description="No. of Pregnant Women With Danger Sign Recorded During Visit",
                title="# Pregnant Women w/ Danger Signs",
                indicator_key="danger_sign",
            ),
            pregnancy_visit_danger_sign_referral=dict(
                description="No. of Pregnant Women Referred for Danger Signs",
                title="# Pregnant Women Referred for Danger Signs",
                indicator_key="danger_sign referred",
            )
        ),
        anc_visits=dict(
            edd_soon_anc4=dict(
                description="No. of Pregnant women reporting at least four (4) Antenatal Care "
                            "visit by 8 months of gestation this time period",
                title="Pregnant receiving 4 ANC visits to facility by 8 months gestation",
                indicator_key="anc4"
            ),
            edd_soon_visit=dict(
                description="No. of Pregnant women who have at least one visit by 8 months of gestation",
                title="Pregnant receiving at least one ANC visit by 8 months gestation",
                indicator_key="visit"
            )
        ),
    )
)

# Use SumLastUniqueEmittedValueCouchViewIndicatorDefinition

SUM_LAST_UNIQUE_MATERNAL_HEALTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        family_planning=dict(
            household_num_fp=dict(
                description="No. households using family planning",
                title="# Households Using Family Planning",
                indicator_key="num_fp"
            ),
            household_num_ec=dict(
                description="No. of Households Seen for Family Planning",
                title="# of Women 15-49 Seen for Family Planning",
                indicator_key="num_ec"
            )
        ),
    )
)
