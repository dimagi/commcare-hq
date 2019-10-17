from custom.icds_reports.models import AggAwcDailyView
from dateutil.relativedelta import relativedelta
from io import StringIO
from custom.icds_reports.utils import apply_exclude
import csv
from datetime import date


def _get_data_for_daily_indicators(filters, domain, show_test=False):
    queryset = AggAwcDailyView.objects.filter(
        **filters
    ).values('state_name', 'num_launched_awcs', 'daily_attendance_open',
             'total_eligible_pse', 'total_attended_pse')
    if not show_test:
        queryset = apply_exclude(domain, queryset)
    return queryset


def get_daily_indicators(domain):
    today_date = date.today()
    filters = {
        'aggregation_level': 1,
        'date': today_date
    }
    daily_yesterday = None
    while daily_yesterday is None or (not daily_yesterday and date.day != 1):
        filename = 'CAS_Daily_Status_{}.csv'.format(filters['date'].strftime('%Y%m%d'))
        filters['date'] -= relativedelta(days=1)
        daily_yesterday = _get_data_for_daily_indicators(filters, domain)

    columns = ['State', 'Total Anganwadis having ICDS CAS', 'Number of  anganwadis open',
               'Percentage of anganwadis open',
               'Total Number of Children eligible for PSE',
               'Total Number of Children Attended PSE',
               'Percentage of Children attended PSE']
    rows = [columns]

    total_launched = 0
    total_open = 0
    total_pse_eligible = 0
    total_pse_attended = 0

    for data in daily_yesterday:
        percent_awc_open = 0
        percent_pse_attended = 0

        if data['num_launched_awcs']:
            percent_awc_open = round(data['daily_attendance_open'] / data['num_launched_awcs'] * 100, 2)

        if data['total_eligible_pse']:
            percent_pse_attended = round(data['total_attended_pse'] / data['total_eligible_pse'] * 100, 2)

        rows.append([
            data['state_name'],
            data['num_launched_awcs'],
            data['daily_attendance_open'],
            '{}%'.format(percent_awc_open),
            data['total_eligible_pse'],
            data['total_attended_pse'],
            '{}%'.format(percent_pse_attended)
        ])

        total_launched += data['num_launched_awcs']
        total_open += data['daily_attendance_open']
        total_pse_eligible += data['total_eligible_pse']
        total_pse_attended += data['total_attended_pse']

    rows.append([
        'Total',
        total_launched,
        total_open,
        round(total_open / total_launched * 100, 2) if total_launched else 0,
        total_pse_eligible,
        total_pse_attended,
        round(total_pse_attended / total_pse_eligible * 100, 2) if total_pse_eligible else 0,

    ])

    export_file = StringIO()

    writer = csv.writer(export_file)
    writer.writerows(rows)
    export_file.seek(0)
    return filename, export_file
