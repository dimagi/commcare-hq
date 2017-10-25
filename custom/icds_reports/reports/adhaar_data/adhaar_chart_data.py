from collections import OrderedDict, defaultdict

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum

from custom.icds_reports.const import Colors, LocationTypes
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.reports.abc.report_data_abc import ChartReportDataABC


class AdhaarChartData(ChartReportDataABC):

    def get_data(self):
        three_before = self.date - relativedelta(months=3)

        chart_data = AggAwcMonthly.objects.filter(
            **self.filters
        ).values(
            'month', '%s_name' % self.location_level
        ).annotate(
            in_month=Sum('cases_person_has_aadhaar'),
            all=Sum('cases_person_beneficiary'),
        ).order_by('month')

        if not self.include_test:
            chart_data = self.apply_exclude(chart_data)

        data = {
            'blue': OrderedDict(),
        }

        dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=self.date)]

        for date in dates:
            miliseconds = int(date.strftime("%s")) * 1000
            data['blue'][miliseconds] = {'y': 0, 'all': 0}

        best_worst = defaultdict(lambda: {
            'in_month': 0,
            'all': 0
        })
        for row in chart_data:
            date = row['month']
            in_month = row['in_month']
            location = row['%s_name' % self.location_level]
            valid = row['all']

            best_worst[location]['in_month'] = in_month
            best_worst[location]['all'] = (valid or 0)

            date_in_miliseconds = int(date.strftime("%s")) * 1000

            data['blue'][date_in_miliseconds]['y'] += in_month
            data['blue'][date_in_miliseconds]['all'] += valid

        top_locations = sorted(
            [
                dict(
                    loc_name=key,
                    percent=(value['in_month'] * 100) / float(value['all'] or 1)
                ) for key, value in best_worst.iteritems()
            ],
            key=lambda x: x['percent'],
            reverse=True
        )

        loc_level = self.location_level

        return {
            "chart_data": [
                {
                    "values": [
                        {
                            'x': key,
                            'y': value['y'] / float(value['all'] or 1),
                            'all': value['all']
                        } for key, value in data['blue'].iteritems()
                    ],
                    "key": "Percentage of beneficiaries with Adhaar numbers",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": Colors.BLUE
                }
            ],
            "all_locations": top_locations,
            "top_five": top_locations[:5],
            "bottom_five": top_locations[-5:],
            "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
        }
