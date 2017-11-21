from __future__ import absolute_import
from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports.const import LocationTypes, ChartColors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude
import six


RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_newborn_with_low_birth_weight_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            low_birth=Sum('low_birth_weight_in_month'),
            in_month=Sum('born_in_month'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}
    low_birth_total = 0
    in_month_total = 0

    for row in get_data_for(config):
        name = row['%s_name' % loc_level]

        low_birth = row['low_birth']
        in_month = row['in_month']

        low_birth_total += (low_birth or 0)
        in_month_total += (in_month or 0)

        value = (low_birth or 0) * 100 / (in_month or 1)
        row_values = {
            'low_birth': low_birth,
            'in_month': in_month,
        }
        if value < 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 <= value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': PINK})
    fills.update({'20%-60%': ORANGE})
    fills.update({'60%-100%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "low_birth",
            "label": "Percent Newborns with Low Birth Weight",
            "fills": fills,
            "rightLegend": {
                "average": (low_birth_total * 100) / float(in_month_total or 1),
                "info": _((
                    "Percentage of newborns with born with birth weight less than 2500 grams."
                    "<br/><br/>"
                    "Newborns with Low Birth Weight are closely associated with foetal and neonatal "
                    "mortality and morbidity, inhibited growth and cognitive development, and chronic "
                    "diseases later in life"
                ))
            },
            "data": map_data,
        }
    ]


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_newborn_with_low_birth_weight_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        low_birth=Sum('low_birth_weight_in_month'),
        in_month=Sum('born_in_month'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0, 'low_birth': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        low_birth = row['low_birth']

        best_worst[location] = (low_birth or 0) * 100 / float(in_month or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data_for_month = data['blue'][date_in_miliseconds]
        data_for_month['low_birth'] += low_birth
        data_for_month['all'] += in_month
        data_for_month['y'] = data_for_month['low_birth'] / float(data_for_month['all'] or 1)

    top_locations = sorted(
        [dict(loc_name=key, percent=val) for key, val in six.iteritems(best_worst)],
        key=lambda x: x['percent']
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all'],
                        'low_birth': val['low_birth']
                    } for key, val in six.iteritems(data['blue'])
                ],
                "key": "% Newborns with Low Birth Weight",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "all_locations": top_locations,
        "top_five": top_locations[:5],
        "bottom_five": top_locations[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


@quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_newborn_with_low_birth_weight_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        low_birth=Sum('low_birth_weight_in_month'),
        in_month=Sum('born_in_month'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'in_month': 0,
        'low_birth': 0,
    })

    loc_children = SQLLocation.objects.get(location_id=location_id).get_children()
    result_set = set()

    for row in data:
        in_month = row['in_month']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        low_birth = row['low_birth'] or 0

        value = low_birth / float(in_month or 1)

        tooltips_data[name]['low_birth'] += low_birth
        tooltips_data[name]['in_month'] += (in_month or 0)

        chart_data['blue'].append([
            name, value
        ])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "info": _((
            "Percentage of newborns with born with birth weight less than 2500 grams."
            "<br/><br/>"
            "Newborns with Low Birth Weight are closely associated with foetal and neonatal "
            "mortality and morbidity, inhibited growth and cognitive development, and chronic "
            "diseases later in life"
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
