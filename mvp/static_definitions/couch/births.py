BIRTH_INDICATORS = dict(
    app="mvp_births",
    indicators=dict(
        child_cases_by_dob=dict(
            newborn_visit=dict(
                description="No. of newborns receiving first CHW check-up within 7 days of birth during the time period",
                title="# Newborns checked within 7 days of birth",
                indicator_key="newborn_visit",
                startdate_shift=-7,
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