import json
from django.utils.translation import ugettext_lazy, ugettext as _
from corehq.util.dates import iso_string_to_date
from dimagi.utils.dates import DateSpan
from corehq.apps.reports.filters.base import BaseReportFilter
import datetime
from dimagi.utils.dates import add_months


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
    is_editable = True

    @property
    def datespan(self):
        datespan = DateSpan.since(self.default_days, timezone=self.timezone, inclusive=self.inclusive)
        if self.request.datespan.is_valid() and self.slug == 'datespan':
            datespan.startdate = self.request.datespan.startdate
            datespan.enddate = self.request.datespan.enddate
        return datespan

    @property
    def filter_context(self):
        return {
            'datespan': self.datespan,
            'report_labels': self.report_labels,
            'report_labels_json': self.report_labels_json,
            'separator': _(' to '),
            'timezone': self.timezone.zone,
        }

    @property
    def report_labels(self):
        return {
            'last_7_days': _('Last 7 Days'),
            'last_month': _('Last Month'),
            'last_30_days': _('Last 30 Days')
        }

    @property
    def report_labels_json(self):
        return json.dumps(self.report_labels)


class HiddenLastMonthDateFilter(DatespanFilter):
    """
    A filter that returns last month as datespan
    but is hidden since datespan should be fixed to last month
    """
    template = "reports/filters/month_datespan.html"
    label = ugettext_lazy("Date Range")
    slug = "datespan"
    inclusive = True
    is_editable = False

    @property
    def datespan(self):
        now = datetime.datetime.utcnow()
        year, month = add_months(now.year, now.month, -1)
        last_month = DateSpan.from_month(month, year)
        self.request.datespan = last_month
        self.context.update(dict(datespan=last_month))
        return last_month


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
                return iso_string_to_date(from_req)
            except ValueError:
                pass

        return datetime.date.today()

    @property
    def filter_context(self):
        return {
            'date': self.date,
        }
