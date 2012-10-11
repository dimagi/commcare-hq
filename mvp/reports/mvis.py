import calendar
import datetime
from django.utils.safestring import mark_safe
import numpy
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from mvp.indicator_handlers.household import HouseholdIndicatorHandler
from mvp.indicator_handlers.under5 import Under5IndicatorHandler
from mvp.reports import MVPIndicatorReport

class HealthCoordinatorReport(MVPIndicatorReport):
    """
        MVP Custom Report: MVIS Health Coordinator
    """
    slug = "health_coordinator"
    name = "MVIS Health Coordinator Report"
    report_template_path = "mvp/reports/health_coordinator.html"

    @property
    def report_context(self):
        total_months = len(self.last_13_months)
        total_indicators = len(self.indicator_keys)
        report_matrix = [dict(indicator=i, title=None, values=[dict() for _ in range(total_months)])
                         for i in range(total_indicators)]

        month_headers = [month.startdate.strftime("%b %Y") for month in self.last_13_months]

        for month_index, month in enumerate(self.last_13_months):
            m_loc = total_months - (month_index+1)
            under5 = Under5IndicatorHandler(self.domain, self.user_ids, month)
            household = HouseholdIndicatorHandler(self.domain, self.user_ids, month)
            all_indicators = dict(under5.indicators.items() + household.indicators.items())
            for indicator_index, indicator_key in enumerate(self.indicator_keys):
                i_loc = total_indicators - (indicator_index+1)
                calc_fn = all_indicators.get(indicator_key, {}).get("get_value")
                if calc_fn is not None:
                    report_matrix[i_loc]['values'][m_loc] = calc_fn()
                if not report_matrix[i_loc].get('title'):
                    title = all_indicators.get(indicator_key, {}).get('title')
                    report_matrix[i_loc]['title'] = title

        for indicator_row in report_matrix:
            indicator_row['table'] = self._get_indicator_table(indicator_row.get('values'))
        report_matrix.reverse()
        return dict(
            months=month_headers,
            report=report_matrix
        )

    @property
    def indicator_keys(self):
        return  [
            "under5_fever_rdt",
            "under5_fever_rdt_positive",
            "under5_fever_rdt_positive_medicated",
            "under5_fever_rdt_not_received",
            "household_ontime_visit_90",
            "household_ontime_visit",
            "household_ontime_under5_visit",
            "household_ontime_neonate_visit",
            "household_ontime_pregnant_visit"
        ]

    @property
    @memoized
    def last_13_months(self):
        dates = list()
        now = datetime.datetime.utcnow()
        first_day = datetime.datetime(now.year, now.month, 1, hour=0, minute=0, second=0, microsecond=0)
        currrent_month = self._get_last_month(first_day, 0)
        dates.append(currrent_month)
        for i in range(1,13):
            this_month = self._get_last_month(first_day)
            first_day = this_month.startdate
            dates.append(this_month)
        return dates

    def _get_last_month(self, last_start, offset=7):
        current=last_start-datetime.timedelta(days=offset)
        last_day_of_month = calendar.monthrange(current.year, current.month)[1]
        return DateSpan(
            datetime.datetime(current.year, current.month, 1,
                hour=0, minute=0, second=0, microsecond=0),
            datetime.datetime(current.year, current.month, last_day_of_month,
                hour=23, minute=59, second=59, microsecond=999999),
            format="%b %Y",
            inclusive=False
        )

    def _get_indicator_table(self, indicators):
        n_row = [v.get('numerator', 0) for v in indicators]
        d_row = [v.get('denominator', 0) for v in indicators]
        r_row = [float(n_row[i])/float(d_row[i]) if d_row[i] > 0 else None for i in range(len(indicators))]

        n_stats = []
        d_stats = []
        r_stats = []
        for i in range(len(indicators)):
            if r_row[i] is not None:
                n_stats.append(n_row[i])
                d_stats.append(d_row[i])
                r_stats.append(r_row[i])

        def _get_statistics(nonzero_row):
            return [numpy.average(nonzero_row), numpy.median(nonzero_row), numpy.std(nonzero_row)]

        def _format_row(row, as_percent=False):
            formatted = list()
            num_cols = len(row)
            for i, val in enumerate(row):
                if val is not None:
                    text = "%.f%%" % (val*100) if as_percent else "%d" % int(val)
                else:
                    text = "--"

                if i == num_cols-4:
                    css = "current_month"
                elif i > num_cols-4:
                    css = "summary"
                else:
                    css = ""

                formatted.append(dict(
                    raw_value=val,
                    text=text,
                    css=css
                ))
            return formatted

        n_row.extend(_get_statistics(n_stats))
        d_row.extend(_get_statistics(d_stats))
        r_row.extend(_get_statistics(r_stats))

        return dict(
            numerators=_format_row(n_row),
            denominators=_format_row(d_row),
            percentages=_format_row(r_row, True)
        )


