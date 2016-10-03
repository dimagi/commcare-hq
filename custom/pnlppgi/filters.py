import datetime

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from dimagi.utils.decorators.memoized import memoized


class WeekFilter(BaseSingleOptionFilter):
    slug = 'week'
    label = 'Week'

    @property
    @memoized
    def selected(self):
        return self.request.GET.get('week', datetime.datetime.utcnow().isocalendar()[1])

    @property
    def options(self):
        return [(p, p) for p in range(1, 53)]
