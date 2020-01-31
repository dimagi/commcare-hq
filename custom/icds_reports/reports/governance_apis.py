from datetime import date

from django.db.models import F, Case, When, TextField, Value

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.aggregate import AggGovernanceDashboard
from custom.icds_reports.const import AggregationLevels
from custom.icds_reports.models import AggAwcMonthly, AwcLocation


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_home_visit_data(length, year, month, order, query_filters):
    data = AggAwcMonthly.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).annotate(awc_code=F('awc_site_code')).values(
        'awc_id', 'awc_code', 'valid_visits', 'expected_visits'
    )
    paginated_data = list(data[:length])

    return paginated_data, data.count()


@icds_quickcache(['length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_vhnd_data(length, year, month, order, query_filters):

    def yes_no_or_null(col_name):
        when_true = {col_name: 1, 'then': Value('yes')}
        when_false = {col_name: 0, 'then': Value('no')}
        return Case(
            When(**when_true),
            When(**when_false),
            default=None,
            output_field=TextField()
        )

    data = AggGovernanceDashboard.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).values(
        'awc_id',
        'awc_code'
    ).annotate(
        asha_present=yes_no_or_null('asha_present'),
        vhsnd_date=F('vhsnd_date_past_month'),
        anm_present=yes_no_or_null('anm_mpw_present'),
        children_immunized=yes_no_or_null('child_immu'),
        anc_conducted=yes_no_or_null('anc_today'),
        vhsnd_conducted=Case(
            When(vhsnd_date_past_month__isnull=False, then=Value('yes')),
            default=Value('no'),
            output_field=TextField()
        ),
    )

    paginated_data = list(data[:length])

    return paginated_data, data.count()


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
    paginated_data = list(data[:length])

    return paginated_data, data.count()


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

    # To apply pagination on database query with data size length
    paginated_data = list(data[:length])

    return paginated_data, data.count()
