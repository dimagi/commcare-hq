from collections import defaultdict
from django.db.models.aggregates import Sum

from custom.icds_reports.const import Colors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.reports.abc.report_data_abc import SectorReportDataABC

from django.utils.translation import ugettext as _


class PrevalenceOfUndernutritionSectorData(SectorReportDataABC):

    def get_data(self):
        group_by = ['%s_name' % self.location_level]

        data = AggChildHealthMonthly.objects.filter(
            **self.filters
        ).values(
            *group_by
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            valid=Sum('wer_eligible'),
            normal=Sum('nutrition_status_normal')
        ).order_by('%s_name' % self.location_level)

        if not self.include_test:
            data = self.apply_exclude(data)

        chart_data = {
            'blue': []
        }

        tooltips_data = defaultdict(lambda: {
            'severely_underweight': 0,
            'moderately_underweight': 0,
            'total': 0,
            'normal': 0
        })

        loc_children = self.location.get_children()
        result_set = set()

        for row in data:
            valid = row['valid']
            name = row['%s_name' % self.location_level]
            result_set.add(name)

            severely_underweight = row['severely_underweight']
            moderately_underweight = row['moderately_underweight']
            normal = row['normal']

            tooltips_data[name]['severely_underweight'] += severely_underweight
            tooltips_data[name]['moderately_underweight'] += moderately_underweight
            tooltips_data[name]['total'] += (valid or 0)
            tooltips_data[name]['normal'] += normal

            chart_data['blue'].append([
                name,
                ((moderately_underweight or 0) + (severely_underweight or 0)) / float(valid or 1)
            ])

        for sql_location in loc_children:
            if sql_location.name not in result_set:
                chart_data['blue'].append([sql_location.name, 0])

        chart_data['blue'] = sorted(chart_data['blue'])

        return {
            "tooltips_data": dict(tooltips_data),
            "info": _((
                "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age "
                "less than -2 standard deviations of the WHO Child Growth Standards median. "
                "<br/><br/>"
                "Children who are moderately or severely underweight have a higher risk of mortality"
            )),
            "chart_data": [
                {
                    "values": chart_data['blue'],
                    "key": "",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": Colors.BLUE
                }
            ]
        }
