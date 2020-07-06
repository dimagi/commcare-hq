from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors, AggregationLevels
from custom.icds_reports.messages import wasting_help_text
from custom.icds_reports.models import AggChildHealthMonthly, ChildHealthMonthlyView
from custom.icds_reports.utils import apply_exclude, chosen_filters_to_labels, indian_formatted_number, \
    wasting_moderate_column, wasting_severe_column, wasting_normal_column, \
    default_age_interval, wfh_recorded_in_month_column, get_filters_from_config_for_chart_view
from custom.icds_reports.utils import get_location_launched_status


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_prevalence_of_severe_data_map(domain, config, loc_level, show_test=False, icds_feature_flag=False):
    config['month'] = datetime(*config['month'])

    def get_data_for(filters):
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            moderate=Sum(wasting_moderate_column(icds_feature_flag)),
            severe=Sum(wasting_severe_column(icds_feature_flag)),
            normal=Sum(wasting_normal_column(icds_feature_flag)),
            total_height_eligible=Sum('height_eligible'),
            total_weighed=Sum('nutrition_status_weighed'),
            total_measured=Sum(wfh_recorded_in_month_column(icds_feature_flag)),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        if 'age_tranche' not in config:
            queryset = queryset.filter(age_tranche__lt=72)
        return queryset

    data_for_map = defaultdict(lambda: {
        'moderate': 0,
        'severe': 0,
        'normal': 0,
        'total_weighed': 0,
        'total_measured': 0,
        'total_height_eligible': 0,
        'original_name': []
    })

    severe_for_all_locations = 0
    moderate_for_all_locations = 0
    normal_for_all_locations = 0
    weighed_for_all_locations = 0
    measured_for_all_locations = 0
    height_eligible_for_all_locations = 0

    values_to_calculate_average = {'numerator': 0, 'denominator': 0}
    if icds_feature_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in get_data_for(config):
        if location_launched_status:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
        total_weighed = row['total_weighed'] or 0
        total_height_eligible = row['total_height_eligible'] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0
        total_measured = row['total_measured'] or 0

        values_to_calculate_average['numerator'] += moderate if moderate else 0
        values_to_calculate_average['numerator'] += severe if severe else 0
        values_to_calculate_average['denominator'] += total_measured if total_measured else 0

        severe_for_all_locations += severe
        moderate_for_all_locations += moderate
        normal_for_all_locations += normal
        weighed_for_all_locations += total_weighed
        measured_for_all_locations += total_measured
        height_eligible_for_all_locations += total_height_eligible

        data_for_map[on_map_name]['severe'] += severe
        data_for_map[on_map_name]['moderate'] += moderate
        data_for_map[on_map_name]['normal'] += normal
        data_for_map[on_map_name]['total_weighed'] += total_weighed
        data_for_map[on_map_name]['total_measured'] += total_measured
        data_for_map[on_map_name]['total_height_eligible'] += total_height_eligible
        data_for_map[on_map_name]['original_name'].append(name)

    for data_for_location in data_for_map.values():
        numerator = data_for_location['moderate'] + data_for_location['severe']
        value = numerator * 100 / (data_for_location['total_measured'] or 1)
        if value < 5:
            data_for_location.update({'fillKey': '0%-5%'})
        elif 5 <= value <= 7:
            data_for_location.update({'fillKey': '5%-7%'})
        elif value > 7:
            data_for_location.update({'fillKey': '7%-100%'})

    fills = OrderedDict()
    fills.update({'0%-5%': MapColors.PINK})
    fills.update({'5%-7%': MapColors.ORANGE})
    fills.update({'7%-100%': MapColors.RED})
    if icds_feature_flag:
        fills.update({'Not Launched': MapColors.GREY})
    fills.update({'defaultFill': MapColors.GREY})

    gender_label, age_label, chosen_filters = chosen_filters_to_labels(
        config,
        default_interval=default_age_interval(icds_feature_flag)
    )

    average = (
        (values_to_calculate_average['numerator'] * 100) /
        float(values_to_calculate_average['denominator'] or 1)
    )

    return {
        "slug": "severe",
        "label": "Percent of Children{gender} Wasted ({age})".format(
            gender=gender_label,
            age=age_label
        ),
        "fills": fills,
        "rightLegend": {
            "average": "%.2f" % average,
            "info": wasting_help_text(age_label),
            "extended_info": [
                {
                    'indicator': 'Total Children{} weighed in given month:'.format(chosen_filters),
                    'value': indian_formatted_number(weighed_for_all_locations)
                },
                {
                    'indicator': 'Total Children{} with weight and height measured in given month:'
                    .format(chosen_filters),
                    'value': indian_formatted_number(measured_for_all_locations)
                },
                {
                    'indicator': 'Number of children{} unmeasured:'.format(chosen_filters),
                    'value': indian_formatted_number(height_eligible_for_all_locations - weighed_for_all_locations)
                },
                {
                    'indicator': '% Severely Acute Malnutrition{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (severe_for_all_locations * 100 / float(measured_for_all_locations or 1))
                },
                {
                    'indicator': '% Moderately Acute Malnutrition{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (moderate_for_all_locations * 100 / float(measured_for_all_locations or 1))
                },
                {
                    'indicator': '% Normal{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (normal_for_all_locations * 100 / float(measured_for_all_locations or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_prevalence_of_severe_data_chart(domain, config, loc_level, show_test=False, icds_feature_flag=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']
    # using child health monthly while querying for sector level due to performance issues
    if icds_feature_flag and config['aggregation_level'] >= AggregationLevels.SUPERVISOR:
        chm_filter = get_filters_from_config_for_chart_view(config)
        chm_queryset = ChildHealthMonthlyView.objects.filter(**chm_filter)
    else:
        chm_queryset = AggChildHealthMonthly.objects.filter(**config)

    chart_data = chm_queryset.values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderate=Sum(wasting_moderate_column(icds_feature_flag)),
        severe=Sum(wasting_severe_column(icds_feature_flag)),
        normal=Sum(wasting_normal_column(icds_feature_flag)),
        total_height_eligible=Sum('height_eligible'),
        total_weighed=Sum('nutrition_status_weighed'),
        total_measured=Sum(wfh_recorded_in_month_column(icds_feature_flag)),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)
    if 'age_tranche' not in config:
        chart_data = chart_data.filter(age_tranche__lt=72)

    data = {
        'red': OrderedDict(),
        'orange': OrderedDict(),
        'peach': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['red'][miliseconds] = {'y': 0, 'total_weighed': 0, 'total_measured': 0, 'total_height_eligible': 0}
        data['orange'][miliseconds] = {'y': 0, 'total_weighed': 0, 'total_measured': 0, 'total_height_eligible': 0}
        data['peach'][miliseconds] = {'y': 0, 'total_weighed': 0, 'total_measured': 0, 'total_height_eligible': 0}

    best_worst = {}
    if icds_feature_flag:
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
        total_weighed = row['total_weighed'] or 0
        total_measured = row['total_measured'] or 0
        total_height_eligible = row['total_height_eligible'] or 0
        location = row['%s_name' % loc_level]
        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0

        underweight = moderate + severe

        best_worst[location] = underweight * 100 / float(total_measured or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['peach'][date_in_miliseconds]['y'] += normal
        data['peach'][date_in_miliseconds]['total_weighed'] += total_weighed
        data['peach'][date_in_miliseconds]['total_measured'] += total_measured
        data['peach'][date_in_miliseconds]['total_height_eligible'] += total_height_eligible
        data['orange'][date_in_miliseconds]['y'] += moderate
        data['orange'][date_in_miliseconds]['total_weighed'] += total_weighed
        data['orange'][date_in_miliseconds]['total_measured'] += total_measured
        data['orange'][date_in_miliseconds]['total_height_eligible'] += total_height_eligible
        data['red'][date_in_miliseconds]['y'] += severe
        data['red'][date_in_miliseconds]['total_weighed'] += total_weighed
        data['red'][date_in_miliseconds]['total_measured'] += total_measured
        data['red'][date_in_miliseconds]['total_height_eligible'] += total_height_eligible

    top_locations = sorted(
        [dict(loc_name=key, percent=value) for key, value in best_worst.items()],
        key=lambda x: (x['percent'], x['loc_name'])
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['total_measured'] or 1),
                        'total_weighed': value['total_weighed'],
                        'total_measured': value['total_measured'],
                        'total_height_eligible': value['total_height_eligible']
                    } for key, value in data['peach'].items()
                ],
                "key": "% normal",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.PINK
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['total_measured'] or 1),
                        'total_weighed': value['total_weighed'],
                        'total_measured': value['total_measured'],
                        'total_height_eligible': value['total_height_eligible']
                    } for key, value in data['orange'].items()
                ],
                "key": "% moderately wasted (moderate acute malnutrition)",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.ORANGE
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['total_measured'] or 1),
                        'total_weighed': value['total_weighed'],
                        'total_measured': value['total_measured'],
                        'total_height_eligible': value['total_height_eligible']
                    } for key, value in data['red'].items()
                ],
                "key": "% severely wasted (severe acute malnutrition)",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.RED
            }
        ],
        "all_locations": top_locations,
        "top_five": top_locations[:5],
        "bottom_five": top_locations[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_prevalence_of_severe_sector_data(domain, config, loc_level, location_id, show_test=False,
                                         icds_feature_flag=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderate=Sum(wasting_moderate_column(icds_feature_flag)),
        severe=Sum(wasting_severe_column(icds_feature_flag)),
        normal=Sum(wasting_normal_column(icds_feature_flag)),
        total_height_eligible=Sum('height_eligible'),
        total_weighed=Sum('nutrition_status_weighed'),
        total_measured=Sum(wfh_recorded_in_month_column(icds_feature_flag)),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)
    if 'age_tranche' not in config:
        data = data.filter(age_tranche__lt=72)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'severe': 0,
        'moderate': 0,
        'total_height_eligible': 0,
        'normal': 0,
        'total_weighed': 0,
        'total_measured': 0
    })
    if icds_feature_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in data:
        if location_launched_status:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
        total_weighed = row['total_weighed'] or 0
        name = row['%s_name' % loc_level]

        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0
        total_measured = row['total_measured'] or 0
        total_height_eligible = row['total_height_eligible'] or 0

        tooltips_data[name]['severe'] += severe
        tooltips_data[name]['moderate'] += moderate
        tooltips_data[name]['total_weighed'] += total_weighed
        tooltips_data[name]['normal'] += normal
        tooltips_data[name]['total_measured'] += total_measured
        tooltips_data[name]['total_height_eligible'] += total_height_eligible

        value = (moderate + severe) / float(total_weighed or 1)
        chart_data['blue'].append([
            name, value
        ])

    chart_data['blue'] = sorted(chart_data['blue'])

    gender_label, age_label, chosen_filters = chosen_filters_to_labels(
        config,
        default_interval=default_age_interval(icds_feature_flag)
    )

    return {
        "tooltips_data": dict(tooltips_data),
        "info": _(wasting_help_text(age_label)),
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
