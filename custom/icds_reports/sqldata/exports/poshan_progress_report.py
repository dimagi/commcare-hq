from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.const import (
    PPR_HEADERS_COMPREHENSIVE,
    PPR_HEADERS_SUMMARY,
    PPR_COLS_COMPREHENSIVE,
    PPR_COLS_SUMMARY,
    PPR_COLS_TO_FETCH,
    PPR_COLS_PERCENTAGE_RELATIONS
)
from custom.icds_reports.models.views import PoshanProgressReportView
from custom.icds_reports.utils import generate_quarter_months, calculate_percent, handle_average, apply_exclude
from custom.icds_reports.utils import india_now


class PoshanProgressReport(object):
    title = 'Poshan Progress Report'

    def __init__(self, config, loc_level=0, beta=False, show_test=False):
        self.config = config
        self.loc_level = loc_level
        self.beta = beta
        self.show_test = show_test
        self.layout = self.config['report_layout']
        self.report_type = self.config['data_period']
        self.row_constants = [
            PPR_HEADERS_COMPREHENSIVE[:], PPR_COLS_COMPREHENSIVE[:], PPR_HEADERS_SUMMARY[:], PPR_COLS_SUMMARY[:],
            PPR_COLS_TO_FETCH[:]]
        if self.report_type == 'quarter':
            self.quarter = self.config['quarter']
            self.year = self.config['year']
        if loc_level == 1:
            self.row_constants[0].remove('District Name')
            self.row_constants[1].remove('district_name')
            self.row_constants[2].remove('District Name')
            self.row_constants[3].remove('district_name')
            self.row_constants[4].remove('district_name')

    def __calculate_percentage_in_rows(self, row, all_cols):
        for k, v in PPR_COLS_PERCENTAGE_RELATIONS.items():
            num = row[all_cols.index(v[0])]
            den = row[all_cols.index(v[1])]
            extra_number = v[2] if len(v) > 2 else None
            row[all_cols.index(k)] = calculate_percent(num, den, extra_number)
            # calculation is done on decimal values
            # and then round off to nearest integer
            row[all_cols.index(v[0])] = round(row[all_cols.index(v[0])])
            row[all_cols.index(v[1])] = round(row[all_cols.index(v[1])])
        return row

    def quarter_wise(self, filters, order_by, aggregation_level):
        """
        :param filters: quaterwise filter (months in [month array])
        :param order_by: order by columns
        :return: excel_rows
        """
        headers_comprehensive, cols_comprehensive, headers_summary, cols_summary, cols_to_fetch = self.row_constants
        query_set = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)
        if not self.show_test:
            query_set = apply_exclude(self.config['domain'], query_set)
        all_cols = list(set(cols_comprehensive + cols_to_fetch))

        # it used to uniquely identify the row
        # for district wise data we need district id
        # for statewise we need state id
        unique_id = 'district_id'
        if aggregation_level == 1:
            unique_id = 'state_id'
        cols = cols_to_fetch[:]
        cols.append(unique_id)  # used as key for the dict
        data = query_set.values(*cols)
        row_data_dict = {}
        dummy_row = [0 for _ in range(0, len(all_cols))]
        # update the dict
        # {'unique_id': [contains the excel row with sum of col values for all months eg. m1+m2+m3]}
        for row in data:
            if row[unique_id] not in row_data_dict.keys():
                row_data_dict[row[unique_id]] = dummy_row[:]
            row_data = row_data_dict[row[unique_id]][:]
            for k, v in row.items():
                if k in ['state_name', 'district_name']:
                    row_data[all_cols.index(k)] = v
                elif k != unique_id:
                    row_data[all_cols.index(k)] += v if v else 0
            row_data_dict[row[unique_id]] = row_data

        # stores names and ids not numbers like state_name, id
        named_cols = ['state_name', 'district_name', unique_id]
        total_row = [0 for _ in range(0, len(all_cols))]

        # calculating average and getting total row
        # m1+m2+m3/3
        for k, v in row_data_dict.items():
            for col in all_cols:
                if col not in named_cols:
                    val = v[all_cols.index(col)]
                    val = handle_average(val)
                    row_data_dict[k][all_cols.index(col)] = val
                    total_row[all_cols.index(col)] += round(val) if val else 0
                else:
                    total_row[all_cols.index(col)] = 'Total'

        row_data_dict['total_row'] = total_row

        # calculating percentage
        # percent(current col) = 100 * (actual_value(prev col) / expected_value(prev prev col))
        for k, v in row_data_dict.items():
            row = v[:]
            row_data_dict[k] = self.__calculate_percentage_in_rows(row, all_cols)
            # rounding remaining values (not used to calculate percentage)
            for col in ['num_launched_districts', 'num_launched_blocks']:
                row_data_dict[k][all_cols.index(col)] = round(row_data_dict[k][all_cols.index(col)])
            # marking all the unlaunched states as Not Launched
            if row_data_dict[k][all_cols.index('num_launched_awcs')] == 0:
                for col in all_cols:
                    if col not in named_cols:
                        row_data_dict[k][all_cols.index(col)] = 'Not Launched'

        # for district wise the number of launched districts are always one
        # so removing this column from report
        if aggregation_level == 2:
            headers_summary.remove('Number of Districts Covered')
            headers_comprehensive.remove('Number of Districts Covered')
            cols_summary.remove('num_launched_districts')
            cols_comprehensive.remove('num_launched_districts')

        if self.layout != 'comprehensive':
            headers = headers_summary
            for k, v in row_data_dict.items():
                row_data_dict[k] = [v[all_cols.index(column)] for column in cols_summary]
        else:
            headers = headers_comprehensive
            for k, v in row_data_dict.items():
                row_data_dict[k] = [v[all_cols.index(column)] for column in cols_comprehensive]

        excel_rows = [headers]
        for _, v in row_data_dict.items():
            excel_rows.append(v)
        return excel_rows

    def month_wise(self, filters, order_by, aggregation_level):
        """
        :param filters: monthwise filter [month=month]
        :param order_by: order by columns
        :return: excel_rows
        """
        query_set = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)
        if not self.show_test:
            query_set = apply_exclude(self.config['domain'], query_set)
        headers_comprehensive, cols_comprehensive, headers_summary, cols_summary, cols_to_fetch = self.row_constants
        data = query_set.values(*cols_to_fetch)
        all_cols = list(set(cols_comprehensive + cols_to_fetch))
        excel_rows = [headers_comprehensive]
        dummy_row = [0 for _ in range(0, len(all_cols))]
        total_row = [0 for _ in range(0, len(all_cols))]
        for row in data:
            row_data = dummy_row[:]
            for col in cols_to_fetch:
                row_data[all_cols.index(col)] = row[col]
                if col not in ['state_name', 'district_name']:
                    total_row[all_cols.index(col)] += row[col] if row[col] else 0
                else:
                    total_row[all_cols.index(col)] = 'Total'
            excel_rows.append(row_data)
        excel_rows.append(total_row)
        # calcuating percentage for all rows
        for i in range(1, len(excel_rows)):
            row = excel_rows[i][:]
            excel_rows[i] = self.__calculate_percentage_in_rows(row, all_cols)
            # marking all the unlaunched states as Not Launched
            if excel_rows[i][all_cols.index('num_launched_awcs')] == 0:
                for col in all_cols:
                    if col not in ['state_name', 'district_name']:
                        excel_rows[i][all_cols.index(col)] = 'Not Launched'
        # for district wise the number of launched districts are always one
        # so removing this column from report
        if aggregation_level == 2:
            headers_summary.remove('Number of Districts Covered')
            headers_comprehensive.remove('Number of Districts Covered')
            cols_summary.remove('num_launched_districts')
            cols_comprehensive.remove('num_launched_districts')

        if self.layout != 'comprehensive':
            excel_rows[0] = headers_summary
            for i in range(1, len(excel_rows)):
                val = excel_rows[i][:]
                excel_rows[i] = [val[all_cols.index(column)] for column in cols_summary]
        else:
            excel_rows[0] = headers_comprehensive
            for i in range(1, len(excel_rows)):
                val = excel_rows[i][:]
                excel_rows[i] = [val[all_cols.index(column)] for column in cols_comprehensive]

        return excel_rows

    def _quarter_name(self, quarter):
        quarter_months = ''
        if quarter == 1:
            quarter_months = 'January-March'
        elif quarter == 2:
            quarter_months = 'April-June'
        elif quarter == 3:
            quarter_months = 'July-September'
        elif quarter == 4:
            quarter_months = 'July-September'
        return quarter_months

    def get_excel_data(self, location):
        aggregation_level = self.loc_level
        filters = {}
        filters['aggregation_level'] = aggregation_level  # this report is needed district wise only
        export_filters = [['Generated at', india_now()]]
        if location:
            try:
                locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
                for loc in locs:
                    export_filters.append([loc.location_type.name.title(), loc.name])
                    location_key = '%s_id' % loc.location_type.code
                    filters.update({
                        location_key: loc.location_id,
                    })
            except SQLLocation.DoesNotExist:
                pass
        order_by = ('state_name', 'district_name')
        if self.report_type == 'month':
            filters['month'] = self.config['month']
            excel_rows = self.month_wise(filters, order_by, aggregation_level)
        else:
            filters['month__in'] = generate_quarter_months(self.quarter, self.year)
            excel_rows = self.quarter_wise(filters, order_by, aggregation_level)

        export_filters.append(['Report Layout', self.layout.title()])
        export_filters.append(['Data Period', self.report_type.title()])
        if self.report_type == 'month':
            date = self.config['month']
            export_filters.append(['Month', date.strftime("%B")])
            export_filters.append(['Year', date.year])
        else:
            export_filters.append(['Quarter', self._quarter_name(int(self.quarter))])
            export_filters.append(['Year', self.year])

        return [
            [
                self.title,
                excel_rows
            ],
            [
                'Export Info',
                export_filters
            ]
        ]
