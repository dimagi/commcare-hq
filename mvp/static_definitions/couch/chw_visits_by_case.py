APP_NAME = "mvp_chw_visits_by_case"

CHW_VISIT_INDICATORS_BY_CASE = dict(
    app=APP_NAME,
    indicators=dict(
        child_cases_by_status=dict(
            num_newborns=dict(
                description="No. of newborns",
                title="# Newborns",
                indicator_key="dob",
            ),
        )
    )
)

# Indicators below use MVPActiveCasesCouchViewIndicatorDefinition
ACTIVE_CASES_CHW_VISIT_INDICATORS = dict(
    app="mvp_chw_visits_by_case",
    indicators=dict(
        child_cases_by_status=dict(
            num_under5_past30days=dict(
                description="Number of Under-5s in the last 30 days",
                title="# Under-5s in last 30 days",
                indicator_key="dob",
                fixed_datespan_days=30,
                startdate_shift=-1826, # <60 months (5 years)
            ),
            num_neonate_past7days=dict(
                description="Number of Neonates in the last 7 days",
                title="# Neonates in last 7 days",
                indicator_key="dob",
                fixed_datespan_days=7,
                startdate_shift=-31,
            ),
            num_children=dict(
                description="No. of children",
                title="# Children",
                indicator_key="dob",
                startdate_shift=-1826, # <60 months (5 years)
                enddate_shift=-183 # >6 months
            ),
            num_under5=dict(
                description="No. of Children Under 5",
                title="# Under-5s",
                indicator_key="dob",
                startdate_shift=-1826, # <60 months (5 years)
            ),
            num_under1=dict(
                description="No. of Children Under 1",
                title="# Under-1s",
                indicator_key="dob",
                startdate_shift=-365, # 1 year
            ),
            num_active_gam=dict(
                description="No. of Active GAM Cases",
                title="# Active GAM Cases",
                indicator_key="gam"
            )
        ),
        household_cases_by_status=dict(
            num_active_households_past30days=dict(
                description="No. of Active Households in the last 30 days",
                title="# Active Household Cases in last 30 days",
                indicator_key="",
                fixed_datespan_days=30
            ),
            num_active_households_past90days=dict(
                description="No. of Active Households in the last 90 days",
                title="# Active Household Cases in last 90 days",
                indicator_key="",
                fixed_datespan_days=90
            ),
            num_active_households=dict(
                description="No. of Households",
                indicator_key=""
            )
        ),
        pregnancy_cases_by_status=dict(
            num_active_pregnancies_past30days=dict(
                description="No. of Pregnant Women in the last 30 days",
                title="# Pregnant Women in last 30 days",
                indicator_key="",
                fixed_datespan_days=30,
                startdate_shift=-266
            ),
            num_active_pregnancies=dict(
                description="No. of Pregnant Women",
                title="# Pregnant Women",
                indicator_key="",
                startdate_shift=-266
            )
        ),
    )
)