from __future__ import absolute_import, division

from __future__ import unicode_literals
from collections import OrderedDict, defaultdict
from datetime import datetime

import six
from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.messages import early_initiation_breastfeeding_help_text
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude, generate_data_for_map, chosen_filters_to_labels, \
    indian_formatted_number, get_child_locations


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_early_initiation_breastfeeding_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            birth=Sum('bf_at_birth'),
            in_month=Sum('born_in_month'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    data_for_map, in_month_total, birth_total, average, total = generate_data_for_map(
        get_data_for(config),
        loc_level,
        'birth',
        'in_month',
        20,
        60
    )

    fills = OrderedDict()
    fills.update({'0%-20%': MapColors.RED})
    fills.update({'20%-60%': MapColors.ORANGE})
    fills.update({'60%-100%': MapColors.PINK})
    fills.update({'defaultFill': MapColors.GREY})

    gender_ignored, age_ignored, chosen_filters = chosen_filters_to_labels(config)

    return {
        "slug": "early_initiation",
        "label": "Percent Early Initiation of Breastfeeding{}".format(chosen_filters),
        "fills": fills,
        "rightLegend": {
            "average": average,
            "info": early_initiation_breastfeeding_help_text(html=True),
            "extended_info": [
                {
                    'indicator': 'Total Number of Children born in the given month{}:'.format(chosen_filters),
                    'value': indian_formatted_number(in_month_total)
                },
                {
                    'indicator': (
                        'Total Number of Children who were put to the breast within one hour of birth{}:'
                        .format(chosen_filters)
                    ),
                    'value': indian_formatted_number(birth_total)
                },
                {
                    'indicator': '% children who were put to the breast within one hour of '
                                 'birth{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (birth_total * 100 / float(in_month_total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_early_initiation_breastfeeding_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        birth=Sum('bf_at_birth'),
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
        data['blue'][miliseconds] = {'y': 0, 'all': 0, 'birth': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        birth = row['birth']

        best_worst[location] = (birth or 0) * 100 / float(in_month or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000
        data_for_month = data['blue'][date_in_miliseconds]

        data_for_month['all'] += in_month
        data_for_month['birth'] += birth
        data_for_month['y'] = data_for_month['birth'] / float(data_for_month['all'] or 1)

    all_locations = [
        {
            'loc_name': key,
            'percent': val
        }
        for key, val in six.iteritems(best_worst)
    ]
    all_locations_sorted_by_name = sorted(all_locations, key=lambda x: x['loc_name'])
    all_locations_sorted_by_percent_and_name = sorted(
        all_locations_sorted_by_name, key=lambda x: x['percent'], reverse=True)

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all'],
                        'birth': val['birth']
                    } for key, val in six.iteritems(data['blue'])
                ],
                "key": "% Early Initiation of Breastfeeding",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "all_locations": all_locations_sorted_by_percent_and_name,
        "top_five": all_locations_sorted_by_percent_and_name[:5],
        "bottom_five": all_locations_sorted_by_percent_and_name[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_early_initiation_breastfeeding_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        birth=Sum('bf_at_birth'),
        in_month=Sum('born_in_month'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'in_month': 0,
        'birth': 0,
    })

    loc_children = get_child_locations(domain, location_id, show_test)
    result_set = set()

    for row in data:
        in_month = row['in_month']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        birth = row['birth']

        value = (birth or 0) / float(in_month or 1)

        tooltips_data[name]['birth'] += birth
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
        "info": early_initiation_breastfeeding_help_text(html=True),
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": MapColors.BLUE
            }
        ]
    }
