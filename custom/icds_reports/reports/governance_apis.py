from datetime import date

from django.db.models import F

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import AggregationLevels
from custom.icds_reports.models import AggAwcMonthly, AwcLocation
from custom.icds_reports.utils import DATA_NOT_ENTERED


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_home_visit_data(length, year, month, order, query_filters):
    data = AggAwcMonthly.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).annotate(awc_code=F('awc_site_code')).values(
        'awc_id', 'awc_code', 'valid_visits', 'expected_visits'
    )
    paginated_data = data[:length]

    def get_value_or_data_not_entered(value):
        if value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return {key: get_value_or_data_not_entered(value) for key, value in row_data.items()}

    return [base_data(row) for row in paginated_data], data.count()


@icds_quickcache([], timeout=30 * 60)
def get_state_names():
    return list(AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE, state_is_test=0
                                           ).values('state_site_code', 'state_name'))
