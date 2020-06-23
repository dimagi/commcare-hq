from collections import OrderedDict, defaultdict
from datetime import datetime

from django.db.models.aggregates import Sum

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.messages import percent_children_enrolled_help_text
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude, match_age, chosen_filters_to_labels, \
    indian_formatted_number

from custom.icds_reports.utils import get_location_launched_status


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_features_flag'], timeout=30 * 60)
def get_enrolled_children_data_map(domain, config, loc_level, show_test=False, icds_features_flag=False):
    config['month'] = datetime(*config['month'])

    def get_data_for(filters):
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            valid=Sum('valid_in_month'),
            all=Sum('valid_all_registered_in_month')
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)
        if not show_test:
            queryset = apply_exclude(domain, queryset)

        return queryset

    data_for_map = defaultdict(lambda: {
        'valid': 0,
        'all': 0,
        'original_name': [],
        'fillKey': 'Children'
    })
    average = []
    total_valid = 0
    total = 0
    if icds_features_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in get_data_for(config):
        if location_launched_status:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
        valid = row['valid'] or 0
        name = row['%s_name' % loc_level]
        all_children = row['all'] or 0
        on_map_name = row['%s_map_location_name' % loc_level] or name

        average.append(valid)
        total_valid += valid
        total += all_children
        data_for_map[on_map_name]['valid'] += valid
        data_for_map[on_map_name]['all'] += all_children
        data_for_map[on_map_name]['original_name'].append(name)

    fills = OrderedDict()
    fills.update({'Children': MapColors.BLUE})
    if icds_features_flag:
        fills.update({'Not Launched': MapColors.GREY})
    fills.update({'defaultFill': MapColors.GREY})

    gender_ignored, age_label, chosen_filters = chosen_filters_to_labels(config, default_interval='0 - 6 years')

    return {
        "slug": "enrolled_children",
        "label": "",
        "fills": fills,
        "rightLegend": {
            "average": '%.2f' % (total_valid * 100 / float(total or 1)),
            "info": percent_children_enrolled_help_text(age_label=age_label),
            "extended_info": [
                {
                    'indicator':
                        'Number of children{} who are enrolled for Anganwadi Services:'
                        .format(chosen_filters),
                    'value': indian_formatted_number(total_valid)
                },
                {
                    'indicator': (
                        'Total number of children{} who are registered: '
                        .format(chosen_filters)
                    ),
                    'value': indian_formatted_number(total)
                },
                {
                    'indicator': (
                        'Percentage of registered children{} who are enrolled for Anganwadi Services:'
                        .format(chosen_filters)
                    ),
                    'value': '%.2f%%' % (total_valid * 100 / float(total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_features_flag'], timeout=30 * 60)
def get_enrolled_children_data_chart(domain, config, loc_level, show_test=False, icds_features_flag=False):
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
    if icds_features_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in chart_data:
        if icds_features_flag:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
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
                    } for key, value in chart.items()
                ],
                "key": "Children (0-6 years) who are enrolled",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test', 'icds_features_flag'], timeout=30 * 60)
def get_enrolled_children_sector_data(domain, config, loc_level, location_id, show_test=False, icds_features_flag=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        valid=Sum('valid_in_month'),
        all=Sum('valid_all_registered_in_month')
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': []
    }

    tooltips_data = defaultdict(lambda: {
        'valid': 0,
        'all': 0
    })
    if icds_features_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in data:
        if location_launched_status:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
        valid = row['valid'] or 0
        all_children = row['all'] or 0
        name = row['%s_name' % loc_level]

        row_values = {
            'valid': valid,
            'all': all_children
        }

        for prop, value in row_values.items():
            tooltips_data[name][prop] += value

        chart_data['blue'].append([
            name, valid
        ])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "format": "number",
        "info": percent_children_enrolled_help_text(),
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
