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
        stunting_column = current_month_stunting_column(self.beta)
        wasting_column = current_month_wasting_column(self.beta)

        def _generate_months(month):
            months = []
            for i in range(0, 3):
                months.append(month)
                month = month - relativedelta(months=1)
            months.reverse()
            return months

        filters = {
            "month__in": _generate_months(self.config['month']),
            "age_in_months__lte": 72,
            "valid_in_month": 1
        }
        data_month_1, data_month_2, data_month_3 = _generate_months(self.config['month'])

        if self.loc_level == 5:
            filters['awc_id'] = location
            order_by = ('-month', 'person_name')
        elif self.loc_level == 4:
            filters['supervisor_id'] = location
            order_by = ('-month', 'awc_name', 'person_name')
        elif self.loc_level == 3:
            filters['block_id'] = location
            order_by = ('-month', 'supervisor_name', 'awc_name', 'person_name')
        elif self.loc_level == 2:
            filters['district_id'] = location
            order_by = ('-month', 'block_name', 'supervisor_name', 'awc_name', 'person_name')
        query_set = ChildHealthMonthlyView.objects.filter(**filters).order_by(*order_by)
        data_rows = query_set.values('state_name', 'district_name', 'block_name', 'supervisor_name',
                                     'awc_name', 'awc_site_code', 'person_name', 'dob', 'mother_name',
                                     'mother_phone_number', 'pse_days_attended', 'lunch_count',
                                     'current_month_nutrition_status', stunting_column, wasting_column,
                                     'case_id', 'month')
        month_1 = data_month_1.strftime('%B %Y')
        month_2 = data_month_2.strftime('%B %Y')
        month_3 = data_month_3.strftime('%B %Y')

        headers = ['State', 'District', 'Block', 'Sector', 'Awc Name', 'Child', 'Age', 'Mother Name',
                   'Mother Phone Number', f'PSE_{month_1}', f'PSE_{month_2}', f'PSE_{month_3}', f'SN_{month_1}',
                   f'SN_{month_2}', f'SN_{month_3}', f'Stunting_{month_1}', f'Stunting_{month_2}',
                   f'Stunting_{month_3}', f'Wasting_{month_1}', f'Wasting_{month_2}', f'Wasting_{month_3}',
                   f'underweight_{month_1}', f'underweight_{month_2}', f'underweight_{month_3}']

        excel_rows = [headers]
        dummy_row = ["N/A" for _ in range(0, len(headers))]
        final_dict = {}
        for row in data_rows:
            month = row['month']
            case_id = row['case_id']
            if case_id not in final_dict.keys():
                final_dict[case_id] = dummy_row[:]
            if month == data_month_3:
                final_dict[case_id][0] = row['state_name']
                final_dict[case_id][1] = row['district_name']
                final_dict[case_id][2] = row['block_name']
                final_dict[case_id][3] = row['supervisor_name']
                final_dict[case_id][4] = row['awc_name']
                final_dict[case_id][5] = row['person_name']
                final_dict[case_id][6] = calculate_date_for_age(row['dob'], data_month_3)
                final_dict[case_id][7] = row['mother_name']
                final_dict[case_id][8] = phone_number_function(row['mother_phone_number'])
            k = 11
            if month == data_month_2:
                k = 10
            elif month == data_month_1:
                k = 9

            final_dict[case_id][k] = row['pse_days_attended']
            final_dict[case_id][k + 3] = row['lunch_count']
            final_dict[case_id][k + 6] = get_status(row[stunting_column], 'stunted', 'Normal height for age', True)
            final_dict[case_id][k + 9] = get_status(row[wasting_column], 'wasted', 'Normal weight for height',
                                                    True)
            final_dict[case_id][k + 12] = get_status(row['current_month_nutrition_status'], 'underweight',
                                                     'Normal weight for age', True)
        for _, v in final_dict.items():
            excel_rows.append(v)
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
