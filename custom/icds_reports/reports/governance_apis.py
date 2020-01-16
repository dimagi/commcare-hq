from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import AggregationLevels
from custom.icds_reports.models import AggAwcMonthly, AwcLocation
from custom.icds_reports.utils import DATA_NOT_ENTERED


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_home_visit_data(length, year, month, order, query_filters):
    data = AggAwcMonthly.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).values(
        'awc_id', 'awc_site_code', 'month', 'valid_visits', 'expected_visits'
    )
    paginated_data = data[:length]

    def get_value_or_data_not_entered(source, field):
        value = source.get(field)
        if value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return dict(
            awc_id=get_value_or_data_not_entered(row_data, 'awc_id'),
            awc_code=get_value_or_data_not_entered(row_data, 'awc_site_code'),
            valid_visits=get_value_or_data_not_entered(row_data, 'valid_visits'),
            expected_visits=get_value_or_data_not_entered(row_data, 'expected_visits'),
        )

    data_rows = []
    for row in paginated_data:
        data_rows.append(base_data(row))
    return data_rows, data.count()


@icds_quickcache([], timeout=30 * 60)
def get_state_names():
    return list(AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE, state_is_test=0
                                           ).values('state_site_code', 'state_name'))
