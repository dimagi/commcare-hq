import simplejson
from django.utils.translation import ugettext_lazy, ugettext as _
from dimagi.utils.dates import DateSpan
from corehq.apps.reports.filters.base import BaseReportFilter
import datetime


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
            'last_7_days': _('Last 7 Days'),
            'last_month': _('Last Month'),
            'last_30_days': _('Last 30 Days')
        })


class SingleDateFilter(BaseReportFilter):
    """
    A filter that returns a single date
    """
    template = "reports/filters/date_selector.html"
    label = ugettext_lazy("Date")
    slug = "date"

    @property
    def date(self):
        from_req = self.request.GET.get('date')
        if from_req:
            try:
                return datetime.datetime.strptime(from_req, '%Y-%m-%d').date()
            except ValueError:
                pass

        return datetime.date.today()

    @property
    def filter_context(self):
        return {
            'date': self.date,
        }
