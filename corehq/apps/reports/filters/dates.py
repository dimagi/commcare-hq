import simplejson
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
    inclusive = True
    default_days = 30

    @property
    def datespan(self):
        datespan = DateSpan.since(self.default_days, format="%Y-%m-%d", timezone=self.timezone, inclusive=self.inclusive)
        if self.request.datespan.is_valid() and self.slug == 'datespan':
            datespan.startdate = self.request.datespan.startdate
            datespan.enddate = self.request.datespan.enddate
        return datespan

    @property
    def filter_context(self):
        return {
            'datespan': self.datespan,
            'report_labels': self.report_labels,
            'separator': _(' to '),
            'timezone': self.timezone.zone,
        }

    @property
    def report_labels(self):
        return simplejson.dumps({
                    'year_to_date': _('Year to Date'), 'last_month': _('Last Month'),
                    'last_quarter': _('Last Quarter'), 'last_two_quarters': _('Last Two Quarters'),
                    'last_three_quarters': _('Last Three Quarters'), 'last_year': _('Last Year'),
                    'last_two_years': _('Last Two Years'), 'last_three_years': _('Last Three Years'),
                    'last_four_years': _('Last Four Years')
                })