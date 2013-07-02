from datetime import datetime, timedelta
from corehq.apps.reports.filters.base import BaseReportFilter

# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from dimagi.utils.dates import DateSpan

class DatespanFilter(BaseReportFilter):
    """
        A filter that returns a startdate and an enddate.
        This is the standard datespan filter that gets pulled into request with the decorator
        @datespan_in_request
    """
    template = "reports/filters/datespan.html"
    label = ugettext_noop("Date Range")
    slug = "datespan"
    default_days = 7
    inclusive = True

    @property
    def datespan(self):
        enddate = datetime.now(tz=self.timezone)
        if self.inclusive:
            enddate = enddate - timedelta(days=1)
        days = self.default_days - 1 if self.inclusive else self.default_days
        datespan = DateSpan.since(days, enddate=enddate, format="%Y-%m-%d", timezone=self.timezone)
        if self.request.datespan.is_valid() and self.slug == 'datespan':
            datespan.startdate = self.request.datespan.startdate
            datespan.enddate = self.request.datespan.enddate
        return datespan

    @property
    def filter_context(self):
        return {
            'datespan': self.datespan,
            'timezone': self.timezone.zone,
        }


