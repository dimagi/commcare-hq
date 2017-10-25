from collections import OrderedDict

from django.db.models.aggregates import Sum

from custom.icds_reports.const import Colors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.reports.abc.report_data_abc import MapReportDataABC

from django.utils.translation import ugettext as _


class PrevalenceOfUndernutritionMapData(MapReportDataABC):

    def get_data(self):
        queryset = AggChildHealthMonthly.objects.filter(
            **self.filters
        ).values(
            '%s_name' % self.location_level
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            normal=Sum('nutrition_status_normal'),
            valid=Sum('wer_eligible'),
        )
        if not self.include_test:
            queryset = self.apply_exclude(queryset)

        map_data = {}
        moderately_underweight_total = 0
        severely_underweight_total = 0
        valid_total = 0

        for row in queryset:
            valid = row['valid']
            name = row['%s_name' % self.location_level]

            severely_underweight = row['severely_underweight']
            moderately_underweight = row['moderately_underweight']
            normal = row['normal']

            value = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / (valid or 1)

            moderately_underweight_total += (moderately_underweight or 0)
            severely_underweight_total += (severely_underweight_total or 0)
            valid_total += (valid or 0)

            row_values = {
                'severely_underweight': severely_underweight or 0,
                'moderately_underweight': moderately_underweight or 0,
                'total': valid or 0,
                'normal': normal
            }
            if value < 20:
                row_values.update({'fillKey': '0%-20%'})
            elif 20 <= value < 35:
                row_values.update({'fillKey': '20%-35%'})
            elif value >= 35:
                row_values.update({'fillKey': '35%-100%'})

            map_data.update({name: row_values})

        fills = OrderedDict()
        fills.update({'0%-20%': Colors.PINK})
        fills.update({'20%-35%': Colors.ORANGE})
        fills.update({'35%-100%': Colors.RED})
        fills.update({'defaultFill': Colors.GREY})

        average = ((moderately_underweight_total + severely_underweight_total) * 100) / (valid_total or 1)

        return [
            {
                "slug": "moderately_underweight",
                "label": "Percent of Children Underweight (0-5 years)",
                "fills": fills,
                "rightLegend": {
                    "average": average,
                    "info": _((
                        "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age "
                        "less than -2 standard deviations of the WHO Child Growth Standards median. "
                        "<br/><br/>"
                        "Children who are moderately or severely underweight have a higher risk of mortality"
                    ))
                },
                "data": map_data,
            }
        ]
