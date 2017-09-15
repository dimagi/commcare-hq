from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
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


def get_registered_household_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        household=Sum('cases_household'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        household = (row['household'] or 0)
        location = row['%s_name' % loc_level]

        if location in best_worst:
            best_worst[location].append(household)
        else:
            best_worst[location] = [household]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['blue'][date_in_miliseconds]['y'] += household

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

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
                "key": "Registered Households",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }
