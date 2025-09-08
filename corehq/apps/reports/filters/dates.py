import datetime
import json

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from dimagi.utils.dates import DateSpan, add_months
from dimagi.utils.parsing import ISO_DATETIME_FORMAT, string_to_datetime

from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.apps.reports.util import DatatablesServerSideParams
from corehq.util.dates import iso_string_to_date


class DatespanFilter(BaseReportFilter):
    """
        A filter that returns a startdate and an enddate.
        This is the standard datespan filter that gets pulled into request with the decorator
        @datespan_in_request
    """
    template = "reports/filters/bootstrap3/datespan.html"
    label = gettext_lazy("Date Range")
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
    template = "reports/filters/bootstrap3/month_datespan.html"
    label = gettext_lazy("Date Range")
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


class DateTimeSpanFilter(BaseReportFilter):
    template = "reports/filters/bootstrap3/datetimespan.html"
    label = gettext_lazy("Date And Time Range")
    slug = "datetimespan"
    inclusive = True
    default_days = 7
    is_editable = True

    @property
    def start_datetime(self):
        start_datetime_str = self.request.GET.get(f'{self.slug}_startdatetime', '')
        if start_datetime_str:
            return string_to_datetime(start_datetime_str)
        return None

    @property
    def end_datetime(self):
        end_datetime_str = self.request.GET.get(f'{self.slug}_enddatetime', '')
        if end_datetime_str:
            return string_to_datetime(end_datetime_str)
        return None

    @property
    def datetimespan(self):
        start_dt = self.start_datetime
        end_dt = self.end_datetime

        if start_dt and end_dt:
            return DateSpan(startdate=start_dt, enddate=end_dt,
                           timezone=self.timezone, inclusive=self.inclusive, format=ISO_DATETIME_FORMAT)

        return DateSpan.since(self.default_days, timezone=self.timezone,
                              inclusive=self.inclusive, format=ISO_DATETIME_FORMAT)

    @property
    def filter_context(self):
        return {
            'datetimespan': self.datetimespan,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
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


class SingleDateFilter(BaseReportFilter):
    """
    A filter that returns a single date
    """
    template = "reports/filters/bootstrap3/date_selector.html"
    label = gettext_lazy("Date")
    slug = "date"
    # below delta should be in days from today's date
    default_date_delta = 0
    min_date_delta = None
    max_date_delta = None

    @property
    def date(self):
        from_req = DatatablesServerSideParams.get_value_from_request(self.request, self.slug)
        if from_req:
            try:
                return iso_string_to_date(from_req)
            except ValueError:
                pass

        return datetime.date.today() + datetime.timedelta(days=self.default_date_delta)

    @property
    def min_date(self):
        if self.min_date_delta:
            return datetime.date.today() + datetime.timedelta(days=self.min_date_delta)

    @property
    def max_date(self):
        if self.max_date_delta:
            return datetime.date.today() + datetime.timedelta(days=self.max_date_delta)

    @property
    def filter_context(self):
        return {
            'date': self.date,
            'min_date': self.min_date,
            'max_date': self.max_date
        }
