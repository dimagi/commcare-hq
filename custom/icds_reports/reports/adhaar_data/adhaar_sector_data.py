from collections import defaultdict
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import Colors
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.reports.abc.report_data_abc import ReportDataABC


class AdhaarSectorData(ReportDataABC):

    def get_data(self):
        data = AggAwcMonthly.objects.filter(
            month=self.date,
            **self.location_filter_data
        ).values(
            *self.group_by
        ).annotate(
            in_month=Sum('cases_person_has_aadhaar'),
            all=Sum('cases_person_beneficiary'),
        ).order_by('%s_name' % self.location_level)

        if not self.include_test:
            data = self.apply_exclude(data)

        chart_data = {
            'blue': [],
        }

        tooltips_data = defaultdict(lambda: {
            'in_month': 0,
            'all': 0
        })

        loc_children = self.location.get_children()
        result_set = set()

        for row in data:
            valid = row['all']
            name = row['%s_name' % self.location_level]
            result_set.add(name)

            in_month = row['in_month']

            row_values = {
                'in_month': in_month or 0,
                'all': valid or 0
            }
            for prop, value in row_values.iteritems():
                tooltips_data[name][prop] += value

            value = (in_month or 0) / float(valid or 1)

            chart_data['blue'].append([
                name,
                value
            ])

        for sql_location in loc_children:
            if sql_location.name not in result_set:
                chart_data['blue'].append([sql_location.name, 0])

        chart_data['blue'] = sorted(chart_data['blue'])

        return {
            "tooltips_data": tooltips_data,
            "info": _((
                "Percentage of individuals registered using CAS whose Adhaar identification has been captured"
            )),
            "chart_data": [
                {
                    "values": chart_data['blue'],
                    "key": "",
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": Colors.BLUE
                },
            ]
        }
