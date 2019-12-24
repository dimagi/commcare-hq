from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import DATA_NOT_ENTERED


@icds_quickcache(['start', 'length', 'year', 'month', 'order', 'location_filters'], timeout=30 * 60)
def get_home_visit_data(start, length, year, month, order, location_filters):
    data = AggAwcMonthly.objects.filter(
        month=date(year, month, 1),
        **location_filters
    ).order_by(*order).values(
        'state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'valid_visits',
        'expected_visits'
    )
    config = {
        'data': [],
        'filter_params': {
            'start': start,
            'month': month,
            'year': year
        }
    }

    def get_value_or_data_not_entered(source, field):
        value = source.get(field)
        if value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return dict(
            state=get_value_or_data_not_entered(row_data, 'state_name'),
            district=get_value_or_data_not_entered(row_data, 'district_name'),
            block=get_value_or_data_not_entered(row_data, 'block_name'),
            sector=get_value_or_data_not_entered(row_data, 'supervisor_name'),
            awc=get_value_or_data_not_entered(row_data, 'awc_name'),
            valid_visits=get_value_or_data_not_entered(row_data, 'valid_visits'),
            expected_visits=get_value_or_data_not_entered(row_data, 'expected_visits'),
        )

    for row in data:
        config['data'].append(base_data(row))

    config['data'] = config['data'][start:(start + length)]

    return config
