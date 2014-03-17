DEATH_INDICATORS = dict(
    app="mvp_deaths",
    indicators=dict(
        under5_deaths=dict(
            neonatal_deaths=dict(
                description="No. of Neonatal (0-28 days) Deaths",
                title="# Neonatal Deaths",
                indicator_key="neonatal_death",
            ),
            infant_deaths=dict(
                description="No. of Infant (0-11 months) Deaths",
                title="# Infant Deaths",
                indicator_key="infant_death",
            ),
            under5_deaths=dict(
                description="No. of Under-5 (0-59 months) Deaths",
                title="# Under-5 Deaths",
                indicator_key="under5_death",
            )
        ),
        over5_deaths=dict(
            over5_deaths=dict(
                description="No. of Over-5 (non-maternal) deaths during the time period",
                title="# Over-5 (non-maternal) Deaths",
                indicator_key="over5_death",
            )
        ),
        pregnancy_close=dict(
            maternal_deaths=dict(
                description="No. of Maternal deaths (pregnant or within 42 days of delivery) during the time period",
                title="# Maternal Deaths",
                indicator_key="maternal_death",
            )
        ),
    )
)
