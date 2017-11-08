from __future__ import absolute_import
from collections import OrderedDict, defaultdict
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports.const import LocationTypes, ChartColors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude, match_age

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_enrolled_children_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            valid=Sum('valid_in_month'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        average.append(valid)
        row_values = {
            'valid': valid or 0,
            'fillKey': 'Children'
        }

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'Children': BLUE})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "enrolled_children",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / float(len(average) or 1),
                "average_format": 'number',
                "info": _((
                    "Total number of children between the age of 0 - 6 years who are enrolled for ICDS services"
                ))
            },
            "data": map_data,
        }
    ]


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_enrolled_children_data_chart(domain, config, loc_level, show_test=False):
    config['month'] = datetime(*config['month'])

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', 'age_tranche', '%s_name' % loc_level
    ).annotate(
        valid=Sum('valid_in_month'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    chart = OrderedDict()
    chart.update({'0-1 month': 0})
    chart.update({'1-6 months': 0})
    chart.update({'6-12 months': 0})
    chart.update({'1-3 years': 0})
    chart.update({'3-6 years': 0})

    all = 0
    best_worst = {}
    for row in chart_data:
        location = row['%s_name' % loc_level]

        if not row['age_tranche']:
            continue

        age = int(row['age_tranche'])
        valid = row['valid']
        all += valid
        chart[match_age(age)] += valid

        if location in best_worst:
            best_worst[location] += valid
        else:
            best_worst[location] = valid

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value,
                        'all': all
                    } for key, value in chart.iteritems()
                ],
                "key": "Children (0-6 years) who are enrolled",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


@quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_enrolled_children_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        valid=Sum('valid_in_month'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': []
    }

    tooltips_data = defaultdict(lambda: {
        'valid': 0
    })

    loc_children = SQLLocation.objects.get(location_id=location_id).get_children()
    result_set = set()

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        row_values = {
            'valid': valid or 0,
        }

        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += value

        chart_data['blue'].append([
            name, valid
        ])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "format": "number",
        "info": _((
            "Total number of children between the age of 0 - 6 years who are enrolled for ICDS services"
        )),
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ]
    }
