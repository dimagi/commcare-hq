from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors, AggregationLevels
from custom.icds_reports.models import AggChildHealthMonthly, ChildHealthMonthlyView
from custom.icds_reports.utils import apply_exclude, chosen_filters_to_labels, indian_formatted_number, \
    stunting_moderate_column, stunting_severe_column, stunting_normal_column, \
    default_age_interval, hfa_recorded_in_month_column, get_filters_from_config_for_chart_view
from custom.icds_reports.utils import get_location_launched_status


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_prevalence_of_stunting_data_map(domain, config, loc_level, show_test=False, icds_feature_flag=False):
    config['month'] = datetime(*config['month'])

    def get_data_for(filters):
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            moderate=Sum(stunting_moderate_column(icds_feature_flag)),
            severe=Sum(stunting_severe_column(icds_feature_flag)),
            normal=Sum(stunting_normal_column(icds_feature_flag)),
            total=Sum('height_eligible'),
            total_measured=Sum(hfa_recorded_in_month_column(icds_feature_flag)),
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
        'total': 0,
        'total_measured': 0,
        'original_name': []
    })

    moderate_total = 0
    severe_total = 0
    normal_total = 0
    all_total = 0
    measured_total = 0

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
        total = row['total'] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0
        total_measured = row['total_measured'] or 0

        values_to_calculate_average['numerator'] += moderate if moderate else 0
        values_to_calculate_average['numerator'] += severe if severe else 0
        values_to_calculate_average['denominator'] += total_measured if total_measured else 0

        severe_total += severe
        moderate_total += moderate
        normal_total += normal
        all_total += total
        measured_total += total_measured

        data_for_map[on_map_name]['severe'] += severe
        data_for_map[on_map_name]['moderate'] += moderate
        data_for_map[on_map_name]['normal'] += normal
        data_for_map[on_map_name]['total'] += total
        data_for_map[on_map_name]['total_measured'] += total_measured
        data_for_map[on_map_name]['original_name'].append(name)

    for data_for_location in data_for_map.values():
        numerator = data_for_location['moderate'] + data_for_location['severe']
        value = numerator * 100 / (data_for_location['total_measured'] or 1)
        if value < 25:
            data_for_location.update({'fillKey': '0%-25%'})
        elif 25 <= value < 38:
            data_for_location.update({'fillKey': '25%-38%'})
        elif value >= 38:
            data_for_location.update({'fillKey': '38%-100%'})

    fills = OrderedDict()
    fills.update({'0%-25%': MapColors.PINK})
    fills.update({'25%-38%': MapColors.ORANGE})
    fills.update({'38%-100%': MapColors.RED})
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
        "label": "Percent of Children{gender} Stunted ({age})".format(
            gender=gender_label,
            age=age_label
        ),
        "fills": fills,
        "rightLegend": {
            "average": "%.2f" % average,
            "info": _((
                "Of the children enrolled for Anganwadi services, whose height was measured, the percentage of "
                "children between {} who were moderately/severely stunted in the current month. "
                "<br/><br/>"
                "Stunting is a sign of chronic undernutrition and has long lasting harmful consequences on "
                "the growth of a child".format(age_label)
            )),
            "extended_info": [
                {
                    'indicator': 'Total Children{} eligible to have height measured:'.format(chosen_filters),
                    'value': indian_formatted_number(all_total)
                },
                {
                    'indicator': 'Total Children{} with height measured in given month:'
                    .format(chosen_filters),
                    'value': indian_formatted_number(measured_total)
                },
                {
                    'indicator': 'Number of Children{} unmeasured:'.format(chosen_filters),
                    'value': indian_formatted_number(all_total - measured_total)
                },
                {
                    'indicator': '% children{} with severely stunted growth:'.format(chosen_filters),
                    'value': '%.2f%%' % (severe_total * 100 / float(measured_total or 1))
                },
                {
                    'indicator': '% children{} with moderate stunted growth:'.format(chosen_filters),
                    'value': '%.2f%%' % (moderate_total * 100 / float(measured_total or 1))
                },
                {
                    'indicator': '% children{} with normal stunted growth:'.format(chosen_filters),
                    'value': '%.2f%%' % (normal_total * 100 / float(measured_total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_prevalence_of_stunting_data_chart(domain, config, loc_level, show_test=False, icds_feature_flag=False):
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
        moderate=Sum(stunting_moderate_column(icds_feature_flag)),
        severe=Sum(stunting_severe_column(icds_feature_flag)),
        normal=Sum(stunting_normal_column(icds_feature_flag)),
        total=Sum('height_eligible'),
        measured=Sum(hfa_recorded_in_month_column(icds_feature_flag)),
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
        data['red'][miliseconds] = {'y': 0, 'all': 0, 'measured': 0}
        data['orange'][miliseconds] = {'y': 0, 'all': 0, 'measured': 0}
        data['peach'][miliseconds] = {'y': 0, 'all': 0, 'measured': 0}

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
        total = row['total'] or 0
        measured = row['measured'] or 0
        location = row['%s_name' % loc_level]
        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0

        underweight = moderate + severe

        best_worst[location] = underweight * 100 / float(measured or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['peach'][date_in_miliseconds]['y'] += normal
        data['peach'][date_in_miliseconds]['measured'] += measured
        data['peach'][date_in_miliseconds]['all'] += total
        data['orange'][date_in_miliseconds]['y'] += moderate
        data['orange'][date_in_miliseconds]['measured'] += measured
        data['orange'][date_in_miliseconds]['all'] += total
        data['red'][date_in_miliseconds]['y'] += severe
        data['red'][date_in_miliseconds]['measured'] += measured
        data['red'][date_in_miliseconds]['all'] += total

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
                        'y': value['y'] / float(value['measured'] or 1),
                        'all': value['all'],
                        'measured': value['measured']
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
                        'y': value['y'] / float(value['measured'] or 1),
                        'all': value['all'],
                        'measured': value['measured']
                    } for key, value in data['orange'].items()
                ],
                "key": "% moderately stunted",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.ORANGE
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['measured'] or 1),
                        'all': value['all'],
                        'measured': value['measured']
                    } for key, value in data['red'].items()
                ],
                "key": "% severely stunted",
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
def get_prevalence_of_stunting_sector_data(domain, config, loc_level, location_id, show_test=False,
                                           icds_feature_flag=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderate=Sum(stunting_moderate_column(icds_feature_flag)),
        severe=Sum(stunting_severe_column(icds_feature_flag)),
        normal=Sum(stunting_normal_column(icds_feature_flag)),
        total=Sum('height_eligible'),
        total_measured=Sum(hfa_recorded_in_month_column(icds_feature_flag)),
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
        'total': 0,
        'normal': 0,
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
        total = row['total'] or 0
        name = row['%s_name' % loc_level]

        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0
        total_measured = row['total_measured'] or 0

        row_values = {
            'severe': severe,
            'moderate': moderate,
            'total': total,
            'normal': normal,
            'total_measured': total_measured,
        }

        for prop, value in row_values.items():
            tooltips_data[name][prop] += value

        value = (moderate + severe) / float(total_measured or 1)
        chart_data['blue'].append([
            name, value
        ])

    chart_data['blue'] = sorted(chart_data['blue'])

    __, __, chosen_filters = chosen_filters_to_labels(
        config, default_interval=default_age_interval(icds_feature_flag)
    )

    return {
        "tooltips_data": dict(tooltips_data),
        "info": _((
            "Of the children enrolled for Anganwadi services, whose height was measured, the percentage "
            "of children between {} who were moderately/severely stunted in the current month. "
            "<br/><br/>"
            "Stunting is a sign of chronic undernutrition and has long lasting harmful consequences on "
            "the growth of a child".format(chosen_filters)
        )),
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
