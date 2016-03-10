import datetime
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.util.dates import iso_string_to_date
from dimagi.utils.dates import DateSpan
import json
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.dont_use.fields import ReportField


class DateRangeField(DatespanFilter):
    name = ugettext_noop("Date Range")
    template = 'm4change/fields/daterange.html'
    slug = "datespan"
    inclusive = True
    default_days = 30

    @property
    def report_labels(self):
        return json.dumps({
            'year_to_date': _('Year to Date'),
            'last_month': _('Last Month'),
            'last_quarter': _('Last Quarter'),
            'last_two_quarters': _('Last Two Quarters'),
            'last_three_quarters': _('Last Three Quarters'),
            'last_year': _('Last Year'),
            'last_two_years': _('Last Two Years'),
            'last_three_years': _('Last Three Years'),
            'last_four_years': _('Last Four Years')
        })


class CaseSearchField(ReportField):
    name = ugettext_noop("Case Search")
    slug = "case_search"
    template = "reports/filters/bootstrap2/search.html"

    def update_context(self):
        self.search_query = self.request.GET.get("case_search", "")
        self.context["search_query"] = self.search_query
        self.context["label"] = _("Case Search")
