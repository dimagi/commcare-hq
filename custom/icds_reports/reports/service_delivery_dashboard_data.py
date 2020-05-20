from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.views import ServiceDeliveryReportView
from custom.icds_reports.utils import DATA_NOT_ENTERED, percent_or_not_entered, apply_exclude


@icds_quickcache([
    'start', 'length', 'order', 'reversed_order', 'location_filters', 'year', 'month', 'step'
], timeout=30 * 60)
def get_service_delivery_report_data(domain, start, length, order, reversed_order, location_filters,
                              year, month, step, include_test=False):
    year = 2017
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

    data = ServiceDeliveryReportView .objects.filter(
        month=date(year, month, 1),
        **location_filters
    ).order_by(default_order).values(
        'state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'num_launched_awcs',
        'valid_visits', 'expected_visits', 'gm_0_3', 'children_0_3', 'num_awcs_conducted_cbe',
        'num_awcs_conducted_vhnd', 'thr_21_days', 'thr_25_days', 'thr_eligible', 'lunch_21_days',
        'lunch_25_days', 'pse_eligible', 'pse_21_days', 'pse_25_days', 'gm_3_5', 'children_3_5'
    )
    if not include_test:
        data = apply_exclude(domain, data)
    data_count = data.count()
    config = {
        'data': [],
    }

    def month_filter_check():
        return year >= 2020 and month >= 4

    def get_value_or_data_not_entered(source, field):
        value = source.get(field)
        if value is None:
            return DATA_NOT_ENTERED
        return value

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
                home_visits=percent_or_not_entered(row_data['valid_visits'], row_data['expected_visits']),
                gm_0_3=get_value_or_data_not_entered(row_data, 'gm_0_3'),
                children_0_3=get_value_or_data_not_entered(row_data, 'children_0_3'),
                gm=percent_or_not_entered(row_data['gm_0_3'], row_data['children_0_3']),
                num_awcs_conducted_cbe=get_value_or_data_not_entered(row_data, 'num_awcs_conducted_cbe'),
                num_awcs_conducted_vhnd=get_value_or_data_not_entered(row_data, 'num_awcs_conducted_vhnd'),
                thr_given_21_days=get_value_or_data_not_entered(row_data, 'thr_21_days'),
                thr_given_25_days=get_value_or_data_not_entered(row_data, 'thr_25_days'),
                total_thr_candidates=get_value_or_data_not_entered(row_data, 'thr_eligible'),
                thr=percent_or_not_entered(row_data['thr_21_days'], row_data['thr_eligible']),
                cbe=percent_or_not_entered(row_data['num_awcs_conducted_cbe'], row_data['num_launched_awcs'])
            )
            if month_filter_check():
                return_dict['thr'] = percent_or_not_entered(row_data['thr_25_days'], row_data['thr_eligible'])
            return return_dict
        else:
            return_dict = dict(
                num_launched_awcs=get_value_or_data_not_entered(row_data, 'num_launched_awcs'),
                state_name=get_value_or_data_not_entered(row_data, 'state_name'),
                district_name=get_value_or_data_not_entered(row_data, 'district_name'),
                block_name=get_value_or_data_not_entered(row_data, 'block_name'),
                supervisor_name=get_value_or_data_not_entered(row_data, 'supervisor_name'),
                awc_name=get_value_or_data_not_entered(row_data, 'awc_name'),
                lunch_count_21_days=get_value_or_data_not_entered(row_data, 'lunch_21_days'),
                lunch_count_25_days=get_value_or_data_not_entered(row_data, 'lunch_25_days'),
                children_3_6=get_value_or_data_not_entered(row_data, 'pse_eligible'),
                sn=percent_or_not_entered(row_data['lunch_21_days'], row_data['pse_eligible']),
                pse_attended_21_days=get_value_or_data_not_entered(row_data, 'pse_21_days'),
                pse_attended_25_days=get_value_or_data_not_entered(row_data, 'pse_25_days'),
                pse=percent_or_not_entered(row_data['pse_21_days'], row_data['pse_eligible']),
                gm_3_5=get_value_or_data_not_entered(row_data, 'gm_3_5'),
                children_3_5=get_value_or_data_not_entered(row_data, 'children_3_5'),
                gm=percent_or_not_entered(row_data['gm_3_5'], row_data['children_3_5']),
            )
            if month_filter_check():
                return_dict['pse'] = percent_or_not_entered(row_data['pse_25_days'], row_data['pse_eligible'])
                return_dict['sn'] = percent_or_not_entered(row_data['lunch_25_days'], row_data['pse_eligible'])
            return return_dict

    for row in data:
        config['data'].append(base_data(row))

    percentage_fields = ('home_visits', 'gm', 'thr', 'sn', 'pse')
    if order:
        if order in percentage_fields:
            config['data'].sort(
                key=lambda x: float(x[order][:-1] if x[order] != DATA_NOT_ENTERED else 0), reverse=reversed_order
            )
        else:
            config['data'].sort(key=lambda x: x[order], reverse=reversed_order)
    config['data'] = config['data'][start:(start + length)]

    config["aggregationLevel"] = location_filters['aggregation_level']
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count

    return config


