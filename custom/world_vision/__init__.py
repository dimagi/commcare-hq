from custom.world_vision.reports.child_report import ChildTTCReport
from custom.world_vision.reports.mixed_report import MixedTTCReport
from custom.world_vision.reports.mother_report import MotherTTCReport

DEFAULT_URL = MixedTTCReport

CUSTOM_REPORTS = (
    ('TTC App Reports', (
        MixedTTCReport,
        MotherTTCReport,
        ChildTTCReport
    )),
)
