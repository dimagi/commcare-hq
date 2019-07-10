from __future__ import absolute_import, division

from __future__ import unicode_literals
from collections import OrderedDict, defaultdict
from datetime import datetime

import six
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum, Max
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.messages import awcs_launched_help_text
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude, indian_formatted_number, get_child_locations


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_awcs_covered_data_map(domain, config, loc_level, show_test=False):
    level = config['aggregation_level']

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggAwcMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            states=Sum('num_launched_states') if level <= 1 else Max('num_launched_states'),
            districts=Sum('num_launched_districts') if level <= 2 else Max('num_launched_districts'),
            blocks=Sum('num_launched_blocks') if level <= 3 else Max('num_launched_blocks'),
            supervisors=Sum('num_launched_supervisors') if level <= 4 else Max('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs') if level <= 5 else Max('num_launched_awcs'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    data_for_map = defaultdict(lambda: {
        'awcs': [],
        'supervisors': [],
        'blocks': [],
        'districts': [],
        'states': [],
        'original_name': []
    })

    for row in get_data_for(config):
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        awcs = row['awcs'] or 0
        supervisors = row['supervisors'] or 0
        blocks = row['blocks'] or 0
        districts = row['districts'] or 0
        states = row['states'] or 0

        data_for_map[on_map_name]['awcs'].append(awcs)
        data_for_map[on_map_name]['supervisors'].append(supervisors)
        data_for_map[on_map_name]['blocks'].append(blocks)
        data_for_map[on_map_name]['districts'].append(districts)
        data_for_map[on_map_name]['states'].append(states)
        data_for_map[on_map_name]['original_name'].append(name)

    for data_for_location in six.itervalues(data_for_map):
        data_for_location['awcs'] = (
            sum(data_for_location['awcs']) if level <= 5 else max(data_for_location['awcs'])
        )
        data_for_location['supervisors'] = (
            sum(data_for_location['supervisors']) if level <= 4 else max(data_for_location['supervisors'])
        )
        data_for_location['blocks'] = (
            sum(data_for_location['blocks']) if level <= 3 else max(data_for_location['blocks'])
        )
        data_for_location['districts'] = (
            sum(data_for_location['districts']) if level <= 2 else max(data_for_location['districts'])
        )
        data_for_location['states'] = (
            sum(data_for_location['states']) if level <= 1 else max(data_for_location['states'])
        )
        data_for_location.update({'fillKey': 'Launched' if data_for_location['awcs'] > 0 else 'Not launched'})

    if level == 1:
        prop = 'states'
    elif level == 2:
        prop = 'districts'
    elif level == 3:
        prop = 'blocks'
    elif level == 4:
        prop = 'supervisors'
    else:
        prop = 'awcs'

    total_awcs = sum([(x['awcs'] or 0) for x in six.itervalues(data_for_map)])
    total = sum([(x[prop] or 0) for x in six.itervalues(data_for_map)])

    fills = OrderedDict()
    fills.update({'Launched': MapColors.PINK})
    fills.update({'Not launched': MapColors.GREY})
    fills.update({'defaultFill': MapColors.GREY})

    info = _(
        "{:s}<br /><br />"
        "Number of AWCs launched: {:s}".format(
            awcs_launched_help_text(),
            indian_formatted_number(total_awcs)
        )
    )
    if level != 5:
        info = _(
            "{:s}<br /><br />"
            "Number of AWCs launched: {:s} <br />"
            "Number of {:s} launched: {:s}".format(
                awcs_launched_help_text(),
                indian_formatted_number(total_awcs),
                prop.title(),
                indian_formatted_number(total)
            )
        )

    return {
        "slug": "awc_covered",
        "label": "",
        "fills": fills,
        "rightLegend": {
            "info": info
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_awcs_covered_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])

    level = config['aggregation_level']
    data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        states=Sum('num_launched_states') if level <= 1 else Max('num_launched_states'),
        districts=Sum('num_launched_districts') if level <= 2 else Max('num_launched_districts'),
        blocks=Sum('num_launched_blocks') if level <= 3 else Max('num_launched_blocks'),
        supervisors=Sum('num_launched_supervisors') if level <= 4 else Max('num_launched_supervisors'),
        awcs=Sum('num_launched_awcs') if level <= 5 else Max('num_launched_awcs'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'districts': 0,
        'blocks': 0,
        'states': 0,
        'supervisors': 0,
        'awcs': 0
    })

    loc_children = get_child_locations(domain, location_id, show_test)
    result_set = set()

    for row in data:
        name = row['%s_name' % loc_level]
        awcs = row['awcs'] or 0
        supervisors = row['supervisors'] or 0
        blocks = row['blocks'] or 0
        districts = row['districts'] or 0
        states = row['states'] or 0
        result_set.add(name)

        row_values = {
            'awcs': awcs,
            'supervisors': supervisors,
            'blocks': blocks,
            'districts': districts,
            'states': states,
        }
        for prop, value in six.iteritems(row_values):
            tooltips_data[name][prop] += (value or 0)

    for name, value_dict in six.iteritems(tooltips_data):
        chart_data['blue'].append([name, value_dict['awcs']])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    if level == 1:
        prop = 'states'
    elif level == 2:
        prop = 'districts'
    elif level == 3:
        prop = 'blocks'
    elif level == 4:
        prop = 'supervisors'
    else:
        prop = 'awcs'

    total_awcs = sum([(x['awcs'] or 0) for x in six.itervalues(tooltips_data)])
    total = sum([(x[prop] or 0) for x in six.itervalues(tooltips_data)])

    info = _(
        "{:s}<br /><br />"
        "Number of AWCs launched: {:d}".format(awcs_launched_help_text(), total_awcs)
    )
    if level != 5:
        info = _(
            "{:s}<br /><br />"
            "Number of AWCs launched: {:d} <br />"
            "Number of {:s} launched: {:d}".format(awcs_launched_help_text(), total_awcs, prop.title(), total)
        )

    return {
        "tooltips_data": dict(tooltips_data),
        "format": "number",
        "info": info,
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
def get_awcs_covered_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    level = config['aggregation_level']
    chart_data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        awcs=Sum('num_launched_awcs') if level <= 5 else Max('num_launched_awcs'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'pink': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['pink'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        awcs = (row['awcs'] or 0)
        location = row['%s_name' % loc_level]

        if date.month == month.month:
            if location in best_worst:
                best_worst[location].append(awcs)
            else:
                best_worst[location] = [awcs]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['pink'][date_in_miliseconds]['y'] += awcs

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
                    } for key, value in six.iteritems(data['pink'])
                ],
                "key": "Number of AWCs Launched",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.PINK
            }
        ],
        "all_locations": all_locations_sorted_by_value_and_name,
        "top_five": all_locations_sorted_by_value_and_name[:5],
        "bottom_five": all_locations_sorted_by_value_and_name[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }
