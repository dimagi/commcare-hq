from datetime import date

from django.db.models import F, Case, When, BooleanField, TextField, Value

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.aggregate import AggGovernanceDashboard
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


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_vhnd_data(length, year, month, order, query_filters):
    fields_mapping = {
        'vhsnd_date': 'vhsnd_date_past_month',
        'anm_present': 'anm_mpw_present',
        'any_child_immunized': 'child_immu',
        'anc_conducted': 'anc_today'
    }
    data = AggGovernanceDashboard.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).extra(
        select=fields_mapping
    ).annotate(vhsnd_conducted=Case(
        When(vhsnd_date_past_month__isnull=False, then=True),
        default=False,
        output_field=BooleanField()
    )).values(
        'awc_id', 'awc_code', 'vhsnd_conducted', 'vhsnd_date', 'anm_present', 'asha_present',
        'any_child_immunized', 'anc_conducted'
    )

    paginated_data = data[:length]

    def get_value_or_data_not_entered(value):
        if type(value) is bool:
            if value:
                return 'yes'
            return 'no'
        elif value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return {key: get_value_or_data_not_entered(value) for key, value in row_data.items()}

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

    # To apply pagination on database query with data size length
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


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_cbe_data(length, year, month, order, query_filters):
    data = AggGovernanceDashboard.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).annotate(
        cbe_conducted_1=Case(
            When(cbe_date_1__isnull=False, then=Value('yes')),
            default=Value('no'),
            output_field=TextField(),
        ),
        cbe_conducted_2=Case(
            When(cbe_date_2__isnull=False, then=Value('yes')),
            default=Value('no'),
            output_field=TextField(),
        ),
    ).values(
        'awc_id',
        'awc_code',
        'cbe_conducted_1',
        'cbe_type_1',
        'cbe_date_1',
        'num_target_beneficiaries_1',
        'num_other_beneficiaries_1',
        'cbe_conducted_2',
        'cbe_type_2',
        'cbe_date_2',
        'num_target_beneficiaries_2',
        'num_other_beneficiaries_2',
    )

    def get_value_or_data_not_entered(value):
        if value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return {key: get_value_or_data_not_entered(value) for key, value in row_data.items()}

    # To apply pagination on database query with data size length
    paginated_data = list(data[:length])
    return [base_data(row) for row in paginated_data], data.count()
