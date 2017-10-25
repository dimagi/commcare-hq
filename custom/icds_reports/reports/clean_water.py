from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.const import LocationTypes
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


def get_clean_water_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggAwcMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_month=Sum('infra_clean_water'),
            all=Sum('num_awcs'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}
    in_month_total = 0
    valid_total = 0

    for row in get_data_for(config):
        valid = row['all']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']

        in_month_total += (in_month or 0)
        valid_total += (valid or 0)

        value = (in_month or 0) * 100 / (valid or 1)
        row_values = {
            'in_month': in_month or 0,
            'all': valid or 0
        }
        if value < 25:
            row_values.update({'fillKey': '0%-25%'})
        elif 25 <= value < 75:
            row_values.update({'fillKey': '25%-75%'})
        elif value >= 75:
            row_values.update({'fillKey': '75%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-25%': RED})
    fills.update({'25%-75%': ORANGE})
    fills.update({'75%-100%': PINK})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "clean_water",
            "label": "Percent AWCs with Clean Drinking Water",
            "fills": fills,
            "rightLegend": {
                "average": (in_month_total * 100) / float(valid_total or 1),
                "info": _((
                    "Percentage of AWCs with a source of clean drinking water"
                ))
            },
            "data": map_data,
        }
    ]


def get_clean_water_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('infra_clean_water'),
        all=Sum('num_awcs'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0, 'in_month': 0}

    best_worst = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })
    for row in chart_data:
        date = row['month']
        in_month = (row['in_month'] or 0)
        location = row['%s_name' % loc_level]
        valid = row['all']

        best_worst[location]['in_month'] = in_month
        best_worst[location]['all'] = (valid or 0)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['blue'][date_in_miliseconds]['all'] += (valid or 0)
        data['blue'][date_in_miliseconds]['in_month'] += in_month

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

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['in_month'] / float(value['all'] or 1),
                        'in_month': value['in_month']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "% of AWCs with a source of clean drinking water",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            },
        ],
        "all_locations": top_locations,
        "top_five": top_locations[:5],
        "bottom_five": top_locations[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


def get_clean_water_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('infra_clean_water'),
        all=Sum('num_awcs'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })

    loc_children = SQLLocation.objects.get(location_id=location_id).get_children()
    result_set = set()

    for row in data:
        valid = row['all']
        name = row['%s_name' % loc_level]
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
            name, value
        ])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": tooltips_data,
        "info": _((
            "Percentage of AWCs with a source of clean drinking water"
        )),
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            },
        ]
    }
