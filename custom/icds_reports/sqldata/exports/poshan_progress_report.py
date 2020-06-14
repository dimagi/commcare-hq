from datetime import date

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models.views import PoshanProgressReportView
from custom.icds_reports.utils import india_now

HEADERS_COMPREHENSIVE = [
    "State Name", "District Name", "Number of Districts Covered", "Number of Blocks Covered",
    "Number of AWCs Launched", "% Number of Days AWC Were opened", "Expected Home Visits",
    "Actual Home Visits", "% of Home Visits", "Total Number of Children (3-6 yrs)",
    "No. of children between 3-6 years provided PSE for atleast 21+ days",
    "% of children between 3-6 years provided PSE for atleast 21+ days",
    "Children Eligible to have their weight Measured", "Total number of children that were weighed in the month",
    "Weighing efficiency", "Number of women in third trimester",
    "Number of trimester three women counselled on immediate and EBF",
    "% of trimester three women counselled on immediate and EBF",
    "Children Eligible to have their height Measured",
    "Total number of children that had their height measured in the month",
    "Height Measurement Efficiency", "Number of children between 6 months -3 years, P&LW",
    "No of children between 6 months -3 years, P&LW provided THR for atleast 21+ days",
    "% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days",
    "No. of children between 3-6 years ", "No of children between 3-6 years provided SNP for atleast 21+ days",
    "% of children between 3-6 years provided SNP for atleast 21+ days"]

COLS_COMPREHENSIVE = [
    'state_name', 'district_name', 'num_launched_districts', 'num_launched_blocks', 'num_launched_awcs',
    'avg_days_awc_open_percent', 'expected_visits', 'valid_visits', 'visits_percent', 'pse_eligible',
    'pse_attended_21_days', 'pse_attended_21_days_percent', 'wer_eligible', 'wer_weighed', 'weighed_percent',
    'trimester_3', 'counsel_immediate_bf', 'counsel_immediate_bf_percent', 'height_eligible',
    'height_measured_in_month', 'height_measured_in_month_percent', 'thr_eligible',
    'thr_rations_21_plus_distributed', 'thr_percent', 'lunch_eligible', 'lunch_count_21_days',
    'lunch_count_21_days_percent']

HEADERS_SUMMARY = [
    "State Name", "District Name", "Number of Districts Covered", "Number of Blocks Covered",
    "Number of AWCs Launched", "% Number of Days AWC Were opened", "% of Home Visits",
    "% of children between 3-6 years provided PSE for atleast 21+ days", "Weighing efficiency",
    "% of trimester three women counselled on immediate and EBF",
    "Height Measurement Efficiency",
    "% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days",
    "% of children between 3-6 years provided SNP for atleast 21+ days"]

COLS_SUMMARY = [
    'state_name', 'district_name', 'num_launched_districts', 'num_launched_blocks', 'num_launched_awcs',
    'avg_days_awc_open_percent', 'visits_percent', 'pse_attended_21_days_percent', 'weighed_percent',
    'counsel_immediate_bf_percent', 'height_measured_in_month_percent', 'thr_percent',
    'lunch_count_21_days_percent'
]

COLS_TO_FETCH = [
    'state_name', 'district_name', 'num_launched_districts', 'num_launched_blocks', 'num_launched_awcs',
    'awc_days_open', 'expected_visits', 'valid_visits', 'pse_eligible', 'pse_attended_21_days', 'wer_eligible',
    'wer_weighed', 'trimester_3', 'counsel_immediate_bf', 'height_eligible',
    'height_measured_in_month', 'thr_eligible', 'thr_rations_21_plus_distributed',
    'lunch_eligible', 'lunch_count_21_days'
]

COLS_PERCENTAGE_RELATIONS = {
    'avg_days_awc_open_percent': ['awc_days_open', 'num_launched_awcs', 25],
    'visits_percent': ['valid_visits', 'expected_visits'],
    'pse_attended_21_days_percent': ['pse_attended_21_days', 'pse_eligible'],
    'weighed_percent': ['wer_weighed', 'wer_eligible'],
    'counsel_immediate_bf_percent': ['counsel_immediate_bf', 'trimester_3'],
    'height_measured_in_month_percent': ['height_measured_in_month', 'height_eligible'],
    'thr_percent': ['thr_rations_21_plus_distributed', 'thr_eligible'],
    'lunch_count_21_days_percent': ['lunch_count_21_days', 'lunch_eligible']
}


