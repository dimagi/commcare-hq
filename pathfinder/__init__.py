from pathfinder.models import (PathfinderHBCReport, PathfinderProviderReport,
    PathfinderWardSummaryReport)

CUSTOM_REPORTS = (
    ('Custom Reports', (
        PathfinderHBCReport,
        PathfinderProviderReport,
        PathfinderWardSummaryReport
    )),
)
