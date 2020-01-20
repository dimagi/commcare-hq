from datetime import date

from django.db.models import F

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.aggregate import AggGovernanceDashboard
from custom.icds_reports.const import AggregationLevels
from custom.icds_reports.models import AggAwcMonthly, AwcLocation
from custom.icds_reports.models.views import GovVHNDView
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


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_vhnd_data(length, year, month, order, query_filters):
    data = GovVHNDView.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).annotate(
        vhsnd_conducted=F('vhsnd_date_past_month'), vhsnd_date=F('vhsnd_date_past_month'),
        anm_present=F('anm_mpw_present'), any_child_immunized=F('child_immu'),
        anc_conducted=F('anc_today')).values(
        'awc_id', 'awc_code', 'vhsnd_conducted', 'vhsnd_date', 'anm_present', 'asha_present',
        'any_child_immunized', 'anc_conducted'
    )

    paginated_data = data[:length]

    def get_value_or_data_not_entered(key, value):
        if type(value) is bool or key == 'vhsnd_conducted':
            if value in [None, False]:
                return 'no'
            return 'yes'
        elif value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return {key: get_value_or_data_not_entered(key, value) for key, value in row_data.items()}

    return [base_data(row) for row in paginated_data], data.count()


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_beneficiary_data(length, year, month, order, query_filters):
    data = AggGovernanceDashboard.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).values(
        'awc_id',
        'awc_code',
        'total_preg_benefit_till_date',
        'total_lact_benefit_till_date',
        'total_preg_reg_till_date',
        'total_lact_reg_till_date',
        'total_lact_benefit_in_month',
        'total_preg_benefit_in_month',
        'total_lact_reg_in_month',
        'total_preg_reg_in_month',
        'total_0_3_female_benefit_till_date',
        'total_0_3_male_benefit_till_date',
        'total_0_3_female_reg_till_date',
        'total_0_3_male_reg_till_date',
        'total_3_6_female_benefit_till_date',
        'total_3_6_male_benefit_till_date',
        'total_3_6_female_reg_till_date',
        'total_3_6_male_reg_till_date',
        'total_0_3_female_benefit_in_month',
        'total_0_3_male_benefit_in_month',
        'total_0_3_female_reg_in_month',
        'total_0_3_male_reg_in_month',
        'total_3_6_female_benefit_in_month',
        'total_3_6_male_benefit_in_month',
        'total_3_6_female_reg_in_month',
        'total_3_6_male_reg_in_month'
    )

    # To apply pagination on database query with offset and limit
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
