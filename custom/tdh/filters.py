from corehq.apps.reports.filters.dates import DatespanFilter


class TDHDateSpanFilter(DatespanFilter):
    default_days = 7
