APP_NAME = "mvp_births"

BIRTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        child_cases_by_dob=dict(
            num_newborns=dict(
                description="No. of newborns",
                title="# Newborns",
                indicator_key="dob",
            )
        ),
        child_registrations=dict(
            num_births_registered=dict(
                description="No. of Births Registered",
                title="# Registered Births",
                indicator_key="registration"
            ),
            num_births_registered_in_facility=dict(
                description="No. of Births delivered in a Health Facility during the time period",
                title="# Births delivered in Health Facility",
                indicator_key="facility_delivery"
            ),
            low_birth_weight_registration=dict(
                description="No. of low birth weight (<2.5 kg) babies born during the time period",
                title="# low birth weight (<2.5 kg) births",
                indicator_key="birth_weight low"
            ),
            birth_weight_registration=dict(
                description="Number of births reported with weight recorded during time period",
                title="# birth registrations w/ weight recorded",
                indicator_key="birth_weight"
            ),
        ),
    )
)

# These indicators use MVPChildCasesByAgeIndicatorDefinition

ACTIVE_CHILD_CASES_BY_AGE_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        #todo rename to by_status
        child_cases_bs=dict(
            num_active_under1=dict(
                description="No. of children Under 1 year of age.",
                title="# Under-1s",
                indicator_key="",
                age_in_days=365,
            ),
            num_births_recorded=dict(
                description="Number of births recorded during the time period.",
                title="# Births",
                age_in_days=31,
                filter_by_active=False,
                indicator_key="opened_on"
            ),
        )
    )
)