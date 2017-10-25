from collections import OrderedDict

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum

from custom.icds_reports.const import Colors, LocationTypes
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.reports.abc.report_data_abc import ChartReportDataABC


class PrevalenceOfUndernutritionChartData(ChartReportDataABC):

    def get_data(self):
        chart_data = AggChildHealthMonthly.objects.filter(
            **self.filters
        ).values(
            'month', '%s_name' % self.location_level
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            normal=Sum('nutrition_status_normal'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            valid=Sum('valid_in_month'),
        ).order_by('month')

        if not self.include_test:
            chart_data = self.apply_exclude(chart_data)

        data = {
            'peach': OrderedDict(),
            'orange': OrderedDict(),
            'red': OrderedDict()
        }

        three_before = self.date - relativedelta(months=3)
        dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=self.date)]

        for date in dates:
            miliseconds = int(date.strftime("%s")) * 1000
            data['peach'][miliseconds] = {'y': 0, 'all': 0}
            data['orange'][miliseconds] = {'y': 0, 'all': 0}
            data['red'][miliseconds] = {'y': 0, 'all': 0}

        best_worst = {}
        for row in chart_data:
            date = row['month']
            valid = row['valid']
            location = row['%s_name' % self.location_level]
            severely_underweight = row['severely_underweight']
            moderately_underweight = row['moderately_underweight']
            normal = row['normal']

            underweight = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / float(valid or 1)

            best_worst[location] = underweight

            date_in_miliseconds = int(date.strftime("%s")) * 1000

            data['peach'][date_in_miliseconds]['y'] += normal
            data['peach'][date_in_miliseconds]['all'] += valid
            data['orange'][date_in_miliseconds]['y'] += moderately_underweight
            data['orange'][date_in_miliseconds]['all'] += valid
            data['red'][date_in_miliseconds]['y'] += severely_underweight
            data['red'][date_in_miliseconds]['all'] += valid

        top_locations = sorted(
            [dict(loc_name=key, percent=value) for key, value in best_worst.iteritems()],
            key=lambda x: x['percent']
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
                        } for key, value in data['peach'].iteritems()
                    ],
                    "key": "% Normal",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": Colors.PINK
                },
                {
                    "values": [
                        {
                            'x': key,
                            'y': value['y'] / float(value['all'] or 1),
                            'all': value['all']
                        } for key, value in data['orange'].iteritems()
                    ],
                    "key": "% Moderately Underweight (-2 SD)",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": Colors.ORANGE
                },
                {
                    "values": [
                        {
                            'x': key,
                            'y': value['y'] / float(value['all'] or 1),
                            'all': value['all']
                        } for key, value in data['red'].iteritems()
                    ],
                    "key": "% Severely Underweight (-3 SD) ",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": Colors.RED
                }
            ],
            "all_locations": top_locations,
            "top_five": top_locations[:5],
            "bottom_five": top_locations[-5:],
            "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
        }
