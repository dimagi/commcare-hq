import calendar
import datetime
from dateutil.relativedelta import relativedelta
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from corehq.apps.reports.util import format_datatables_data
from custom.up_nrhm.sql_data import ASHAFacilitatorsData


class BlockLevelMonthReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    name = "Block Level-Month wise Report"
    slug = "block_level_month_wise"
    no_value = '--'

    @property
    def headers(self):
        date = self.report_config['startdate']
        first = ((date + relativedelta(months=2)).month, (date + relativedelta(months=2)).year)
        second = ((date + relativedelta(months=1)).month, (date + relativedelta(months=1)).year)
        third = (date.month, date.year)
        return DataTablesHeader(*[
            DataTablesColumn('Number of ASHAs functional on-', sortable=False),
            DataTablesColumn('%s %d' % (calendar.month_name[first[0]], first[1]), sortable=False),
            DataTablesColumn('%s %d' % (calendar.month_name[second[0]], second[1]), sortable=False),
            DataTablesColumn('%s %d' % (calendar.month_name[third[0]], third[1]), sortable=False),
            DataTablesColumn('Average', sortable=False)])

    @property
    def report_config(self):
        startdate = datetime.datetime.now()
        if not self.needs_filters:
            year = int(self.request.GET.get('year'))
            month = int(self.request.GET.get('month'))
            startdate = datetime.date(year, month, 1) - relativedelta(months=2)
        return {
            'domain': self.domain,
            'startdate': startdate,
            'af': self.request.GET.get('hierarchy_af'),
        }

    @property
    def model(self):
        return ASHAFacilitatorsData(config=self.report_config)

    @property
    def rows(self):
        def format_val(val):
            return self.no_value if val is None else val

        def avg(values):
            sum = 0
            for v in values:
                sum += v['sort_key'] if v is not None else 0
            mean = "%.1f" % (float(sum) / float(len(values)))
            return format_datatables_data(mean, mean)

        data = []
        config = self.report_config
        for i in range(0, 3):
            config['enddate'] = datetime.date(
                config['startdate'].year, config['startdate'].month,
                calendar.monthrange(config['startdate'].year, config['startdate'].month)[1])
            data.append(ASHAFacilitatorsData(config).data)
            config['startdate'] += relativedelta(months=1)

        rows = [[
            column.header,
            format_val(column.get_value(data[2])),
            format_val(column.get_value(data[1])),
            format_val(column.get_value(data[0])),
            avg([column.get_value(data[2]), column.get_value(data[1]), column.get_value(data[0])])
        ] for column in self.model.columns[2:]]

        total = [self.model.columns[0].get_raw_value(d) for d in data]
        reporting = [self.model.columns[1].get_raw_value(d) for d in data]
        not_reporting = [format_datatables_data(i - (j or 0), i - (j or 0)) for i, j in zip(total, reporting)]

        rows.append(["<b>Total number of ASHAs who did not report/not known</b>"] + not_reporting +
                    [avg(not_reporting)])
        return rows, sum(total) / len(total)
