from custom.world_vision.reports.child_report import ChildTTCReport
from custom.world_vision.reports.mother_report import MotherTTCReport

CUSTOM_REPORTS = (
    ('TTC App Reports', (
        MotherTTCReport,
        ChildTTCReport
    )),
)
