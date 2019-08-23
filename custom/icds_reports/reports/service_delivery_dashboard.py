from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.views import ServiceDeliveryMonthly
from custom.icds_reports.utils import DATA_NOT_ENTERED, percent_or_not_entered, apply_exclude


@icds_quickcache([
    'start', 'length', 'order', 'reversed_order', 'location_filters', 'year', 'month', 'step'
], timeout=30 * 60)
def get_service_delivery_data(domain, start, length, order, reversed_order, location_filters,
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

    data = ServiceDeliveryMonthly.objects.filter(
        month=date(year, month, 1),
        **location_filters
    ).order_by(default_order).values(
        'state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'num_launched_awcs',
        'valid_visits', 'expected_visits', 'gm_0_3', 'children_0_3', 'num_awcs_conducted_cbe',
        'num_awcs_conducted_vhnd', 'thr_given_21_days', 'total_thr_candidates', 'lunch_count_21_days',
        'children_3_6', 'pse_attended_21_days', 'gm_3_5', 'children_3_5'
    )
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
        if step == 'pw_lw_children':
            return dict(
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
                thr_given_21_days=get_value_or_data_not_entered(row_data, 'thr_given_21_days'),
                total_thr_candidates=get_value_or_data_not_entered(row_data, 'total_thr_candidates'),
                thr=percent_or_not_entered(row_data['thr_given_21_days'], row_data['total_thr_candidates']),
            )
        else:
            return dict(
                num_launched_awcs=get_value_or_data_not_entered(row_data, 'num_launched_awcs'),
                state_name=get_value_or_data_not_entered(row_data, 'state_name'),
                district_name=get_value_or_data_not_entered(row_data, 'district_name'),
                block_name=get_value_or_data_not_entered(row_data, 'block_name'),
                supervisor_name=get_value_or_data_not_entered(row_data, 'supervisor_name'),
                awc_name=get_value_or_data_not_entered(row_data, 'awc_name'),
                lunch_count_21_days=get_value_or_data_not_entered(row_data, 'lunch_count_21_days'),
                children_3_6=get_value_or_data_not_entered(row_data, 'children_3_6'),
                sn=percent_or_not_entered(row_data['lunch_count_21_days'], row_data['children_3_6']),
                pse_attended_21_days=get_value_or_data_not_entered(row_data, 'pse_attended_21_days'),
                pse=percent_or_not_entered(row_data['pse_attended_21_days'], row_data['children_3_6']),
                gm_3_5=get_value_or_data_not_entered(row_data, 'gm_3_5'),
                children_3_5=get_value_or_data_not_entered(row_data, 'children_3_5'),
                gm=percent_or_not_entered(row_data['gm_3_5'], row_data['children_3_5']),
            )

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
