from sqlagg.columns import SimpleColumn
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from corehq.apps.reports.util import format_datatables_data
from custom.up_nrhm.filters import HierarchySqlData
from custom.up_nrhm.reports.block_level_af_report import BlockLevelAFReport
from custom.up_nrhm.sql_data import ASHAFacilitatorsData


class DistrictFunctionalityReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    name = "District Functionality Report"
    slug = "district_functionality_report"
    no_value = '--'

    def get_blocks_for_district(self):
        blocks = []
        for location in HierarchySqlData(config={'domain': self.domain}).get_data():
            if location['district'] == self.report_config['district']:
                blocks.append(location['block'])
        return set(blocks)

    @property
    def headers(self):
        blocks = self.get_blocks_for_district()
        headers = [DataTablesColumnGroup('')]
        headers.extend([DataTablesColumnGroup(block) for block in self.get_blocks_for_district()])
        columns = [DatabaseColumn("Percentage of ASHAs functional on "
                                  "(Number of functional ASHAs/total number of ASHAs) x 100", SimpleColumn(''),
                                  header_group=headers[0])]
        for i, block in enumerate(blocks):
            columns.append(DatabaseColumn('% of ASHAs', SimpleColumn(block), header_group=headers[i + 1]))
            columns.append(DatabaseColumn('Grade of Block', SimpleColumn(block), header_group=headers[i + 1]))
        return DataTablesHeader(*headers)

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'year': self.request.GET.get('year'),
            'month': self.request.GET.get('month'),
            'district': self.request.GET.get('hierarchy_district'),
        }

    @property
    def model(self):
        return ASHAFacilitatorsData(config=self.report_config)

    @property
    def rows(self):
        def percent(v1, v2):
            return float(v1) * 100.0 / float(v2)

        def get_grade(v):
            return 'D' if v < 25 else 'C' if v < 50 else 'B' if v < 75 else 'A'

        rows = [[column.header] for column in self.model.columns[2:]]
        rows.append(["<b>Total number of ASHAs who did not report/not known</b>"])
        rows.append(["<b>Total Number of ASHAs under each Facilitator</b>"])

        for block in self.get_blocks_for_district():
            self.request_params['hierarchy_block'] = block
            q = self.request.GET.copy()
            q['hierarchy_block'] = block
            self.request.GET = q
            rs, block_total = BlockLevelAFReport(self.request, domain=self.domain).rows
            for index, row in enumerate(rs):
                value = percent(row[-1]['sort_key'], block_total)
                grade = get_grade(value)
                if index < 10:
                    rows[index].append(format_datatables_data('%.1f%%' % value, '%.1f%%' % value))
                    rows[index].append(format_datatables_data(grade, grade))
                else:
                    rows[index].append(row[-1])
                    rows[index].append(format_datatables_data('', ''))

        return rows, 0
