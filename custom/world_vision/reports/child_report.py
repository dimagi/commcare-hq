from corehq.apps.reports.filters.dates import DatespanFilter
from custom.world_vision.reports import TTCReport
from custom.world_vision.filters import LocationFilter
from custom.world_vision.sqldata.child_sqldata import ImmunizationDetailsFirstYear, ImmunizationDetailsSecondYear, \
    ChildDeworming
from dimagi.utils.decorators.memoized import memoized


class ChildTTCReport(TTCReport):
    report_title = 'Child Report'
    name = 'Child Report'
    title = 'Child Report'
    slug = 'child_report'
    fields = [DatespanFilter, LocationFilter]
    default_rows = 25
    exportable = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ImmunizationDetailsFirstYear(config=config),
            ImmunizationDetailsSecondYear(config=config),
            ChildDeworming(config=config),
        ]