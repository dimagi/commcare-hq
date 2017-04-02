import re
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from corehq.apps.reports.util import format_datatables_data
from custom.up_nrhm.filters import HierarchySqlData
from custom.up_nrhm.reports.block_level_month_report import BlockLevelMonthReport
from custom.up_nrhm.sql_data import ASHAFacilitatorsData
from django.utils.translation import ugettext as _, ugettext_noop


class BlockLevelAFReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    name = ugettext_noop("Format-4 Block Consolidation of the functionality status")
    slug = "block_level_month_wise"

    def get_afs_for_block(self):
        afs = []
        for location in HierarchySqlData(config={'domain': self.domain}).get_data():
            if location['block'] == self.report_config['block']:
                afs.append([(u"%s %s" % (location['first_name'] or '', location['last_name'] or '')).strip(),
                            location['doc_id']])
        return afs

    @property
    def headers(self):
        columns = [DataTablesColumn(_('ASHA Sanginis'), sortable=False)]
        columns.extend([DataTablesColumn(af[0], sortable=False) for af in self.get_afs_for_block()])
        columns.append(DataTablesColumn(_('Total of the block'), sortable=False))
        return DataTablesHeader(*columns)

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'year': self.request.GET.get('year'),
            'month': self.request.GET.get('month'),
            'block': self.request.GET.get('hierarchy_block'),
            'is_checklist': 1
        }

    @property
    def model(self):
        return ASHAFacilitatorsData(config=self.report_config)

    @property
    def rows(self):
        rows = [[column.header] for column in self.model.columns[2:]]
        rows.append([_("<b>Total number of ASHAs who did not report/not known</b>")])
        last_row = [_("<b>Total Number of ASHAs under each Facilitator</b>")]
        sums = [0] * len(rows)
        total = 0
        sum_row_10 = 0
        denom_row_10 = 0
        for af in self.get_afs_for_block():
            self.request_params['hierarchy_af'] = af[1]
            q = self.request.GET.copy()
            q['hierarchy_af'] = af[1]
            self.request.GET = q
            rs, afs_count = BlockLevelMonthReport(self.request, domain=self.domain).rows
            total += afs_count
            last_row.append(format_datatables_data(afs_count, afs_count))
            for index, row in enumerate(rs):
                rows[index].append(row[-1])
                if index == 10:
                    numbers = re.split('/|\s|%', row[-1]['html'])
                    sum_row_10 += int(numbers[0])
                    denom_row_10 += int(numbers[1])
                else:
                    sums[index] += float(row[-1]['sort_key'])

        for index, sum in enumerate(sums):
            if index == 10:
                try:
                    percent = sum_row_10 * 100 / denom_row_10
                except ZeroDivisionError:
                    percent = 0
                html = "{0}/{1} ({2}%)".format(sum_row_10, denom_row_10, percent)
                rows[index].append(format_datatables_data(html, percent))
            else:
                rows[index].append(format_datatables_data(sum, sum))

        last_row.append(format_datatables_data(total, total))
        rows.append(last_row)
        return rows, total
