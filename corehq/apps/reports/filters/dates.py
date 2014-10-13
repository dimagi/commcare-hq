from corehq.apps.reports.filters.base import BaseReportFilter

# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from dimagi.utils.dates import DateSpan

class DatespanFilter(BaseReportFilter):
    """
        A filter that returns a startdate and an enddate.
        This is the standard datespan filter that gets pulled into request with the decorator
        @datespan_in_request
    """
    template = "reports/filters/datespan.html"
    label = ugettext_lazy("Date Range")
    slug = "datespan"
    default_days = 7
    default_from_text = ugettext_lazy("From")
    default_to_text = ugettext_lazy("To")
    show_startdate = True
    show_enddate = True

    @property
    def datespan(self):
        datespan = DateSpan.since(self.default_days, format="%Y-%m-%d", timezone=self.timezone)
        if self.request.datespan.is_valid() and self.slug == 'datespan':
            datespan.startdate = self.request.datespan.startdate
            datespan.enddate = self.request.datespan.enddate
        return datespan

    @property
    def filter_context(self):
        return {
            'datespan': self.datespan,
            'timezone': self.timezone.zone,
            'default_from_text': self.default_from_text, 
            'default_to_text': self.default_to_text, 
            'show_startdate': self.show_startdate, 
            'show_enddate': self.show_enddate,
        }
