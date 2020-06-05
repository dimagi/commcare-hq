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
    "Children Eligible to have their height Measured", "Total number of children that were heighed in the month",
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


class PoshanProgressReport(object):
    title = 'Poshan Progress Report'

    def __init__(self, config, loc_level=0, beta=False, show_test=False):
        self.config = config
        self.loc_level = loc_level
        self.beta = beta
        self.show_test = show_test
        self.layout = self.config['report_layout']
        if self.config['data_format'] == 1:
            self.report_type = 'month'
        else:
            self.report_type = 'quarter'
            self.quarter = self.config['quarter']
            self.year = self.config['year']

    def _generate_quarter_years(self):
        months = []
        end_month = self.quarter * 3
        for i in range(end_month - 2, end_month + 1):
            months.append(date(self.year, i, 1))
        return months

    def structure_data(self, headers, cols, rows):
        """
        :param headers: headers of the excel file
        :param cols: columns mapped with headers
        :param rows: row data
        :return: list of list contain the excel rows
        """
        excel_rows = [headers]
        for row in rows:
            row_data = []
            for col in cols:
                row_data.append(row[col])
            excel_rows.append(row_data)
        return excel_rows

    def quarter_wise(self, filters, order_by):
        """
        :param filters: quaterwise filter (months in [month array])
        :param order_by: order by columns
        :return: excel_rows
        """
        query_set = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)
        cols = COLS_COMPREHENSIVE
        cols.append('district_id')  # used as key for the dict
        data = query_set.values(*cols)
        row_data_dict = {}
        dummy_row = ['', ''] + [0 for _ in range(0, len(COLS_COMPREHENSIVE) - 2)]
        headers = HEADERS_COMPREHENSIVE
        # generate a dict
        # {'disitrict_id': [contains the excel row with sum of col values for all months eg. m1+m2+m3]}
        for row in data:
            row_data = dummy_row
            for k, v in row.items():
                if k == 'state_name' or k == 'district_name':
                    row_data[COLS_COMPREHENSIVE.index(k)] = v
                elif k != 'district_id':
                    row_data[COLS_COMPREHENSIVE.index(k)] += v
            row_data_dict[row['district_id']] = row_data

        # Calculating Average
        # m1+m2+m3/3
        for k, v in row_data_dict.items():
            for col in COLS_COMPREHENSIVE[2:]:
                if col != 'state_name' and col != 'district_name':
                    row_data_dict[k][COLS_COMPREHENSIVE.index(col)] = v[COLS_COMPREHENSIVE.index(col)] / 3

        # Calculating Percentage
        # percent(current col) = 100 * (actual_value(prev col) / expected_value(prev prev col))
        for k, v in row_data_dict.items():
            i = 8
            while i < len(COLS_COMPREHENSIVE):
                row_data_dict[k][i] = 100 * (v[i - 1] / v[i - 2]) if v[i - 2] else 0
                i = i + 3

        if self.layout != 'comprehensive':
            headers = HEADERS_SUMMARY
            cols = COLS_SUMMARY
            extra_columns = list(set(COLS_COMPREHENSIVE) - set(COLS_SUMMARY))
            indexes_to_remove = [COLS_COMPREHENSIVE.index(col) for col in extra_columns]
            for k, v in row_data_dict.items():
                row_data_dict[k] = [val for j, val in enumerate(v) if j not in indexes_to_remove]

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
        if self.layout == 'comprehensive':
            cols = COLS_COMPREHENSIVE
            headers = HEADERS_COMPREHENSIVE
        else:
            cols = COLS_SUMMARY
            headers = HEADERS_SUMMARY
        data = query_set.values(*cols)
        return self.structure_data(headers, cols, data)

    def get_excel_data(self, location):
        filters = {}
        filters['aggregation_level'] = 2  # this report is needed district wise only
        if self.loc_level == 2:
            filters['district_id'] = location
        elif self.loc_level == 1:
            filters['state_id'] = location
        order_by = ('district_name', 'state_name')
        if self.report_type == 'month':
            filters['month'] = self.config['month']
            excel_rows = self.month_wise(filters, order_by)
        else:
            filters['month__in'] = self._generate_quarter_years()
            excel_rows = self.quarter_wise(filters, order_by)

        filters = [['Generated at', india_now()]]
        if location:
            locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        filters.append(['Report Layout', self.layout.title()])
        filters.append(['Data Period', self.report_type.title()])

        return [
            [
                self.title,
                excel_rows
            ],
            [
                'Export Info',
                filters
            ]
        ]
