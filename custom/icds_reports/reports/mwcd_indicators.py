from datetime import date, timedelta
from custom.icds_reports.models.views import MWCDReportView
from django.db.models import Sum


def get_implementation_status_data():
    latest_month_available = (date.today() - timedelta(days=1)).replace(day=1)

    implementation_stat = MWCDReportView.objects.filter(month=latest_month_available).values(
        'state_name',
        'state_id',
        'num_launched_awcs',
        'num_launched_districts',
        'num_launched_states',
        'awc_with_gm_devices',
        'cases_household',
        'total_mothers',
        'cases_child_health'
    )

    total_count = {
        "nation_code": 0,
        'num_launched_awcs': 0,
        'num_launched_districts': 0,
        'num_launched_states': 0,
        'awc_with_gm_devices': 0,
        'cases_household': 0,
        'total_mothers': 0,
        'cases_child_health': 0
    }

    for record in implementation_stat:
        for key, value in record.items():
            if key not in ['state_name', 'state_id']:
                total_count[key] += value

    return {
        'national_total': total_count,
        'dataarray': list(implementation_stat)
    }


def get_monthly_trend(monthly_trend_start):
    def split_month(records):
        for record in records:
            month_date = record['month']
            record['month'] = month_date.month
            record['year'] = month_date.year

    monthly_trend = MWCDReportView.objects.filter(month__gte=monthly_trend_start).values(
        'state_name', 'state_id', 'month', 'total_mothers',
        'num_launched_awcs', 'cases_child_health')

    trend_at_national_level = MWCDReportView.objects.filter(month__gte=monthly_trend_start).values(
        'month').annotate(total_awc_launched=Sum('num_launched_awcs'),
                          total_mothers=Sum('total_mothers'),
                          total_children=Sum('cases_child_health'))

    split_month(monthly_trend)
    split_month(trend_at_national_level)

    return {
        'national_total': list(trend_at_national_level),
        'dataarray': list(monthly_trend)
    }


def get_mwcd_indicator_api_data(monthly_trend_start=None):
    if monthly_trend_start is None:
        monthly_trend_start = date(2017, 7, 1)
    implementation_status = get_implementation_status_data()
    monthly_trend = get_monthly_trend(monthly_trend_start)

    return {
        "scheme_code": "C002",
        "implementation_status": implementation_status,
        "monthly_trend": monthly_trend
    }
