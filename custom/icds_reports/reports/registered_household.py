from __future__ import absolute_import, division

from __future__ import unicode_literals
from collections import OrderedDict, defaultdict
from datetime import datetime

import six
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude, indian_formatted_number, get_child_locations


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_registered_household_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggAwcMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            household=Sum('cases_household'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)
        if not show_test:
            queryset = apply_exclude(domain, queryset)

        return queryset

    data_for_map = defaultdict(lambda: {
        'household': 0,
        'original_name': [],
        'fillKey': 'Household'
    })
    average = []

    for row in get_data_for(config):
        household = row['household'] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name

        average.append(household)
        data_for_map[on_map_name]['household'] += household
        data_for_map[on_map_name]['original_name'].append(name)

    fills = OrderedDict()
    fills.update({'Household': MapColors.BLUE})
    fills.update({'defaultFill': MapColors.GREY})

    return {
        "slug": "registered_household",
        "label": "",
        "fills": fills,
        "rightLegend": {
            "average": sum(average) / float(len(average) or 1),
            "average_format": 'number',
            "info": _("Total number of households registered: %s" % indian_formatted_number(sum(average)))
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_registered_household_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

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

    loc_children = get_child_locations(domain, location_id, show_test)
    result_set = set()

    for row in data:
        name = row['%s_name' % loc_level]
        household = row['household']
        result_set.add(name)

        row_values = {
            'household': household
        }
        for prop, value in six.iteritems(row_values):
            tooltips_data[name][prop] += value

    for name, value_dict in six.iteritems(tooltips_data):
        chart_data['blue'].append([name, value_dict['household'] or 0])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "format": "number",
        "info": _("Total number of households registered"),
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


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
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

        if date.month == month.month:
            if location in best_worst:
                best_worst[location].append(household)
            else:
                best_worst[location] = [household]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['blue'][date_in_miliseconds]['y'] += household

    all_locations = [
        {
            'loc_name': key,
            'value': sum(value) / len(value)
        }
        for key, value in six.iteritems(best_worst)
    ]
    all_locations_sorted_by_name = sorted(all_locations, key=lambda x: x['loc_name'])
    all_locations_sorted_by_value_and_name = sorted(
        all_locations_sorted_by_name, key=lambda x: x['value'], reverse=True)

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in six.iteritems(data['blue'])
                ],
                "key": "Registered Households",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "all_locations": all_locations_sorted_by_value_and_name,
        "top_five": all_locations_sorted_by_value_and_name[:5],
        "bottom_five": all_locations_sorted_by_value_and_name[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }
