from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import DATA_NOT_ENTERED
from django.db.models import F


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
            month=get_value_or_data_not_entered(row_data, 'month'),
            valid_visits=get_value_or_data_not_entered(row_data, 'valid_visits'),
            expected_visits=get_value_or_data_not_entered(row_data, 'expected_visits'),
        )

    data_rows = []
    for row in paginated_data:
        data_rows.append(base_data(row))
    return data_rows, data.count()


@icds_quickcache(['start', 'length', 'year', 'month', 'order', 'query_filters'], timeout=30 * 60)
def get_beneficiary_data(start, length, year, month, order, query_filters):
    data = AggAwcMonthly.objects.filter(
        month=date(year, month, 1),
        **query_filters
    ).order_by(*order).values(
        'month',
        state=F('state_name'),
        district=F('district_name'),
        block=F('block_name'),
        sector=F('supervisor_name'),
        awc=F('awc_name'),
        total_preg_benefit_till_date=F('cases_ccs_pregnant'),
        total_lact_benefit_till_date=F('cases_ccs_lactating'),
        total_preg_reg_till_date=F('cases_ccs_pregnant_all'),
        total_lact_reg_till_date=F('cases_ccs_lactating_all'),
        total_lact_benefit_in_month=F('cases_ccs_lactating_reg_in_month'),
        total_preg_benefit_in_month=F('cases_ccs_pregnant_reg_in_month'),
        total_lact_reg_in_month=F('cases_ccs_lactating_all_reg_in_month'),
        total_preg_reg_in_month=F('cases_ccs_pregnant_all_reg_in_month'),
        total_0_3_female_benefit_till_date=F('valid_all_0_3_female'),
        total_0_3_male_benefit_till_date=F('valid_all_0_3_male'),
        total_0_3_female_reg_till_date=F('open_all_0_3_female'),
        total_0_3_male_reg_till_date=F('open_all_0_3_male'),
        total_3_6_female_benefit_till_date=F('valid_all_3_6_female'),
        total_3_6_male_benefit_till_date=F('valid_all_3_6_male'),
        total_3_6_female_reg_till_date=F('open_all_3_6_female'),
        total_3_6_male_reg_till_date=F('open_all_3_6_male'),
        total_0_3_female_benefit_in_month=F('valid_reg_in_month_0_3_female'),
        total_0_3_male_benefit_in_month=F('valid_reg_in_month_0_3_male'),
        total_0_3_female_reg_in_month=F('open_reg_in_month_0_3_female'),
        total_0_3_male_reg_in_month=F('open_reg_in_month_0_3_male'),
        total_3_6_female_benefit_in_month=F('valid_reg_in_month_3_6_female'),
        total_3_6_male_benfit_in_month=F('valid_reg_in_month_3_6_male'),
        total_3_6_female_reg_in_month=F('open_reg_in_month_3_6_female'),
        total_3_6_male_reg_in_month=F('open_reg_in_month_3_6_male'),

    )

    # To apply pagination on database query with offset and limit
    paginated_data = data[int(start):(int(start) + length)]

    def get_value_or_data_not_entered(value):
        if value is None:
            return DATA_NOT_ENTERED
        return value

    def base_data(row_data):
        return {key: get_value_or_data_not_entered(value) for key, value in row_data.items()}

    return [base_data(row) for row in paginated_data], data.count()
