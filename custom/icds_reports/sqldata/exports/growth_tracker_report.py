import gevent

from dateutil.relativedelta import relativedelta

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models import ChildHealthMonthlyView
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils import get_status, calculate_date_for_age, \
    current_month_stunting_column, \
    current_month_wasting_column, phone_number_function, india_now
from custom.icds_reports.utils.mixins import ExportableMixin


class GrowthTrackerExport(ExportableMixin, IcdsSqlData):
    title = 'Child Growth Tracking'
    table_name = 'child_health_monthly_view'

    def get_excel_data(self, location):

        def _check_case_presence(case_id, column, data_dict):
            return data_dict[case_id][column] if case_id in data_dict.keys() else "N/A"

        def _fetch_data(query_filter):
            filters = query_filter['filters']
            order_by = query_filter['order_by']
            case_by_grouping = query_filter['case_by_grouping']
            query_set = ChildHealthMonthlyView.objects.filter(**filters).order_by(*order_by)
            data_month = query_set.values('state_name', 'district_name', 'block_name', 'supervisor_name',
                                          'awc_name', 'awc_site_code', 'person_name', 'dob', 'mother_name',
                                          'mother_phone_number', 'pse_days_attended', 'lunch_count',
                                          'current_month_nutrition_status',
                                          current_month_stunting_column(None),
                                          current_month_wasting_column(None), 'case_id')
            if case_by_grouping is True:
                data_month = {item['case_id']: item for item in data_month}
            return data_month

        filters = {
            "month": self.config['month'],
            "age_in_months__lte": 72,
            "valid_in_month": 1
        }
        initial_month = self.config['month']

        if self.loc_level == 5:
            filters['awc_id'] = location
            order_by = ('person_name',)
        elif self.loc_level == 4:
            filters['supervisor_id'] = location
            order_by = ('awc_name', 'person_name')
        elif self.loc_level == 3:
            filters['block_id'] = location
            order_by = ('supervisor_name', 'awc_name', 'person_name')
        elif self.loc_level == 2:
            filters['district_id'] = location
            order_by = ('block_name', 'supervisor_name', 'awc_name', 'person_name')
        query_filters = [{"filters": filters, "order_by": order_by, "case_by_grouping": False}]
        filters = filters.copy()
        filters["month"] = initial_month - relativedelta(months=1)
        query_filters.append({"filters": filters, "order_by": order_by, "case_by_grouping": True})
        filters = filters.copy()
        filters["month"] = initial_month - relativedelta(months=2)
        query_filters.append({"filters": filters, "order_by": order_by, "case_by_grouping": True})
        jobs = [gevent.spawn(_fetch_data, query_filter) for query_filter in query_filters]
        gevent.joinall(jobs, timeout=120)
        data_month_3, data_month_2, data_month_1 = [job.value for job in jobs]
        filters["month"] = initial_month
        month_1 = (initial_month - relativedelta(months=2)).strftime('%B %Y')
        month_2 = (initial_month - relativedelta(months=1)).strftime('%B %Y')
        month_3 = initial_month.strftime('%B %Y')

        headers = ['State', 'District', 'Block', 'Sector', 'Awc Name', 'Child', 'Age', 'Mother Name',
                   'Mother Phone Number', f'PSE_{month_1}', f'PSE_{month_2}', f'PSE_{month_3}', f'SN_{month_1}',
                   f'SN_{month_2}', f'SN_{month_3}', f'Stunting_{month_1}', f'Stunting_{month_2}',
                   f'Stunting_{month_3}', f'Wasting_{month_1}', f'Wasting_{month_2}', f'Wasting_{month_3}',
                   f'underweight_{month_1}', f'underweight_{month_2}', f'underweight_{month_3}']

        excel_rows = [headers]

        for row in data_month_3:
            row_data = [
                row['state_name'],
                row['district_name'],
                row['block_name'],
                row['supervisor_name'],
                row['awc_name'],
                row['person_name'],
                calculate_date_for_age(row['dob'], initial_month),
                row['mother_name'],
                phone_number_function(row['mother_phone_number']),
                _check_case_presence(row['case_id'], 'pse_days_attended', data_month_1),
                _check_case_presence(row['case_id'], 'pse_days_attended', data_month_2),
                row['pse_days_attended'],
                _check_case_presence(row['case_id'], 'lunch_count', data_month_1),
                _check_case_presence(row['case_id'], 'lunch_count', data_month_2),
                row['lunch_count'],
                get_status(
                    _check_case_presence(row['case_id'], current_month_stunting_column(self.beta),
                                         data_month_1),
                    'stunted',
                    'Normal height for age',
                    True
                ),
                get_status(
                    _check_case_presence(row['case_id'], current_month_stunting_column(self.beta),
                                         data_month_2),
                    'stunted',
                    'Normal height for age',
                    True
                ),
                get_status(
                    row[current_month_stunting_column(self.beta)],
                    'stunted',
                    'Normal height for age',
                    True
                ),
                get_status(
                    _check_case_presence(row['case_id'], current_month_wasting_column(self.beta),
                                         data_month_1),
                    'wasted',
                    'Normal weight for height',
                    True
                ),
                get_status(
                    _check_case_presence(row['case_id'], current_month_wasting_column(self.beta), data_month_2),
                    'wasted',
                    'Normal weight for height',
                    True
                ),
                get_status(
                    row[current_month_wasting_column(self.beta)],
                    'wasted',
                    'Normal weight for height',
                    True
                ),
                get_status(
                    _check_case_presence(row['case_id'], 'current_month_nutrition_status', data_month_1),
                    'underweight',
                    'Normal weight for age',
                    True
                ),
                get_status(
                    _check_case_presence(row['case_id'], 'current_month_nutrition_status', data_month_2),
                    'underweight',
                    'Normal weight for age',
                    True
                ),
                get_status(
                    row['current_month_nutrition_status'],
                    'underweight',
                    'Normal weight for age',
                    True
                )
            ]
            excel_rows.append(row_data)
        filters = [['Generated at', india_now()]]
        if location:
            locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])

        date = self.config['month']
        filters.append(['Month', date.strftime("%B")])
        filters.append(['Year', date.year])

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
