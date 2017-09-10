from collections import OrderedDict, defaultdict
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import LocationTypes
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude


RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


def get_registered_household_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggAwcMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            household=Sum('cases_household'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)

        return queryset

    average = []
    map_data = {}
    for row in get_data_for(config):
        name = row['%s_name' % loc_level]
        household = row['household']
        average.append(household)
        row_values = {
            'household': household,
            'fillKey': 'Household',
        }

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'Household': BLUE})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "registered_household",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / float(len(average) or 1),
                "average_format": 'number',
                "info": _("Total number of households registered"),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_registered_household_sector_data(domain, config, loc_level, show_test=False):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])

    data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        household=Sum('cases_household'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': []
    }

    tooltips_data = defaultdict(lambda: {
        'household': 0
    })

    for row in data:
        name = row['%s_name' % loc_level]
        household = row['household']

        row_values = {
            'household': household
        }
        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += value

    for name, value_dict in tooltips_data.iteritems():
        chart_data['blue'].append([name, value_dict['household'] or 0])

    return {
        "tooltips_data": tooltips_data,
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "Registered household",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ]
    }
