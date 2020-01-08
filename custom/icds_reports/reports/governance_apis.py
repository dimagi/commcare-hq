from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.models.views import GovVHNDView
from custom.icds_reports.utils import DATA_NOT_ENTERED


def get_value_or_data_not_entered(source, field):
    value = source.get(field)
    if value is None:
        return DATA_NOT_ENTERED
    return value


def get_boolean_if_data_not_null(source, field):
    value = source.get(field)
    if value is None:
        return 'no'
    return 'yes'


@icds_quickcache(['start', 'length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_home_visit_data(start, length, year, month, order, query_filters):
    data = AggAwcMonthly.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).values(
        'state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'month', 'valid_visits',
        'expected_visits'
    )
    paginated_data = data[int(start):(int(start) + length)]

    def base_data(row_data):
        return dict(
            state=get_value_or_data_not_entered(row_data, 'state_name'),
            district=get_value_or_data_not_entered(row_data, 'district_name'),
            block=get_value_or_data_not_entered(row_data, 'block_name'),
            sector=get_value_or_data_not_entered(row_data, 'supervisor_name'),
            awc=get_value_or_data_not_entered(row_data, 'awc_name'),
            month=get_value_or_data_not_entered(row_data, 'month'),
            valid_visits=get_value_or_data_not_entered(row_data, 'valid_visits'),
            expected_visits=get_value_or_data_not_entered(row_data, 'expected_visits'),
        )

    data_rows = []
    for row in paginated_data:
        data_rows.append(base_data(row))
    return data_rows, data.count()


def get_vhnd_data(start, length, year, month, order):
    data = GovVHNDView.objects.filter(
        month=date(year, month, 1)
    ).order_by(*order)

    paginated_data = data[int(start):(int(start) + length)]

    def base_data(row_data):
        return dict(
            state=get_value_or_data_not_entered(row_data, 'state_name'),
            district=get_value_or_data_not_entered(row_data, 'district_name'),
            block=get_value_or_data_not_entered(row_data, 'block_name'),
            sector=get_value_or_data_not_entered(row_data, 'supervisor_name'),
            awc=get_value_or_data_not_entered(row_data, 'awc_name'),
            month=get_value_or_data_not_entered(row_data, 'month'),
            vhsnd_conducted = get_boolean_if_data_not_null(row_data, 'vhsnd_date_past_month'),
            vhsnd_date=get_value_or_data_not_entered(row_data, 'vhsnd_date_past_month'),
            anm_present=get_value_or_data_not_entered(row_data, 'anm_mpw_present'),
            asha_present=get_value_or_data_not_entered(row_data, 'asha_present'),
            any_child_immunized=get_value_or_data_not_entered(row_data, 'child_immu'),
            anc_conducted=get_value_or_data_not_entered(row_data, 'anc_today'),
        )

    data_rows = []
    for row in paginated_data:
        data_rows.append(base_data(row))
    return data_rows, data.count()
