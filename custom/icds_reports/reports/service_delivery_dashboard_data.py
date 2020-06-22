import copy
from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.views import ServiceDeliveryReportView
from custom.icds_reports.utils import DATA_NOT_ENTERED, percent_or_not_entered, apply_exclude, \
    format_data_not_entered_to_zero


def get_value_or_data_not_entered(source, field):
    value = source.get(field)
    if value is None:
        return DATA_NOT_ENTERED
    return value


def _get_pre_percents(base_dict, row_data, service_name, eligibility):
    base_dict[f'{service_name}_0_days_val'] = percent_or_not_entered(row_data[f'{service_name}_0_days'],
                                                                     row_data[f'{eligibility}_eligible'])
    base_dict[f'{service_name}_1_7_days_val'] = percent_or_not_entered(row_data[f'{service_name}_1_7_days'],
                                                                       row_data[f'{eligibility}_eligible'])
    base_dict[f'{service_name}_8_14_days_val'] = percent_or_not_entered(row_data[f'{service_name}_8_14_days'],
                                                                        row_data[f'{eligibility}_eligible'])
    base_dict[f'{service_name}_15_20_days_val'] = percent_or_not_entered(row_data[f'{service_name}_15_20_days'],
                                                                         row_data[f'{eligibility}_eligible'])
    base_dict[f'{service_name}_21_24_days_val'] = percent_or_not_entered(row_data[f'{service_name}_21_24_days'],
                                                                         row_data[f'{eligibility}_eligible'])
    base_dict[f'{service_name}_25_days_val'] = percent_or_not_entered(row_data[f'{service_name}_25_days'],
                                                                      row_data[f'{eligibility}_eligible'])
    return base_dict


def _get_pre_values(base_dict, row_data, service_name, eligibility):
    base_dict[f'{service_name}_0_days'] = get_value_or_data_not_entered(row_data, f'{service_name}_0_days')
    base_dict[f'{service_name}_1_7_days'] = get_value_or_data_not_entered(row_data, f'{service_name}_1_7_days')
    base_dict[f'{service_name}_8_14_days'] = get_value_or_data_not_entered(row_data, f'{service_name}_8_14_days')
    base_dict[f'{service_name}_15_20_days'] = get_value_or_data_not_entered(row_data, f'{service_name}_15_20_days')
    base_dict[f'{service_name}_21_24_days'] = get_value_or_data_not_entered(row_data, f'{service_name}_21_24_days')
    base_dict[f'{service_name}_25_days'] = get_value_or_data_not_entered(row_data, f'{service_name}_25_days')
    base_dict[f'{eligibility}_eligible'] = get_value_or_data_not_entered(row_data, f'{eligibility}_eligible')
    return base_dict


