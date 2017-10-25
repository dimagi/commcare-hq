from collections import OrderedDict

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import Colors
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.reports.abc.report_data_abc import MapReportDataABC


class AdhaarMapData(MapReportDataABC):

    def get_data(self):
        queryset = AggAwcMonthly.objects.filter(
            **self.filters
        ).values(
            '%s_name' % self.location_level
        ).annotate(
            in_month=Sum('cases_person_has_aadhaar'),
            all=Sum('cases_person_beneficiary'),
        )
        if not self.include_test:
            queryset = self.apply_exclude(queryset)

        map_data = {}
        valid_total = 0
        in_month_total = 0

        for row in queryset:
            valid = row['all']
            name = row['%s_name' % self.location_level]

            in_month = row['in_month']

            value = (in_month or 0) * 100 / (valid or 1)

            valid_total += (valid or 0)
            in_month_total += (in_month or 0)

            row_values = {
                'in_month': in_month or 0,
                'all': valid or 0
            }
            if value < 25:
                row_values.update({'fillKey': '0%-25%'})
            elif 25 <= value <= 50:
                row_values.update({'fillKey': '25%-50%'})
            elif value > 50:
                row_values.update({'fillKey': '50%-100%'})

            map_data.update({name: row_values})

        fills = OrderedDict()
        fills.update({'0%-25%': Colors.RED})
        fills.update({'25%-50%': Colors.ORANGE})
        fills.update({'50%-100%': Colors.PINK})
        fills.update({'defaultFill': Colors.GREY})

        return [
            {
                "slug": "adhaar",
                "label": "Percent Adhaar-seeded Beneficiaries",
                "fills": fills,
                "rightLegend": {
                    "average": (in_month_total * 100) / float(valid_total or 1),
                    "info": _((
                        "Percentage of individuals registered using"
                        " CAS whose Adhaar identification has been captured"
                    ))
                },
                "data": map_data,
            }
        ]
