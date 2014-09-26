from corehq.apps.reports.filters.dates import DatespanFilter
from custom.intrahealth.filters import LocationFilter
from custom.world_vision.reports import TTCReport
from dimagi.utils.decorators.memoized import memoized
from custom.world_vision.sqldata import MotherRegistrationOverview, ClosedMotherCasesBreakdown, PregnantMotherBreakdownByTrimester, \
    AnteNatalCareServiceOverview, PostnatalCareOverview, CauseOfMaternalDeaths, ChildRegistrationDetails, \
    ClosedChildCasesBreakdown, ImmunizationOverview, ChildrenDeathDetails


class MixedTTCReport(TTCReport):
    report_title = 'Mother/Child Report'
    name = 'Mother/Child Report'
    slug = 'mother_child_report'
    title = "Mother/Child Report"
    fields = [DatespanFilter, ]
    default_rows = 10
    exportable = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            MotherRegistrationOverview(config=config),
            ClosedMotherCasesBreakdown(config=config),
            PregnantMotherBreakdownByTrimester(config=config),
            AnteNatalCareServiceOverview(config=config),
            PostnatalCareOverview(config=config),
            CauseOfMaternalDeaths(config=config),
            ChildRegistrationDetails(config=config),
            ClosedChildCasesBreakdown(config=config),
            ImmunizationOverview(config=config),
            ChildrenDeathDetails(config=config)
        ]