@icds_quickcache([
    'domain', 'start', 'length', 'order', 'reversed_order', 'location_filters', 'year', 'month', 'step'
], timeout=30 * 60)
def get_service_delivery_report_data(domain, start, length, order, reversed_order, location_filters,
                                     year, month, step, include_test=False):
    if location_filters.get('aggregation_level') == 1:
        default_order = 'state_name'
    elif location_filters.get('aggregation_level') == 2:
        default_order = 'district_name'
    elif location_filters.get('aggregation_level') == 3:
        default_order = 'block_name'
    elif location_filters.get('aggregation_level') == 4:
        default_order = 'supervisor_name'
    else:
        default_order = 'awc_name'

    location_fields = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
    value_fields = location_fields + ['num_launched_awcs', 'valid_visits', 'expected_visits', 'gm_0_3',
                                      'children_0_3', 'num_awcs_conducted_cbe', 'num_awcs_conducted_vhnd',
                                      'thr_21_days', 'thr_25_days', 'thr_eligible', 'lunch_21_days',
                                      'lunch_25_days', 'pse_eligible', 'pse_21_days', 'pse_25_days',
                                      'gm_3_5', 'children_3_5', 'vhnd_conducted']
    data = ServiceDeliveryReportView .objects.filter(
        month=date(year, month, 1),
        **location_filters
    ).order_by(default_order).values(*value_fields)
    if not include_test:
        data = apply_exclude(domain, data)
    data_count = data.count()
    config = {
        'data': [],
    }

    def should_show_25():
        return year >= 2020 and month >= 4

    def update_total_row(first_dict, second_dict):
        for key, value in first_dict.items():
            # excluding location and percentage fields
            if key not in location_fields + ['cbe', 'thr', 'pse', 'sn', 'gm', 'home_visits']:
                first_dict[key] = format_data_not_entered_to_zero(first_dict[key]) +\
                                  format_data_not_entered_to_zero(second_dict[key])
        return first_dict

    def get_pw_lw_percents(return_dict, row_data):
        return_dict['home_visits'] = percent_or_not_entered(row_data['valid_visits'],
                                                            row_data['expected_visits'])
        return_dict['gm'] = percent_or_not_entered(row_data['gm_0_3'], row_data['children_0_3'])
        return_dict['cbe'] = percent_or_not_entered(row_data['num_awcs_conducted_cbe'],
                                                    row_data['num_launched_awcs'])
        if should_show_25():
            return_dict['thr'] = percent_or_not_entered(row_data['thr_25_days'], row_data['thr_eligible'])
        else:
            return_dict['thr'] = percent_or_not_entered(row_data['thr_21_days'], row_data['thr_eligible'])
        return return_dict

    def get_children_percents(return_dict, row_data):
        return_dict['gm'] = percent_or_not_entered(row_data['gm_3_5'], row_data['children_3_5'])
        if should_show_25():
            return_dict['pse'] = percent_or_not_entered(row_data['pse_25_days'], row_data['pse_eligible'])
            return_dict['sn'] = percent_or_not_entered(row_data['lunch_25_days'], row_data['pse_eligible'])
        else:
            return_dict['pse'] = percent_or_not_entered(row_data['pse_21_days'], row_data['pse_eligible'])
            return_dict['sn'] = percent_or_not_entered(row_data['lunch_21_days'], row_data['pse_eligible'])
        return return_dict

    def base_data(row_data):
        if step == 'pw_lw_children':
            return_dict = dict(
                state_name=get_value_or_data_not_entered(row_data, 'state_name'),
                district_name=get_value_or_data_not_entered(row_data, 'district_name'),
                block_name=get_value_or_data_not_entered(row_data, 'block_name'),
                supervisor_name=get_value_or_data_not_entered(row_data, 'supervisor_name'),
                awc_name=get_value_or_data_not_entered(row_data, 'awc_name'),
                num_launched_awcs=get_value_or_data_not_entered(row_data, 'num_launched_awcs'),
                valid_visits=get_value_or_data_not_entered(row_data, 'valid_visits'),
                expected_visits=get_value_or_data_not_entered(row_data, 'expected_visits'),
                gm_0_3=get_value_or_data_not_entered(row_data, 'gm_0_3'),
                children_0_3=get_value_or_data_not_entered(row_data, 'children_0_3'),
                num_awcs_conducted_cbe=get_value_or_data_not_entered(row_data, 'num_awcs_conducted_cbe'),
                num_awcs_conducted_vhnd=get_value_or_data_not_entered(row_data, 'num_awcs_conducted_vhnd'),
                thr_21_days=get_value_or_data_not_entered(row_data, 'thr_21_days'),
                thr_25_days=get_value_or_data_not_entered(row_data, 'thr_25_days'),
                thr_eligible=get_value_or_data_not_entered(row_data, 'thr_eligible'),
                vhnd_conducted=get_value_or_data_not_entered(row_data, 'vhnd_conducted')
            )
            return_dict = get_pw_lw_percents(return_dict, row_data)
        else:
            return_dict = dict(
                num_launched_awcs=get_value_or_data_not_entered(row_data, 'num_launched_awcs'),
                state_name=get_value_or_data_not_entered(row_data, 'state_name'),
                district_name=get_value_or_data_not_entered(row_data, 'district_name'),
                block_name=get_value_or_data_not_entered(row_data, 'block_name'),
                supervisor_name=get_value_or_data_not_entered(row_data, 'supervisor_name'),
                awc_name=get_value_or_data_not_entered(row_data, 'awc_name'),
                lunch_21_days=get_value_or_data_not_entered(row_data, 'lunch_21_days'),
                lunch_25_days=get_value_or_data_not_entered(row_data, 'lunch_25_days'),
                pse_eligible=get_value_or_data_not_entered(row_data, 'pse_eligible'),
                pse_21_days=get_value_or_data_not_entered(row_data, 'pse_21_days'),
                pse_25_days=get_value_or_data_not_entered(row_data, 'pse_25_days'),
                gm_3_5=get_value_or_data_not_entered(row_data, 'gm_3_5'),
                children_3_5=get_value_or_data_not_entered(row_data, 'children_3_5')
            )
            return_dict = get_children_percents(return_dict, row_data)
        return return_dict

    all_row = dict()

    data_length = len(data)
    for index, row in enumerate(data):
        base_row = base_data(row)
        if not all_row.keys():
            all_row = copy.deepcopy(base_row)
        else:
            all_row = update_total_row(all_row, base_row)
        config['data'].append(base_row)
    if data_length:
        # setting location params to all
        for location in location_fields:
            all_row[location] = 'All'
        all_row['cbe_sector_percent'] = percent_or_not_entered(all_row['num_awcs_conducted_cbe'], data_length)
        all_row['vhnd_sector_value'] = get_value_or_data_not_entered(all_row, 'num_awcs_conducted_vhnd')
        # Calculating percentages for all row
        if step == 'pw_lw_children':
            get_pw_lw_percents(all_row, all_row)
        else:
            get_children_percents(all_row, all_row)

        percentage_fields = ('home_visits', 'gm', 'thr', 'sn', 'pse')
        if order:
            if order in percentage_fields:
                config['data'].sort(
                    key=lambda x: float(x[order][:-1] if x[order] != DATA_NOT_ENTERED else 0), reverse=reversed_order
                )
            else:
                config['data'].sort(key=lambda x: x[order], reverse=reversed_order)
        config['data'] = config['data'][start:(start + length)]
        config['data'].insert(0, all_row)
    config["aggregationLevel"] = location_filters['aggregation_level']
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count
    return config


