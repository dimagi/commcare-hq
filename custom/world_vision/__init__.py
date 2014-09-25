from custom.world_vision.reports.child_report import ChildTTCReport
from custom.world_vision.reports.mixed_report import MixedTTCReport
from custom.world_vision.reports.mother_report import MotherTTCReport

DEFAULT_URL = MixedTTCReport

WORLD_VISION_DOMAINS = ('wvindia2', )

CUSTOM_REPORTS = (
    ('TTC App Reports', (
        MixedTTCReport,
        MotherTTCReport,
        ChildTTCReport
    )),
)
