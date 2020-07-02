from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED
from custom.icds_reports.models.views import TakeHomeRationMonthly
from custom.icds_reports.models.views import ServiceDeliveryReportView
from custom.icds_reports.const import (
    THR_REPORT_BENEFICIARY_TYPE,
    THR_REPORT_DAY_BENEFICIARY_TYPE,
    THR_21_DAYS_THRESHOLD_DATE
)
from custom.icds_reports.utils import apply_exclude

class TakeHomeRationExport(object):
    title = 'Take Home Ration'

    def __init__(self, domain, location, month, loc_level=0, beta=False, report_type='consolidated'):
        self.domain = domain
        self.location = location
        self.loc_level = loc_level
        self.month = month
        self.beta = beta
        self.report_type = report_type

    def get_excel_data(self):
        def _format_report_data(column, value, is_launched):
            location_names = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
            AWC_NOT_LAUNCHED = 'AWC Not Launched'
            if column in location_names:
                return value
            elif not is_launched:
                return AWC_NOT_LAUNCHED
            else:
                return value if value is not None else DATA_NOT_ENTERED

        filters = {"month": self.month, "aggregation_level": 5}

        if self.loc_level == 4:
            filters['supervisor_id'] = self.location
            order_by = ('awc_name',)
        elif self.loc_level == 3:
            filters['block_id'] = self.location
            order_by = ('supervisor_name', 'awc_name')
        elif self.loc_level == 2:
            filters['district_id'] = self.location
            order_by = ('block_name', 'supervisor_name', 'awc_name')
        elif self.loc_level == 1:
            filters['state_id'] = self.location
            order_by = ('district_name', 'block_name', 'supervisor_name', 'awc_name')
        else:
            order_by = ('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name')

        if self.report_type == THR_REPORT_BENEFICIARY_TYPE:
            headers, data = self.get_beneficiary_wise_data(filters, order_by)
        elif self.report_type == THR_REPORT_DAY_BENEFICIARY_TYPE:
            headers, data = self.get_beneficiary_and_days_wise_data(filters, order_by)
        else:
            headers, data = self.get_consolidated_data(filters, order_by)

        #Exclude test states
        data = apply_exclude(self.domain, data)
        excel_rows = [headers]

        for row in data:
            awc_is_launched = row.get('is_launched') == 'yes' or row.get('num_launched_awcs') == 1
            row_data = [_format_report_data(column_name, col_values, awc_is_launched)
                        for column_name, col_values in row.items() if column_name not in ('num_launched_awcs',
                                                                                          'is_launched')]
            excel_rows.append(row_data)
        filters = [['Generated at', india_now()]]
        if self.location:
            locs = SQLLocation.objects.get(location_id=self.location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        else:
            filters.append(['Location', 'National'])

        date = self.month
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

    def get_consolidated_data(self, filters, order_by):
        thr_days = 21 if self.month <= THR_21_DAYS_THRESHOLD_DATE else 25
        thr_column = f'thr_{thr_days}_days'
        launched_column = 'num_launched_awcs'
        thr_eligible_column = 'thr_eligible'
        class_model = ServiceDeliveryReportView

        headers = ['State', 'District', 'Block', 'Sector', 'Awc Name', 'AWW Name', 'AWW Phone No.',
                   'Total No. of Beneficiaries eligible for THR',
                   f'Total No. of beneficiaries received THR for at least {thr_days} days in given month',
                   'Total No of Pictures taken by AWW']

        columns = [
            'state_name', 'district_name', 'block_name',
            'supervisor_name', 'awc_name', 'aww_name', 'contact_phone_number',
            launched_column,
            thr_eligible_column,
            thr_column,
            'thr_distribution_image_count'
        ]

        query_set = class_model.objects.filter(**filters).order_by(*order_by)
        data = query_set.values(*columns)
        return headers, data

    def get_beneficiary_wise_data(self, filters, order_by):

        thr_days = '21' if self.month <= THR_21_DAYS_THRESHOLD_DATE else '25'

        headers = ['State', 'District', 'Block', 'Sector', 'Awc Name', 'AWW Name', 'AWW Phone No.',
                   'Total No. of PW eligible for THR',
                   'Total No. of LW eligible for THR',
                   'Total No. of Children(6-36 months) eligible for THR',
                   f'Total No. of PW received THR>={thr_days} days in given month',
                   f'Total No. of LW received THR>={thr_days} days in given month',
                   f'Total No. of Children(6-36 months) received THR>={thr_days} days in given month',
                   'Total No of Pictures taken by AWW']

        columns = ['state_name', 'district_name', 'block_name',
                   'supervisor_name', 'awc_name', 'aww_name', 'contact_phone_number',
                   'num_launched_awcs',
                   'pw_thr_eligible',
                   'lw_thr_eligible',
                   'child_thr_eligible',
                   f'pw_thr_{thr_days}_days',
                   f'lw_thr_{thr_days}_days',
                   f'child_thr_{thr_days}_days',
                   'thr_distribution_image_count']
        query_set = ServiceDeliveryReportView.objects.filter(**filters).order_by(*order_by)
        data = query_set.values(*columns)
        return headers, data

    def get_beneficiary_and_days_wise_data(self, filters, order_by):
        headers = ['State', 'District', 'Block', 'Sector', 'Awc Name', 'AWW Name', 'AWW Phone No.',
                   'Total No. of PW eligible for THR',
                   'Total No. of LW eligible for THR',
                   'Total No. of Children (0-3 years) eligible for THR',
                   'Total No. of PW did not received THR in given month',
                   'Total No. of LW did not received THR in given month',
                   'Total No. of Children (0-3 years) did not received THR in given month',
                   'Total No. of PW received THR for 1-7 days in given month',
                   'Total No. of LW received THR for 1-7 days in given month',
                   'Total No. of Children (0-3 years) received THR for 1-7 days in given month',
                   'Total No. of PW received THR for 8-14 days in given month',
                   'Total No. of LW received THR for 8-14 days in given month',
                   'Total No. of Children (0-3 years) received THR for 8-14 days in given month',
                   'Total No. of PW received THR for 15-20 days in given month',
                   'Total No. of LW received THR for 15-20 days in given month',
                   'Total No. of Children (0-3 years) received THR for 15-20 days in given month',
                   'Total No. of PW received THR for 21-24 days in given month',
                   'Total No. of LW received THR for 21-24 days in given month',
                   'Total No. of Children (0-3 years) received THR for 21-24 days in given month',
                   'Total No. of PW received THR>=25 days in given month',
                   'Total No. of LW received THR>=25 days in given month',
                   'Total No. of Children(0-3 years) received THR>=25 days in given month',
                   'Total No of Pictures taken by AWW']

        columns = ['state_name', 'district_name', 'block_name',
                   'supervisor_name', 'awc_name',
                   'aww_name', 'contact_phone_number',
                   'num_launched_awcs', 'pw_thr_eligible',
                   'lw_thr_eligible',
                   'child_thr_eligible',
                   'pw_thr_0_days',
                   'lw_thr_0_days',
                   'child_thr_0_days',
                   'pw_thr_1_7_days',
                   'lw_thr_1_7_days',
                   'child_thr_1_7_days',
                   'pw_thr_8_14_days',
                   'lw_thr_8_14_days',
                   'child_thr_8_14_days',
                   'pw_thr_15_20_days',
                   'lw_thr_15_20_days',
                   'child_thr_15_20_days',
                   'pw_thr_21_24_days',
                   'lw_thr_21_24_days',
                   'child_thr_21_24_days',
                   'pw_thr_25_days',
                   'lw_thr_25_days',
                   'child_thr_25_days',
                   'thr_distribution_image_count'
                   ]
        query_set = ServiceDeliveryReportView.objects.filter(**filters).order_by(*order_by)
        data = query_set.values(*columns)
        return headers, data
