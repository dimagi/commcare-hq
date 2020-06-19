import copy
from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED
from custom.icds_reports.models.views import ServiceDeliveryReportView
from custom.icds_reports.utils import apply_exclude

class ServiceDeliveryReport(object):
    def __init__(self, config, location, beta=False):
        self.location = location
        self.beta = beta
        self.config = config
        if self.config['beneficiary_category'] == 'pw_lw_children':
            self.title = 'SDR - PW,LM & Children (0-3 years)'
        else:
            self.title = 'SDR - Children (3-6 years)'

    @property
    def location_columns(self):
        location_names = ['state_name', 'district_name', 'block_name', 'supervisor_name', "awc_name"]
        return location_names[:self.config['aggregation_level']]

    @property
    def headers_and_calculation(self):

        def _location_name():
            location_and_col_names = [('State', 'state_name'),
                                      ('District', 'district_name'),
                                      ('Block', 'block_name'),
                                      ('Sector', 'supervisor_name'),
                                      ('AWC', 'awc_name')]
            return location_and_col_names[:self.config['aggregation_level']]

        headers = _location_name()

        if self.config['beneficiary_category'] == 'pw_lw_children':

            if self.config['aggregation_level'] < 5:
                headers.append(
                    ('Number of AWCs launched', 'num_launched_awcs')
                )

            headers += [
                ('Number of home visits conducted by AWW', 'valid_visits'),
                ('Number of expected home visits to be conducted by the AWW', 'expected_visits'),
                ('Percentage of home visits conducted by the AWW', 'valid_visits', 'expected_visits'),
                ('Number of children (0-3 years) enrolled for Anganwadi services who were weighed', 'gm_0_3'),
                ('Total children (0-3 years) enrolled for Anganwadi services', 'children_0_3'),
                ('Percentage of children (0-3 years) enrolled for Anganwadi services who were weighed', 'gm_0_3', 'children_0_3')]

            if self.config['aggregation_level'] == 5:
                headers += [
                    ('Number of CBE conducted', 'cbe_conducted'),
                    ('Anganwadi center conducted at least 2 CBEs?', 'num_awcs_conducted_cbe'),
                    ('Number of VHSND conducted', 'vhnd_conducted'),
                    ('Anganwadi center conducted at least 1 VHSND?', 'num_awcs_conducted_vhnd')
                ]
            else:
                headers += [
                    ('Number of Anganwadi centers who have conducted at least 2 CBE', 'num_awcs_conducted_cbe'),
                    ('Total number of launched Anganwadi centers', 'num_launched_awcs'),
                    ('Percentage of Anganwadi centers who have conducted at least 2 CBE', 'num_awcs_conducted_cbe', 'num_launched_awcs'),
                    ('Number of anganwadi centers who have conducted at least 1 VHSND', 'num_awcs_conducted_vhnd')
                ]

            headers += [
                ('Number of beneficiaries to whom THR was not provided', 'thr_0_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                ('Percentage of beneficiaries to whom THR was not provided', 'thr_0_days', 'thr_eligible'),
                ('Number of beneficiaries to whom THR was provided for 1-7 days', 'thr_1_7_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                ('Percentage of beneficiaries to whom THR was provided for 1-7 days', 'thr_1_7_days', 'thr_eligible'),
                ('Number of beneficiaries to whom THR was provided for 8-14 days', 'thr_8_14_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                ('Percentage of beneficiaries to whom THR was provided for 8-14 days', 'thr_8_14_days', 'thr_eligible'),
                ('Number of beneficiaries to whom THR was provided for 15-20 days', 'thr_15_20_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                ('Percentage of beneficiaries to whom THR was provided for 15-20 days', 'thr_15_20_days', 'thr_eligible'),
                ('Number of beneficiaries to whom THR was provided for at least 21 days', 'thr_21_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                ('Percentage of beneficiaries to whom THR was provided for at least 21 days', 'thr_21_days', 'thr_eligible'),
            ]
            if self.beta:
                headers = headers[:-3]
                headers += [
                    ('Number of beneficiaries to whom THR was provided for 21-24 days', 'thr_21_24_days'),
                    ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                    ('Percentage of beneficiaries to whom THR was provided for 21-24 days', 'thr_21_24_days',
                     'thr_eligible'),
                    ('Number of beneficiaries to whom THR was provided for at least 25 days', 'thr_25_days'),
                    ('Number of beneficiaries enrolled for Anganwadi services', 'thr_eligible'),
                    ('Percentage of beneficiaries to whom THR was provided for at least 25 days', 'thr_25_days',
                     'thr_eligible'),
                ]

        else:
            headers += [
                ('Number of beneficiaries to whom hot cooked meal was not provided', 'lunch_0_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'lunch_eligible'),
                ('Percentage of beneficiaries to whom hot cooked meal was not provided', 'lunch_0_days', 'lunch_eligible'),
                ('Number of beneficiaries to whom hot cooked meal was provided for 1-7 days', 'lunch_1_7_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'lunch_eligible'),
                ('Percentage of beneficiaries to whom hot cooked meal was provided for 1-7 days', 'lunch_1_7_days', 'lunch_eligible'),
                ('Number of beneficiaries to whom hot cooked meal was provided for 8-14 days', 'lunch_8_14_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'lunch_eligible'),
                ('Percentage of beneficiaries to whom hot cooked meal was provided for 8-14 days', 'lunch_8_14_days', 'lunch_eligible'),
                ('Number of beneficiaries to whom hot cooked meal was provided for 15-20 days', 'lunch_15_20_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'lunch_eligible'),
                ('Percentage of beneficiaries to whom hot cooked meal was provided for 15-20 days', 'lunch_15_20_days', 'lunch_eligible'),
                ('Number of beneficiaries to whom hot cooked meal was provided for at least 21 days', 'lunch_21_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'lunch_eligible'),
                ('Percentage of beneficiaries to whom hot cooked meal was provided for at least 21 days', 'lunch_21_days', 'lunch_eligible'),
                ('Number of beneficiaries who did not attend pre-school education', 'pse_0_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'pse_eligible'),
                ('Percentage of beneficiaries who did not attend pre-school education', 'pse_0_days', 'pse_eligible'),
                ('Number of beneficiaries who attended pre-school education for 1-7 days', 'pse_1_7_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'pse_eligible'),
                ('Percentage of beneficiaries who attended pre-school education for 1-7 days', 'pse_1_7_days', 'pse_eligible'),
                ('Number of beneficiaries who attended pre-school education for 8-14 days', 'pse_8_14_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'pse_eligible'),
                ('Percentage of beneficiaries who attended pre-school education for 8-14 days', 'pse_8_14_days', 'pse_eligible'),
                ('Number of beneficiaries who attended pre-school education for 15-20 days', 'pse_15_20_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'pse_eligible'),
                ('Percentage of beneficiaries who attended pre-school education for 15-20 days', 'pse_15_20_days', 'pse_eligible'),
                ('Number of beneficiaries who attended pre-school education for at least 21 days','pse_21_days'),
                ('Number of beneficiaries enrolled for Anganwadi services', 'pse_eligible'),
                ('Percentage of beneficiaries who attended pre-school education for at least 21 days', 'pse_21_days', 'pse_eligible'),
                ('Number of children who were weighed', 'gm_3_5'),
                ('Total children enrolled for Anganwadi services', 'children_3_5'),
                ('Percentage of children who were weighed', 'gm_3_5', 'children_3_5')
            ]
            if self.beta:
                index = headers.index(('Number of beneficiaries to whom hot cooked meal was provided for at'
                                       ' least 21 days', 'lunch_21_days'))
                headers[index] = ('Number of beneficiaries to whom hot cooked meal was provided for at'
                                  ' 21-24 days', 'lunch_21_24_days')
                headers[index + 1] = ('Number of beneficiaries enrolled for Anganwadi services', 'lunch_eligible')
                headers[index + 2] = ('Percentage of beneficiaries to whom hot cooked meal was provided'
                                      ' for 21-24 days', 'lunch_21_24_days', 'lunch_eligible')
                headers.insert(index + 3, ('Number of beneficiaries to whom hot cooked meal was provided for at'
                                           ' least 25 days', 'lunch_25_days'))
                headers.insert(index + 4, ('Number of beneficiaries enrolled for Anganwadi services',
                                           'lunch_eligible'))
                headers.insert(index + 5, ('Percentage of beneficiaries to whom hot cooked meal was provided for'
                                           ' at least 25 days', 'lunch_25_days', 'lunch_eligible'))

                index = headers.index(('Number of beneficiaries who attended pre-school education for at'
                                       ' least 21 days', 'pse_21_days'))
                headers[index] = ('Number of beneficiaries who attended pre-school education for 21-24 days',
                                  'pse_21_24_days')
                headers[index + 1] = ('Number of beneficiaries enrolled for Anganwadi services', 'pse_eligible')
                headers[index + 2] = ('Percentage of beneficiaries who attended pre-school education'
                                      ' for 21-24 days', 'pse_21_24_days', 'pse_eligible')
                headers.insert(index + 3, ('Number of beneficiaries who attended pre-school education for at'
                                           ' least 25 days', 'pse_25_days'))
                headers.insert(index + 4, ('Number of beneficiaries enrolled for Anganwadi services',
                                           'pse_eligible'))
                headers.insert(index + 5, ('Percentage of beneficiaries who attended pre-school education for at'
                                           ' least 25 days', 'pse_25_days', 'pse_eligible'))
        return headers

    def get_excel_data(self):

        # cells under all location columns, these will be blank
        location_column_list = [''] * self.config['aggregation_level']

        # cells to contain actual grand total
        actual_value_columns_list = [0] * (
            len(self.headers_and_calculation) - self.config['aggregation_level']
        )
        total_sum_row = location_column_list + actual_value_columns_list

        total_sum_row[0] = 'Grand Total'

        def evaulate_value(row, headers_with_columns):
            row_data = []

            for index, header in enumerate(headers_with_columns):
                if len(header) == 2:
                    if header[1] in (
                        'num_awcs_conducted_cbe',
                        'num_awcs_conducted_vhnd'
                    ) and self.config['aggregation_level'] == 5:
                        row_data.append('Yes' if row[header[1]] == 1 else 'No')
                        total_sum_row[index] = 'N/A'
                    else:
                        if header[1] not in self.location_columns:
                            total_sum_row[index] += row[header[1]]
                        row_data.append(row[header[1]])
                else:
                    if row[header[2]]:
                        percentage = row[header[1]]/row[header[2]] * 100
                    else:
                        percentage = 0
                    row_data.append("{}%".format("%.2f" % percentage))

                    if total_sum_row[index - 1]:
                        percentage = (total_sum_row[index - 2] / total_sum_row[index - 1]) * 100
                    else:
                        percentage = 0
                    total_sum_row[index] = "{}%".format("%.2f" % percentage)

            return row_data

        filters = copy.deepcopy(self.config)

        del filters['beneficiary_category']
        del filters['domain']

        order_by = self.location_columns

        values = {header[1] for header in self.headers_and_calculation if len(header) == 2}
        headers = [header[0] for header in self.headers_and_calculation]

        data = ServiceDeliveryReportView.objects.filter(**filters).order_by(*order_by).values(*values)

        data = apply_exclude(self.config['domain'], data)
        excel_rows = [headers]

        for row in data:
            excel_rows.append(evaulate_value(row, self.headers_and_calculation))

        excel_rows.append(total_sum_row)

        filters = [['Generated at', india_now()]]
        if self.location:
            locs = SQLLocation.objects.get(location_id=self.location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        else:
            filters.append(['Location', 'National'])

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
