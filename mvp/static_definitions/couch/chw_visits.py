CHW_VISIT_INDICATORS = dict(
    app="mvp_chw_visits_by_form",
    indicators=dict(
        #note this doesn't count uniquely
        all_visit_forms=dict(
            num_household_visits=dict(
                description="No. of Household visits",
                title="# Household Visits",
                indicator_key="household"
            )
        ),
#        visited_households=dict(
#            visited_households_past30days=dict(
#                description="No. of unique households visited in the last 30 days",
#                title="# Households Visited in Last 30 Days",
#                indicator_key="visited",
#                fixed_datespan_days=30
#            ),
#            visited_households_past90days=dict(
#                description="No. of unique households visited in the last 90 days",
#                title="# Households Visited in Last 90 Days",
#                indicator_key="visited",
#                fixed_datespan_days=90
#            )
#        ),
#        visited_pregnancies=dict(
#            pregnant_visited_past30days=dict(
#                description="No. of Pregnant Women visited in the last 30 days",
#                title="# Pregnant Women Visited in Last 30 Days",
#                indicator_key="pregnant",
#                fixed_datespan_days=30
#            ),
#            pregnant_visited_past6weeks=dict(
#                description="No. of Pregnant Women visited in the last 6 weeks",
#                title="# Pregnant Women Visited in Last 6 weeks",
#                indicator_key="pregnant",
#                fixed_datespan_days=42
#            ),
#        ),
#        visited_under5=dict(
#            under5_visited_past30days=dict(
#                description="No. of Under-5s visited in the last 30 days",
#                title="# Under-5s Visited in Last 30 Days",
#                indicator_key="under5",
#                fixed_datespan_days=30
#            ),
#            neonate_visited_past7days=dict(
#                description="No. of Neonate Newborns visited in the last 7 days",
#                title="# Newborns Visited in Last 7 Days",
#                indicator_key="neonate",
#                fixed_datespan_days=7
#            ),
#        ),
    )
)

CHW_VISIT_ACTIVE_CASES_INDICATORS = dict(
    app="indicators",
    indicators=dict(
        cases_by_status=dict(

        )
    )
)

CHW_VISITS_UNIQUE_COUNT_INDICATORS = dict(
    app="mvp_chw_visits",
    indicators=dict(

    )
)