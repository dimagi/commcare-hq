APP_NAME = "mvp_chw_referrals"

CHW_REFERRAL_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        followup_cases=dict(
            num_on_time_followups=dict(
                description="# Referred / Treated receiving on-time follow-up (within 2 days)",
                title="# Referred / Treated receiving on-time follow-up (within 2 days)",
                indicator_key="urgent_followup on_time",
            ),
            num_late_followups=dict(
                description="# Referred / Treated receiving LATE follow-up (within 3-7 days)",
                title="# Referred / Treated receiving LATE follow-up (within 3-7 days)",
                indicator_key="urgent_followup late",
            ),
            num_none_followups=dict(
                description="# Referred / Treated receiving NO follow-up",
                title="# Referred / Treated receiving NO follow-up",
                indicator_key="urgent_followup none",
            )
        ),
        urgent_referrals_by_case=dict(
            urgent_referral_followups=dict(
                description="No. urgent referrals (codes A, E, B) or treatment receiving CHW follow-up within 2 days "\
                            "of referral / treatment during the time period",
                title="# Urgent Referrals w/ Followup within 2 days",
                indicator_key="urgent_referral_followup"
            )
        ),
        urgent_referrals_by_form=dict(
            num_urgent_referrals=dict(
                description="No. of Urgent Referrals",
                title="# Urgent Referrals",
                indicator_key="urgent_referral"
            ),
            num_urgent_treatment_referral=dict(
                description="No. of Cases Urgently referred OR Treated by CHW",
                title="# Cases Urgently referred OR Treated by CHW",
                indicator_key="urgent_treatment_referral"
            )
        ),
    )
)

# Indicators below use MedianEmittedValueCouchViewIndicatorDefinition

MEDIAN_CHW_REFERRAL_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        urgent_referrals_by_case=dict(
            median_days_referral_followup=dict(
                description="Median number of days to follow-up referral / treatment for "\
                            "urgent referrals (codes A, E, B) or treatment ",
                title="Median # Days to follow up urgent referral",
                indicator_key="urgent_referral_followup_days",
            )
        ),
        followup_cases=dict(
            median_days_followup=dict(
                description="Median # of days for follow-up",
                title="Median # of days for follow-up",
                indicator_key="urgent_followup_days",
            )
        )
    )
)