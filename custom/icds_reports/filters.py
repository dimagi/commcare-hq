from datetime import datetime

from corehq.apps.reports.filters.select import MonthFilter
from dimagi.utils.decorators.memoized import memoized


class ICDSMonthFilter(MonthFilter):

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "%02d" % datetime.now().month