@icds_quickcache([
    'domain', 'start', 'length', 'order', 'reversed_order', 'location_filters', 'year', 'month', 'step'
], timeout=30 * 60)
def get_service_delivery_details(domain, start, length, order, reversed_order, location_filters,
                                 year, month, step, include_test=False):
    if location_filters.get('aggregation_level') == 1:
        default_order = 'state_name'
    elif location_filters.get('aggregation_level') == 2:
        default_order = 'district_name'
    elif location_filters.get('aggregation_level') == 3:
        default_order = 'block_name'
    elif location_filters.get('aggregation_level') == 4:
        default_order = 'supervisor_name'
    else:
        default_order = 'awc_name'

    location_fields = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
    count_columns = ['num_launched_awcs']

    if step == 'thr':
        count_columns += ['thr_eligible', 'thr_0_days', 'thr_1_7_days', 'thr_8_14_days', 'thr_15_20_days',
                          'thr_21_24_days', 'thr_25_days']
    elif step == 'cbe':
        count_columns += ['cbe_conducted', 'third_fourth_month_of_pregnancy_count', 'annaprasan_diwas_count',
                          'suposhan_diwas_count', 'coming_of_age_count', 'public_health_message_count']
    elif step == 'sn':
        count_columns += ['pse_eligible', 'lunch_0_days', 'lunch_1_7_days', 'lunch_8_14_days', 'lunch_15_20_days',
                          'lunch_21_24_days', 'lunch_25_days']
    elif step == 'pse':
        count_columns += ['pse_eligible', 'pse_0_days', 'pse_1_7_days', 'pse_8_14_days', 'pse_15_20_days',
                          'pse_21_24_days', 'pse_25_days']
    values = location_fields + count_columns

    def get_data_for(default_order, values):
        return ServiceDeliveryReportView.objects.filter(month=date(year, month, 1), **location_filters)\
            .order_by(default_order).values(*values)

    data = get_data_for(default_order, values)

    if not include_test:
        data = apply_exclude(domain, data)
    data_count = data.count()
    config = {
        'data': [],
    }

    def update_total_row(first_dict, second_dict):
        for key, value in first_dict.items():
            # excluding location and percentage fields
            if key in values:
                first_dict[key] = format_data_not_entered_to_zero(first_dict[key]) +\
                                  format_data_not_entered_to_zero(second_dict[key])
        return first_dict

    def base_data(row_data):
        base_dict = dict(
            state_name=get_value_or_data_not_entered(row_data, 'state_name'),
            district_name=get_value_or_data_not_entered(row_data, 'district_name'),
            block_name=get_value_or_data_not_entered(row_data, 'block_name'),
            supervisor_name=get_value_or_data_not_entered(row_data, 'supervisor_name'),
            awc_name=get_value_or_data_not_entered(row_data, 'awc_name'),
            num_launched_awcs=get_value_or_data_not_entered(row_data, 'num_launched_awcs')
        )
        if step == 'thr':
            # calculating percents
            base_dict = _get_pre_percents(base_dict, row_data, 'thr', 'thr')
            # filling the data fields
            base_dict = _get_pre_values(base_dict, row_data, 'thr', 'thr')
        elif step == 'cbe':
            base_dict['cbe_conducted'] = get_value_or_data_not_entered(row_data, 'cbe_conducted')
            base_dict['third_fourth_month_of_pregnancy_count'] =\
                get_value_or_data_not_entered(row_data, 'third_fourth_month_of_pregnancy_count')
            base_dict['annaprasan_diwas_count'] = get_value_or_data_not_entered(row_data,
                                                                                'annaprasan_diwas_count')
            base_dict['suposhan_diwas_count'] = get_value_or_data_not_entered(row_data,
                                                                              'suposhan_diwas_count')
            base_dict['coming_of_age_count'] = get_value_or_data_not_entered(row_data,
                                                                             'coming_of_age_count')
            base_dict['public_health_message_count'] =\
                get_value_or_data_not_entered(row_data, 'public_health_message_count')
        elif step == 'sn':
            base_dict = _get_pre_percents(base_dict, row_data, 'lunch', 'pse')
            base_dict = _get_pre_values(base_dict, row_data, 'lunch', 'pse')

        elif step == 'pse':
            base_dict = _get_pre_percents(base_dict, row_data, 'pse', 'pse')
            base_dict = _get_pre_values(base_dict, row_data, 'pse', 'pse')
        return base_dict

    all_row = dict()

    data_length = len(data)
    for index, row in enumerate(data):
        base_row = base_data(row)
        if not all_row.keys():
            all_row = copy.deepcopy(base_row)
        else:
            all_row = update_total_row(all_row, base_row)
        config['data'].append(base_data(row))
    if data_length:
        # setting location params to all
        for location in location_fields:
            all_row[location] = 'All'
        # Calculating percentages for all row
        if step == 'thr':
            all_row = _get_pre_percents(all_row, all_row, 'thr', 'thr')
        elif step == 'sn':
            all_row = _get_pre_percents(all_row, all_row, 'lunch', 'pse')
        elif step == 'pse':
            all_row = _get_pre_percents(all_row, all_row, 'pse', 'pse')

        sort_columns = [field + '_val' for field in count_columns]

        percentage_fields = sort_columns
        if order:
            if order in percentage_fields:
                config['data'].sort(
                    key=lambda x: float(x[order][:-1] if x[order] != DATA_NOT_ENTERED else 0), reverse=reversed_order
                )
            else:
                config['data'].sort(key=lambda x: x[order], reverse=reversed_order)
        config['data'] = config['data'][start:(start + length)]
        config['data'].insert(0, all_row)
    config["aggregationLevel"] = location_filters['aggregation_level']
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count

    return config
