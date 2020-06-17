from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum, Max
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.messages import ls_launched_help_text
from custom.icds_reports.models.views import SystemUsageReportView
from custom.icds_reports.utils import apply_exclude, indian_formatted_number


def get_prop(level):
    if level == 1:
        return 'states'
    elif level == 2:
        return 'districts'
    elif level == 3:
        return 'blocks'
    elif level == 4:
        return 'sectors'
    else:
        return 'awcs'


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_ls_launched_data_map(domain, config, loc_level, show_test=False):
    level = config['aggregation_level']

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = SystemUsageReportView.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            states=Sum('num_launched_states') if level <= 1 else Max('num_launched_states'),
            districts=Sum('num_launched_districts') if level <= 2 else Max('num_launched_districts'),
            blocks=Sum('num_launched_blocks') if level <= 3 else Max('num_launched_blocks'),
            sectors=Sum('num_launched_supervisors') if level <= 4 else Max('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs') if level <= 5 else Max('num_launched_awcs'),
            ls_launched=Sum('num_supervisor_launched'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    data_for_map = defaultdict(lambda: {
        'awcs': [],
        'sectors': [],
        'blocks': [],
        'districts': [],
        'states': [],
        'original_name': [],
        'ls_launched': []
    })

    for row in get_data_for(config):
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        awcs = row['awcs'] or 0
        sectors = row['sectors'] or 0
        blocks = row['blocks'] or 0
        districts = row['districts'] or 0
        states = row['states'] or 0
        ls_launched = row['ls_launched'] or 0

        data_for_map[on_map_name]['awcs'].append(awcs)
        data_for_map[on_map_name]['sectors'].append(sectors)
        data_for_map[on_map_name]['blocks'].append(blocks)
        data_for_map[on_map_name]['districts'].append(districts)
        data_for_map[on_map_name]['states'].append(states)
        data_for_map[on_map_name]['original_name'].append(name)
        data_for_map[on_map_name]['ls_launched'].append(ls_launched)

    for data_for_location in data_for_map.values():
        data_for_location['ls_launched'] = (
            sum(data_for_location['ls_launched'])
        )
        data_for_location['awcs'] = (
            sum(data_for_location['awcs']) if level <= 5 else max(data_for_location['awcs'])
        )
        data_for_location['sectors'] = (
            sum(data_for_location['sectors']) if level <= 4 else max(data_for_location['sectors'])
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
        data_for_location.update({'fillKey': 'Launched' if data_for_location['ls_launched'] > 0 else 'Not launched'})

    prop = get_prop(level)

    total_lss = sum([(x['ls_launched'] or 0) for x in data_for_map.values()])
    total = sum([(x[prop] or 0) for x in data_for_map.values()])

    fills = OrderedDict()
    fills.update({'Launched': MapColors.PINK})
    fills.update({'Not launched': MapColors.GREY})
    fills.update({'defaultFill': MapColors.GREY})

    info = _(
        "{:s}<br /><br />"
        "Not applicable at AWC level".format(
            ls_launched_help_text()
        )
    )
    if level <= 5:
        info = _(
            "{:s}<br /><br />"
            "Number of LSs launched: {:s} <br />"
            "Number of {:s} launched: {:s}".format(
                ls_launched_help_text(),
                indian_formatted_number(total_lss),
                prop.title(),
                indian_formatted_number(total)
            )
        )

    return {
        "slug": "ls_launched",
        "label": "",
        "fills": fills,
        "rightLegend": {
            "info": info
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_ls_launched_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])

    level = config['aggregation_level']
    data = SystemUsageReportView.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        states=Sum('num_launched_states') if level <= 1 else Max('num_launched_states'),
        districts=Sum('num_launched_districts') if level <= 2 else Max('num_launched_districts'),
        blocks=Sum('num_launched_blocks') if level <= 3 else Max('num_launched_blocks'),
        sectors=Sum('num_launched_supervisors') if level <= 4 else Max('num_launched_supervisors'),
        awcs=Sum('num_launched_awcs') if level <= 5 else Max('num_launched_awcs'),
        ls_launched=Sum('num_supervisor_launched'),
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
        'sectors': 0,
        'awcs': 0,
        'ls_launched': 0
    })

    for row in data:
        name = row['%s_name' % loc_level]
        awcs = row['awcs'] or 0
        sectors = row['sectors'] or 0
        blocks = row['blocks'] or 0
        districts = row['districts'] or 0
        states = row['states'] or 0
        ls_launched = row['ls_launched'] or 0

        row_values = {
            'awcs': awcs,
            'sectors': sectors,
            'blocks': blocks,
            'districts': districts,
            'states': states,
            'ls_launched': ls_launched,
        }
        for prop, value in row_values.items():
            tooltips_data[name][prop] += (value or 0)

    for name, value_dict in tooltips_data.items():
        chart_data['blue'].append([name, value_dict['ls_launched']])

    chart_data['blue'] = sorted(chart_data['blue'])

    prop = get_prop(level)

    total_lss = sum([(x['ls_launched'] or 0) for x in tooltips_data.values()])
    total = sum([(x[prop] or 0) for x in tooltips_data.values()])

    info = _(
        "{:s}<br /><br />"
        "Not applicable at AWC level".format(ls_launched_help_text())
    )
    if level <= 5:
        info = _(
            "{:s}<br /><br />"
            "Number of LSs launched: {:d} <br />"
            "Number of {:s} launched: {:d}".format(ls_launched_help_text(), total_lss, prop.title(), total)
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
def get_ls_launched_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = SystemUsageReportView.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        ls_launched=Sum('num_supervisor_launched'),
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
        ls_launched = (row['ls_launched'] or 0)
        location = row['%s_name' % loc_level]

        if date.month == month.month:
            if location in best_worst:
                best_worst[location].append(ls_launched)
            else:
                best_worst[location] = [ls_launched]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['pink'][date_in_miliseconds]['y'] += ls_launched

    all_locations = [
        {
            'loc_name': key,
            'value': sum(value) / len(value)
        }
        for key, value in best_worst.items()
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
                    } for key, value in data['pink'].items()
                ],
                "key": "Number of LSs Launched",
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