def _generate_quarter_months(quarter, year):
    months = []
    end_month = int(quarter) * 3
    for i in range(end_month - 2, end_month + 1):
        months.append(date(year, i, 1))
    return months


def _calculate_percent(num, den, extra_number):
    if den == 0:
        ret = 0
    else:
        ret = (num / den) * 100

    if extra_number:
        ret = ret / extra_number
    return "{}%".format("%.2f" % ret)


def _handle_average(val):
    if val is None:
        ret = 0
    else:
        ret = "%.2f" % (val / 3)
    return float(ret)


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
            HEADERS_COMPREHENSIVE[:], COLS_COMPREHENSIVE[:], HEADERS_SUMMARY[:], COLS_SUMMARY[:], COLS_TO_FETCH[:]]
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
        for k, v in COLS_PERCENTAGE_RELATIONS.items():
            num = row[all_cols.index(v[0])]
            den = row[all_cols.index(v[1])]
            extra_number = v[2] if len(v) > 2 else None
            row[all_cols.index(k)] = _calculate_percent(num, den, extra_number)
        return row

    def quarter_wise(self, filters, order_by, aggregation_level):
        """
        :param filters: quaterwise filter (months in [month array])
        :param order_by: order by columns
        :return: excel_rows
        """
        headers_comprehensive, cols_comprehensive, headers_summary, cols_summary, cols_to_fetch = self.row_constants
        query_set = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)
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
        headers = headers_comprehensive
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

        # calculating average
        # m1+m2+m3/3
        total_row = [0 for _ in range(0, len(all_cols))]
        for k, v in row_data_dict.items():
            for col in all_cols[:]:
                if col not in ['state_name', 'district_name', unique_id]:
                    val = v[all_cols.index(col)]
                    row_data_dict[k][all_cols.index(col)] = _handle_average(val)
                    total_row[all_cols.index(col)] += val if val else 0
                elif col in ['state_name', 'district_name']:
                    total_row[all_cols.index(col)] = 'Total'

        row_data_dict["total_row"] = total_row

        # calculating percentage
        # percent(current col) = 100 * (actual_value(prev col) / expected_value(prev prev col))
        for k, v in row_data_dict.items():
            row = v[:]
            row_data_dict[k] = self.__calculate_percentage_in_rows(row, all_cols)

        if self.layout != 'comprehensive':
            headers = headers_summary
            for k, v in row_data_dict.items():
                row_data_dict[k] = [v[all_cols.index(column)] for column in cols_summary]
        else:
            for k, v in row_data_dict.items():
                row_data_dict[k] = [v[all_cols.index(column)] for column in cols_comprehensive]

        excel_rows = [headers]
        for _, v in row_data_dict.items():
            excel_rows.append(v)
        return excel_rows

    def month_wise(self, filters, order_by):
        """
        :param filters: monthwise filter [month=month]
        :param order_by: order by columns
        :return: excel_rows
        """
        query_set = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)
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
                row_data.append(row[col])
                if col not in ['state_name', 'district_name']:
                    total_row[all_cols.index(col)] += row[col] if row[col] else 0
                else:
                    total_row[all_cols.index(col)] = 'Total'
            excel_rows.append(row_data)
        # calcuating percentage for all rows
        for i in range(1, len(excel_rows)):
            row = excel_rows[i][:]
            excel_rows[i] = self.__calculate_percentage_in_rows(row, all_cols)
        if self.layout != 'comprehensive':
            excel_rows[0] = headers_summary
            for i in range(1, len(excel_rows)):
                val = excel_rows[i][:]
                excel_rows[i] = [val[all_cols.index(column)] for column in cols_summary]
        else:
            for i in range(1, len(excel_rows)):
                val = excel_rows[i][:]
                excel_rows[i] = [val[all_cols.index(column)] for column in cols_comprehensive]

        return excel_rows

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
            excel_rows = self.month_wise(filters, order_by)
        else:
            filters['month__in'] = _generate_quarter_months(self.quarter, self.year)
            excel_rows = self.quarter_wise(filters, order_by, aggregation_level)

        export_filters.append(['Report Layout', self.layout.title()])
        export_filters.append(['Data Period', self.report_type.title()])

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
