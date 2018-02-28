from __future__ import unicode_literals
APP_NAME = "mvp_chw_referrals"

CHW_REFERRAL_INDICATORS = dict(
    app=APP_NAME,
    indicators=dict(
        urgent_referrals_by_case=dict(
            urgent_referral_followups=dict(
                description="No. urgent referrals (codes A, E, B) or treatment receiving CHW follow-up within 2 days " \
                            "of referral / treatment during the time period",
                title="# Urgent Referrals w/ Followup within 2 days",
                indicator_key="urgent_referral_followup"
            ),
            num_late_followups=dict(
                description="# Referred / Treated receiving LATE follow-up (within 3-7 days)",
                title="# Referred / Treated receiving LATE follow-up (within 3-7 days)",
                indicator_key="urgent_referral_followup_late"
            ),
            num_none_followups=dict(
                description="# Referred / Treated receiving NO follow-up",
                title="# Referred / Treated receiving NO follow-up",
                indicator_key="urgent_referral_followup_none"
            ),
            num_urgent_referrals=dict(
                description="No. of Urgent Referrals",
                title="# Urgent Referrals",
                indicator_key="urgent_or_treatment"
            ),
        )
    )
)

# Indicators below use MedianCouchIndicatorDef

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
        )
    )
)
