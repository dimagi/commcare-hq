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


class PoshanProgressReport(object):
    title = 'Poshan Progress Report'

    def __init__(self, config, loc_level=0, beta=False, show_test=False):
        self.config = config
        self.loc_level = loc_level
        self.beta = beta
        self.show_test = show_test
        self.layout = self.config['report_layout']
        self.report_type = self.config['data_format']
        self.row_constants = [HEADERS_COMPREHENSIVE[:], COLS_COMPREHENSIVE[:], HEADERS_SUMMARY[:], COLS_SUMMARY[:]]
        if self.report_type == 'quarter':
            self.quarter = self.config['quarter']
            self.year = self.config['year']
        if loc_level == 1:
            self.row_constants[0].remove('District Name')
            self.row_constants[1].remove('district_name')
            self.row_constants[2].remove('District Name')
            self.row_constants[3].remove('district_name')

    def _generate_quarter_years(self):
        months = []
        end_month = self.quarter * 3
        for i in range(end_month - 2, end_month + 1):
            months.append(date(self.year, i, 1))
        return months

    def _indexes_to_remove(self):
        _, cols_comprehensive, _, cols_summary = self.row_constants
        extra_columns = list(set(cols_comprehensive) - set(cols_summary))
        indexes_to_remove = [cols_comprehensive.index(col) for col in extra_columns]
        return indexes_to_remove

    def quarter_wise(self, filters, order_by, aggregation_level):
        """
        :param filters: quaterwise filter (months in [month array])
        :param order_by: order by columns
        :return: excel_rows
        """
        headers_comprehensive, cols_comprehensive, headers_summary, cols_summary = self.row_constants
        query_set = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)

        # it used to uniquely identify the row
        # for district wise data we need district id
        # for statewise we need state id
        unique_id = 'district_id'
        if aggregation_level == 1:
            unique_id = 'state_id'
        cols = cols_comprehensive[:]
        cols.append(unique_id)  # used as key for the dict
        data = query_set.values(*cols)
        row_data_dict = {}
        dummy_row = ['' for _ in range(0, aggregation_level)] + [0 for _ in range(0, len(
            headers_comprehensive) - aggregation_level)]
        headers = headers_comprehensive
        # generate a dict
        # {'unique_id': [contains the excel row with sum of col values for all months eg. m1+m2+m3]}
        for row in data:
            row_data = dummy_row
            for k, v in row.items():
                if k == 'state_name' or k == 'district_name':
                    row_data[cols_comprehensive.index(k)] = v
                elif k != unique_id:
                    row_data[cols_comprehensive.index(k)] += v if v else 0
            row_data_dict[row[unique_id]] = row_data

        # calculating average
        # m1+m2+m3/3
        total_row = ['Total' for _ in range(0, aggregation_level)] + [0 for _ in range(0, len(
            headers_comprehensive) - aggregation_level)]
        for k, v in row_data_dict.items():
            for col in cols_comprehensive[2:]:
                if col != 'state_name' and col != 'district_name' and col != unique_id:
                    val = v[cols_comprehensive.index(col)]
                    row_data_dict[k][cols_comprehensive.index(col)] = val / 3 if val else 0
                    total_row[cols_comprehensive.index(col)] += val if val else 0

        row_data_dict["total_row"] = total_row

        # calculating percentage
        # percent(current col) = 100 * (actual_value(prev col) / expected_value(prev prev col))
        for k, v in row_data_dict.items():
            i = 6 + aggregation_level
            while i < len(cols_comprehensive):
                row_data_dict[k][i] = 100 * (v[i - 1] / v[i - 2]) if v[i - 2] else 0
                i = i + 3

        if self.layout != 'comprehensive':
            headers = headers_summary
            for k, v in row_data_dict.items():
                row_data_dict[k] = [val for j, val in enumerate(v) if j not in self._indexes_to_remove()]

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
        headers_comprehensive, cols_comprehensive, headers_summary, cols_summary = self.row_constants
        data = query_set.values(*cols_comprehensive)
        excel_rows = [headers_comprehensive]
        total_row = ['Total' for _ in range(0, aggregation_level)] + [0 for _ in range(0, len(
            headers_comprehensive) - aggregation_level)]
        for row in data:
            row_data = []
            for col in cols_comprehensive:
                row_data.append(row[col])
                if col != 'state_name' and col != 'district_name':
                    total_row[cols_comprehensive.index(col)] += row[col] if row[col] else 0
            excel_rows.append(row_data)
        # calcuating percentage for total row
        i = 6 + aggregation_level
        while i < len(cols_comprehensive):
            total_row[i] = 100 * (total_row[i - 1] / total_row[i - 2]) if total_row[i - 2] else 0
            i = i + 3
        excel_rows.append(total_row)

        if self.layout != 'comprehensive':
            excel_rows[0] = headers_summary
            for i in range(0, len(excel_rows)):
                excel_rows[i] = [val for j, val in enumerate(excel_rows[i]) if j not in self._indexes_to_remove()]
        excel_rows[0] = headers_summary

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
            excel_rows = self.month_wise(filters, order_by, aggregation_level)
        else:
            filters['month__in'] = self._generate_quarter_years()
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
