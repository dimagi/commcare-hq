from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors, AggregationLevels
from custom.icds_reports.messages import children_initiated_appropriate_complementary_feeding_help_text
from custom.icds_reports.models import AggChildHealthMonthly, ChildHealthMonthlyView
from custom.icds_reports.utils import apply_exclude, generate_data_for_map, chosen_filters_to_labels, \
    indian_formatted_number, get_filters_from_config_for_chart_view
from custom.icds_reports.utils import get_location_launched_status


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_children_initiated_data_map(domain, config, loc_level, show_test=False, icds_features_flag=False):
    config['month'] = datetime(*config['month'])

    def get_data_for(filters):
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            children=Sum('cf_initiation_in_month'),
            all=Sum('cf_initiation_eligible'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    if icds_features_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
        get_data_for(config),
        loc_level,
        'children',
        'all',
        20,
        60,
        location_launched_status=location_launched_status
    )

    fills = OrderedDict()
    fills.update({'0%-20%': MapColors.RED})
    fills.update({'20%-60%': MapColors.ORANGE})
    fills.update({'60%-100%': MapColors.PINK})
    if icds_features_flag:
        fills.update({'Not Launched': MapColors.GREY})
    fills.update({'defaultFill': MapColors.GREY})

    gender_ignored, age_ignored, chosen_filters = chosen_filters_to_labels(config)

    return {
        "slug": "severe",
        "label": "Percent Children (6-8 months) initiated Complementary Feeding{}".format(chosen_filters),
        "fills": fills,
        "rightLegend": {
            "average": average,
            "info": children_initiated_appropriate_complementary_feeding_help_text(html=True),
            "extended_info": [
                {
                    'indicator': 'Total number of children between age 6 - 8 months{}:'.format(chosen_filters),
                    'value': indian_formatted_number(valid_total)
                },
                {
                    'indicator': (
                        'Total number of children (6-8 months) given timely introduction to sold or '
                        'semi-solid food in the given month{}:'.format(chosen_filters)
                    ),
                    'value': indian_formatted_number(in_month_total)
                },
                {
                    'indicator': (
                        '% children (6-8 months) given timely introduction to solid or '
                        'semi-solid food in the given month{}:'.format(chosen_filters)
                    ),
                    'value': '%.2f%%' % (in_month_total * 100 / float(valid_total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_features_flag'], timeout=30 * 60)
def get_children_initiated_data_chart(domain, config, loc_level, show_test=False, icds_features_flag=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']
    # using child health monthly while querying for sector level due to performance issues
    if icds_features_flag and config['aggregation_level'] >= AggregationLevels.SUPERVISOR:
        chm_filter = get_filters_from_config_for_chart_view(config)
        chm_queryset = ChildHealthMonthlyView.objects.filter(**chm_filter)
    else:
        chm_queryset = AggChildHealthMonthly.objects.filter(**config)

    chart_data = chm_queryset.values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('cf_initiation_in_month'),
        eligible=Sum('cf_initiation_eligible'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0, 'in_month': 0}

    best_worst = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })

    if icds_features_flag:
        if 'month' not in config:
            config['month'] = month
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in chart_data:
        if location_launched_status:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['eligible']

        best_worst[location]['in_month'] = in_month
        best_worst[location]['all'] = (valid or 0)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data_for_month = data['blue'][date_in_miliseconds]
        data_for_month['in_month'] += in_month
        data_for_month['all'] += valid
        data_for_month['y'] = data_for_month['in_month'] / float(data_for_month['all'] or 1)

    all_locations = [
        {
            'loc_name': key,
            'percent': (value['in_month'] * 100) / float(value['all'] or 1)
        }
        for key, value in best_worst.items()
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
                        'y': value['y'],
                        'all': value['all'],
                        'in_month': value['in_month']
                    } for key, value in data['blue'].items()
                ],
                "key": "% Children began complementary feeding",
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


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test', 'icds_features_flag'],
                 timeout=30 * 60)
def get_children_initiated_sector_data(domain, config, loc_level, location_id,
                                       show_test=False, icds_features_flag=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('cf_initiation_in_month'),
        eligible=Sum('cf_initiation_eligible'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'children': 0,
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

        valid = row['eligible']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']
        row_values = {
            'children': in_month or 0,
            'all': valid or 0
        }
        for prop, value in row_values.items():
            tooltips_data[name][prop] += value

        value = (in_month or 0) / float(valid or 1)

        chart_data['blue'].append([
            name, value
        ])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "info": children_initiated_appropriate_complementary_feeding_help_text(html=True),
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": MapColors.BLUE
            },
        ]
    }
