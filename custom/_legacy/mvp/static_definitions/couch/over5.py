OVER5_HEALTH_INDICATORS = dict(
    app="mvp_over5",
    indicators=dict(
        over5_health=dict(
            over5_positive_rdt=dict(
                description="No. Over5 who received positive RDT Result",
                title="# Over5 who received positive RDT Result",
                indicator_key="over5_positive_rdt"
            ),
            over5_positive_rdt_medicated=dict(
                description="No. Over5 who received positive RDT Result and were given anti-malarials",
                title="# Over5 who received positive RDT Result and were given anti-malarials",
                indicator_key="over5_positive_rdt_medicated"
            ),
        ),
    )
)
