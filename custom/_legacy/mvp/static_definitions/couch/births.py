APP_NAME = "mvp_births"

BIRTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        child_cases_by_status=dict(
            num_births_registered=dict(
                description="No. of Births Registered",
                title="# Births Registered",
                indicator_key="dob delivered"
            ),
            num_births_registered_in_facility=dict(
                description="No. of Births delivered in a Health Facility during the time period",
                title="# Births delivered in Health Facility",
                indicator_key="dob delivered_in_facility"
            ),
        ),
    )
)

COUNT_UNIQUE_BIRTH_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
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
                max_age_in_days=365,
            ),
            under1_cases_6weeks=dict(
                description="No. of children Under 1 year of age.",
                title="# Under-1s",
                indicator_key="",
                fixed_datespan_days=42,
                max_age_in_days=365,
            ),
            num_births_occured=dict(
                description="Number of births that occured during the time period.",
                title="# Births",
                max_age_in_days=31,
                show_active_only=False,
                indicator_key="occured_on"
            ),
            num_births_recorded=dict(
                description="Number of births recorded during the time period.",
                title="# Births",
                max_age_in_days=31,
                show_active_only=False,
                indicator_key="opened_on"
            ),
            num_children_6to59months=dict(
                description="No. of Children 6 to 59 Months of Age during this timespan",
                title="# Under-5s 6-59 Months",
                max_age_in_days=1825,
                min_age_in_days=180,
                indicator_key="",
            ),
            under5_cases_30days=dict(
                description="No. of Under-5 Children in the past 30 days",
                title="# Under-5s",
                max_age_in_days=1825,
                indicator_key="",
                fixed_datespan_months=1,
            ),
            neonate_cases_7days=dict(
                description="No. of Neonate Newborns in the past 7 days",
                title="# Under-5s",
                max_age_in_days=31,
                indicator_key="",
                fixed_datespan_days=7,
            ),
            num_newborns=dict(
                description="No. of newborns",
                title="# Newborns",
                indicator_key="opened_on",
                is_dob_in_datespan=True,
                show_active_only=False,
            ),
            birth_weight_registration=dict(
                description="Number of births reported with weight recorded during time period",
                title="# birth registrations w/ weight recorded",
                indicator_key="opened_on weight_recorded",
                is_dob_in_datespan=True,
                show_active_only=False,
            ),
            low_birth_weight=dict(
                description="No. of low birth weight (<2.5 kg) babies born during the time period",
                title="# low birth weight (<2.5 kg) births",
                indicator_key="opened_on low_birth_weight",
                is_dob_in_datespan=True,
                show_active_only=False,
            ),
            num_children_3to24months=dict(
                description="No. of Children 3 to 24 Months of Age during this timespan",
                title="# Under-5s 3-24 Months",
                max_age_in_days=730,
                min_age_in_days=90,
                indicator_key="",
            ),
        )
    )
)
