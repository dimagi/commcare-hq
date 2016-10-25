from datetime import datetime

from corehq.apps.reports.filters.fixtures import AsyncDrillableFilter
from corehq.apps.reports.filters.select import MonthFilter
from dimagi.utils.decorators.memoized import memoized


class ICDSMonthFilter(MonthFilter):

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "%02d" % datetime.now().month


class IcdsLocationFilter(AsyncDrillableFilter):
    slug = 'icds'
    label = 'Location'
    example_hierarchy = [
        {"type": "state", "display": "name"},
        {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},
        {"type": "block", "parent_ref": "district_id", "references": "id", "display": "name"}
    ]