@icds_quickcache([
    'start', 'length', 'order', 'reversed_order', 'location_filters', 'year', 'month', 'step'
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

    values = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']

    if step == 'thr':
        values.extend(['thr_eligible', 'thr_0_days', 'thr_1_7_days', 'thr_8_14_days', 'thr_15_20_days',
                       'thr_21_24_days', 'thr_25_days'])
    elif step == 'cbe':
        values.extend(['cbe_conducted', 'third_fourth_month_of_pregnancy_count', 'annaprasan_diwas_count',
                       'suposhan_diwas_count', 'coming_of_age_count', 'public_health_message_count'])
    elif step == 'sn':
        values.extend(['pse_eligible', 'lunch_0_days', 'lunch_1_7_days', 'lunch_8_14_days', 'lunch_15_20_days',
                       'lunch_21_24_days', 'lunch_25_days'])
    elif step == 'pse':
        values.extend(['pse_eligible', 'pse_0_days', 'pse_1_7_days', 'pse_8_14_days', 'pse_15_20_days',
                       'pse_21_24_days', 'pse_25_days'])

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

    def get_value_or_data_not_entered(source, field):
        value = source.get(field)
        if value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        base_dict = dict(
            state_name=get_value_or_data_not_entered(row_data, 'state_name'),
            district_name=get_value_or_data_not_entered(row_data, 'district_name'),
            block_name=get_value_or_data_not_entered(row_data, 'block_name'),
            supervisor_name=get_value_or_data_not_entered(row_data, 'supervisor_name'),
            awc_name=get_value_or_data_not_entered(row_data, 'awc_name')
        )
        if step == 'thr':
            base_dict['thr_0_days'] = percent_or_not_entered(row_data['thr_0_days'],
                                                             row_data['thr_eligible'])
            base_dict['thr_1_7_days'] = percent_or_not_entered(row_data['thr_1_7_days'],
                                                               row_data['thr_eligible'])
            base_dict['thr_8_14_days'] = percent_or_not_entered(row_data['thr_8_14_days'],
                                                                row_data['thr_eligible'])
            base_dict['thr_15_20_days'] = percent_or_not_entered(row_data['thr_15_20_days'],
                                                                 row_data['thr_eligible'])
            base_dict['thr_21_24_days'] = percent_or_not_entered(row_data['thr_21_24_days'],
                                                                 row_data['thr_eligible'])
            base_dict['thr_25_days'] = percent_or_not_entered(row_data['thr_25_days'],
                                                              row_data['thr_eligible'])
            base_dict['thr_0_days_val'] = get_value_or_data_not_entered(row_data, 'thr_0_days')
            base_dict['thr_1_7_days_val'] = get_value_or_data_not_entered(row_data, 'thr_1_7_days')
            base_dict['thr_8_14_days_val'] = get_value_or_data_not_entered(row_data, 'thr_8_14_days')
            base_dict['thr_15_20_days_val'] = get_value_or_data_not_entered(row_data, 'thr_15_20_days')
            base_dict['thr_21_24_days_val'] = get_value_or_data_not_entered(row_data, 'thr_21_24_days')
            base_dict['thr_25_days_val'] = get_value_or_data_not_entered(row_data, 'thr_25_days')
            base_dict['thr_eligible'] = get_value_or_data_not_entered(row_data, 'thr_eligible')
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
            base_dict['lunch_0_days'] = percent_or_not_entered(row_data['lunch_0_days'],
                                                               row_data['pse_eligible'])
            base_dict['lunch_1_7_days'] = percent_or_not_entered(row_data['lunch_1_7_days'],
                                                                 row_data['pse_eligible'])
            base_dict['lunch_8_14_days'] = percent_or_not_entered(row_data['lunch_8_14_days'],
                                                                  row_data['pse_eligible'])
            base_dict['lunch_15_20_days'] = percent_or_not_entered(row_data['lunch_15_20_days'],
                                                                   row_data['pse_eligible'])
            base_dict['lunch_21_24_days'] = percent_or_not_entered(row_data['lunch_21_24_days'],
                                                                   row_data['pse_eligible'])
            base_dict['lunch_25_days'] = percent_or_not_entered(row_data['lunch_25_days'],
                                                                row_data['pse_eligible'])
            base_dict['lunch_0_days_val'] = get_value_or_data_not_entered(row_data, 'lunch_0_days')
            base_dict['lunch_1_7_days_val'] = get_value_or_data_not_entered(row_data, 'lunch_1_7_days')
            base_dict['lunch_8_14_days_val'] = get_value_or_data_not_entered(row_data, 'lunch_8_14_days')
            base_dict['lunch_15_20_days_val'] = get_value_or_data_not_entered(row_data, 'lunch_15_20_days')
            base_dict['lunch_21_24_days_val'] = get_value_or_data_not_entered(row_data, 'lunch_21_24_days')
            base_dict['lunch_25_days_val'] = get_value_or_data_not_entered(row_data, 'lunch_25_days')
            base_dict['pse_eligible'] = get_value_or_data_not_entered(row_data, 'pse_eligible')
        elif step == 'pse':
            base_dict['pse_0_days'] = percent_or_not_entered(row_data['pse_0_days'],
                                                             row_data['pse_eligible'])
            base_dict['pse_1_7_days'] = percent_or_not_entered(row_data['pse_1_7_days'],
                                                               row_data['pse_eligible'])
            base_dict['pse_8_14_days'] = percent_or_not_entered(row_data['pse_8_14_days'],
                                                                row_data['pse_eligible'])
            base_dict['pse_15_20_days'] = percent_or_not_entered(row_data['pse_15_20_days'],
                                                                 row_data['pse_eligible'])
            base_dict['pse_21_24_days'] = percent_or_not_entered(row_data['pse_21_24_days'],
                                                                 row_data['pse_eligible'])
            base_dict['pse_25_days'] = percent_or_not_entered(row_data['pse_25_days'],
                                                              row_data['pse_eligible'])
            base_dict['pse_0_days_val'] = get_value_or_data_not_entered(row_data, 'pse_0_days')
            base_dict['pse_1_7_days_val'] = get_value_or_data_not_entered(row_data, 'pse_1_7_days')
            base_dict['pse_8_14_days_val'] = get_value_or_data_not_entered(row_data, 'pse_8_14_days')
            base_dict['pse_15_20_days_val'] = get_value_or_data_not_entered(row_data, 'pse_15_20_days')
            base_dict['pse_21_24_days_val'] = get_value_or_data_not_entered(row_data, 'pse_21_24_days')
            base_dict['pse_25_days_val'] = get_value_or_data_not_entered(row_data, 'pse_25_days')
            base_dict['pse_eligible'] = get_value_or_data_not_entered(row_data, 'pse_eligible')
        return base_dict
    for row in data:
        config['data'].append(base_data(row))

    percentage_fields = values
    if order:
        if order in percentage_fields:
            config['data'].sort(
                key=lambda x: float(x[order][:-1] if x[order] != DATA_NOT_ENTERED else 0), reverse=reversed_order
            )
        else:
            config['data'].sort(key=lambda x: x[order], reverse=reversed_order)
    config['data'] = config['data'][start:(start + length)]

    config["aggregationLevel"] = location_filters['aggregation_level']
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count

    return config
