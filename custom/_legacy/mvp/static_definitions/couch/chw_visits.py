APP_NAME = "mvp_chw_visits"

CHW_VISIT_ACTIVE_CASES_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        all_cases=dict(
            household_cases_90days=dict(
                description="No. of active households in the past 90 days",
                title="# Households in past 90 days",
                indicator_key="",
                case_type="household",
                fixed_datespan_months=3,
            ),
            household_cases_30days=dict(
                description="No. of Households in the past 30 days",
                title="# Households in the past 30 days",
                indicator_key="",
                case_type="household",
                fixed_datespan_months=1,
            ),
            household_cases=dict(
                description="No. of Active Households ",
                title="# Households in specified time period",
                indicator_key="",
                case_type="household",
            ),
            pregnancy_cases_6weeks=dict(
                description="No. of Active Pregnancies in the Past 6 Weeks",
                title="# pregnancies in last 6 weeks",
                indicator_key="",
                case_type="pregnancy",
                fixed_datespan_days=42,
            ),
            pregnancy_cases_30days=dict(
                description="No. of Active Pregnancies in the Past 30 Days",
                title="# pregnancies in the last 30 days",
                indicator_key="",
                case_type="pregnancy",
                fixed_datespan_months=1,
            ),
            pregnancy_cases=dict(
                description="No. of Active Pregnancies",
                title="# Pregnancies in specified time period",
                indicator_key="",
                case_type="pregnancy",
            ),
        )
    )
)

CHW_VISIT_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        all_visit_forms=dict(
            household_visits=dict(
                description="No. of household visits",
                title="# Household Visits in specified time period",
                indicator_key="household",
            ),
        ),
    ),
)

CHW_VISITS_UNIQUE_COUNT_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        all_visit_forms=dict(
            household_visits_90days=dict(
                description="No. of household visits in the past 90 days.",
                title="# household visits in past 90 days",
                indicator_key="household",
                fixed_datespan_months=3,
            ),
            household_visits_30days=dict(
                description="No. of household visits",
                title="# Household Visits",
                indicator_key="household",
                fixed_datespan_months=1,
            ),
            pregnancy_visits_6weeks=dict(
                description="No. of pregnancy visits in the past 6 weeks",
                title="# Pregnancy Visits in Past 6 Weeks",
                indicator_key="pregnancy",
                fixed_datespan_days=42,
            ),
            pregnancy_visits_30days=dict(
                description="No. of Pregnancy Visits in the last 30 days",
                title="# Pregnancy Visits in Past 30 days",
                indicator_key="pregnancy",
                fixed_datespan_months=1,
            ),
            under5_visits_30days=dict(
                description="No. of Under5 visits",
                title="# Under5 Visits",
                indicator_key="child under5",
                fixed_datespan_months=1,
            ),
            neonate_visits_7days=dict(
                description="No. of Neonate visits",
                title="# Neonate Visits",
                indicator_key="child neonate",
                fixed_datespan_days=7,
            ),
            under1_visits=dict(
                description="No. of children Under-1 receiving on-time scheduled check-ups during the time period",
                title="# Under-1 receiving check-ups",
                indicator_key="child under1",
            ),
            under1_visits_6weeks=dict(
                description="No. of children Under-1 receiving on-time scheduled check-ups during the time period",
                title="# Under-1 receiving check-ups",
                fixed_datespan_days=42,
                indicator_key="child under1",
            ),
            under1_immunization_up_to_date=dict(
                description="No. of children Under-1 with up-to-date immunizations at visit during this time period",
                title="# Under-1 up-to-date immunizations",
                indicator_key="child under1 immunized",
            ),
            newborn_visits=dict(
                description="No. of newborns visited 7 days after birth",
                title="# Newborns visited 7 days after birth",
                indicator_key="child 7days",
            ),
            under6month_exclusive_breastfeeding=dict(
                description="No. of children under 6 months reported as exclusively breast-fed during visit",
                title="# Under-6-Months reported as exclusively breast-fed during visit",
                indicator_key="child under6mo_ex_breast",
            ),
            under6month_visits=dict(
                description="No. of children receiving visit who were under 6 months",
                title="# Under-6-Month Visits",
                indicator_key="child under6mo",
            ),
            household_num_func_bednets=dict(
                description="No. of households ASSESSED with at least one functioning bednet per sleeping site",
                title="# of households with at least one functioning bednet per sleeping site",
                indicator_key="household atleastonebednet",
            ),
            household_num_bednets=dict(
                description="No. of households ASSESSED for functioning bednet",
                title="# of households ASSESSED  for functioning bednet",
                indicator_key="household bednet",
            ),
            num_handwashing_latrine=dict(
                description="No. of households ASSESSED with handwashing station within 10m of the latrine",
                title="# of households with handwashing station within 10m of the latrine",
                indicator_key="household handwashing10metres",
            ),
            num_handwashing=dict(
                description="No. of households ASSESSED with handwashing station",
                title="# of households with handwashing station",
                indicator_key="household handwashing",
            ),
        )
    )
)
