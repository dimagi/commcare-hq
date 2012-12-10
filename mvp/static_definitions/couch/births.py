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
                title="# Births Registered",
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
        child_cases_by_status=dict(
            under1_cases=dict(
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
            num_active_under5=dict(
                description="No. of Under-5 Children during this timespan",
                title="# Under-5s",
                age_in_days=1827,
                indicator_key="",
            ),
            under5_cases_30days=dict(
                description="No. of Under-5 Children in the past 30 days",
                title="# Under-5s",
                age_in_days=1827,
                indicator_key="",
                fixed_datespan_months=1,
            ),
            neonate_cases_7days=dict(
                description="No. of Neonate Newborns in the past 7 days",
                title="# Under-5s",
                age_in_days=31,
                indicator_key="",
                fixed_datespan_days=7,
            ),
        )
    )
)
