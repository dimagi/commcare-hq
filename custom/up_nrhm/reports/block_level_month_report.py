import calendar
import datetime
import re
from dateutil.relativedelta import relativedelta
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from corehq.apps.reports.util import format_datatables_data
from custom.up_nrhm.sql_data import ASHAFacilitatorsData
from django.utils.translation import ugettext as _, ugettext_noop


class BlockLevelMonthReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    name = ugettext_noop("Format-3 Block Consolidation of the functionality status")
    slug = "block_level_month_wise"
    no_value = '--'

    @property
    def headers(self):
        date = self.report_config['startdate']
        first = ((date + relativedelta(months=3)).month, (date + relativedelta(months=3)).year)
        second = ((date + relativedelta(months=2)).month, (date + relativedelta(months=2)).year)
        third = ((date + relativedelta(months=1)).month, (date + relativedelta(months=1)).year)
        return DataTablesHeader(*[
            DataTablesColumn(_('Number of ASHAs functional on-'), sortable=False),
            DataTablesColumn('%s %d' % (calendar.month_name[first[0]], first[1]), sortable=False),
            DataTablesColumn('%s %d' % (calendar.month_name[second[0]], second[1]), sortable=False),
            DataTablesColumn('%s %d' % (calendar.month_name[third[0]], third[1]), sortable=False),
            DataTablesColumn(_('Average'), sortable=False)])

    @property
    def report_config(self):
        startdate = datetime.datetime.utcnow()
        if not self.needs_filters:
            year = int(self.request.GET.get('year'))
            month = int(self.request.GET.get('month'))
            startdate = datetime.datetime(year, month, 21) - relativedelta(months=3)
        return {
            'domain': self.domain,
            'startdate': startdate.replace(hour=0, minute=0, second=0),
            'af': self.request.GET.get('hierarchy_af'),
            'is_checklist': 1
        }

    @property
    def model(self):
        return ASHAFacilitatorsData(config=self.report_config)

    @property
    def rows(self):
        def format_val(val):
            return self.no_value if val is None else val

        def avg(values, idx=None):
            sum = 0
            denom = 0
            for v in values:
                if idx == 10:
                    numbers = re.split('/|\s|%', v['html'])
                    sum += int(numbers[0])
                    if int(numbers[1]) > denom:
                        denom = int(numbers[1])
                else:
                    sum += v['sort_key'] if v is not None else 0
            mean = (float(sum) / float(len(values)))
            if idx == 10:
                try:
                    percent = mean * 100 / denom
                except ZeroDivisionError:
                    percent = 0
                html = "{0}/{1} ({2}%)".format(int(mean), int(denom), int(percent))
                return format_datatables_data(html, percent)
            mean = "%.0f" % mean
            return format_datatables_data(mean, mean)

        data = []
        config = self.report_config
        for i in range(0, 3):
            config['enddate'] = (
                config['startdate'] + relativedelta(months=1) - relativedelta(days=1)
            ).replace(hour=23, minute=59, second=59)
            data.append(ASHAFacilitatorsData(config).data)
            config['startdate'] += relativedelta(months=1)

        rows = [[
            column.header,
            format_val(column.get_value(data[2])),
            format_val(column.get_value(data[1])),
            format_val(column.get_value(data[0])),
            avg([column.get_value(data[2]), column.get_value(data[1]), column.get_value(data[0])], idx)
        ] for idx, column in enumerate(self.model.columns[2:])]

        total = [self.model.columns[0].get_raw_value(d) for d in data]
        reporting = [self.model.columns[1].get_raw_value(d) for d in data]
        not_reporting = [format_datatables_data(i - (j or 0), i - (j or 0)) for i, j in zip(total, reporting)]

        rows.append([_("<b>Total number of ASHAs who did not report/not known</b>")] + not_reporting +
                    [avg(not_reporting)])
        return rows, sum(total) / len(total)
