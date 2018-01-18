from __future__ import absolute_import, division

from collections import OrderedDict, defaultdict
from datetime import datetime

import six
from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.util.quickcache import quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude, chosen_filters_to_labels, indian_formatted_number, \
    get_child_locations


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_prevalence_of_severe_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            moderate=Sum('wasting_moderate'),
            severe=Sum('wasting_severe'),
            normal=Sum('wasting_normal'),
            valid=Sum('height_eligible'),
            total_measured=Sum('height_measured_in_month'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        if 'age_tranche' not in config:
            queryset = queryset.exclude(age_tranche__in=[0, 6, 72])
        return queryset

    data_for_map = defaultdict(lambda: {
        'moderate': 0,
        'severe': 0,
        'normal': 0,
        'total': 0,
        'total_measured': 0,
        'original_name': []
    })

    severe_total = 0
    moderate_total = 0
    normal_total = 0
    valid_total = 0
    measured_total = 0

    values_to_calculate_average = []
    for row in get_data_for(config):
        valid = row['valid'] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        severe = row['severe'] or 0
        moderate = row['moderate'] or 0
        normal = row['normal'] or 0
        total_measured = row['total_measured'] or 0

        numerator = moderate + severe
        values_to_calculate_average.append(numerator * 100 / (valid or 1))

        severe_total += severe
        moderate_total += moderate
        normal_total += normal
        valid_total += valid
        measured_total += total_measured

        data_for_map[on_map_name]['severe'] += severe
        data_for_map[on_map_name]['moderate'] += moderate
        data_for_map[on_map_name]['normal'] += normal
        data_for_map[on_map_name]['total'] += valid
        data_for_map[on_map_name]['total_measured'] += total_measured
        data_for_map[on_map_name]['original_name'].append(name)

    for data_for_location in six.itervalues(data_for_map):
        numerator = data_for_location['moderate'] + data_for_location['severe']
        value = numerator * 100 / (data_for_location['total'] or 1)
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
    fills.update({'defaultFill': MapColors.GREY})

    sum_of_indicators = moderate_total + severe_total + normal_total
    percent_unmeasured = (valid_total - sum_of_indicators) * 100 / float(valid_total or 1)

    gender_label, age_label, chosen_filters = chosen_filters_to_labels(config, default_interval='6 - 60 months')

    return {
        "slug": "severe",
        "label": "Percent of Children{gender} Wasted ({age})".format(
            gender=gender_label,
            age=age_label
        ),
        "fills": fills,
        "rightLegend": {
            "average": "%.2f" % ((sum(values_to_calculate_average)) / float(len(values_to_calculate_average) or 1)),
            "info": _((
                "Percentage of children between {} enrolled for ICDS services with "
                "weight-for-height below -2 standard deviations of the WHO Child Growth Standards median. "
                "<br/><br/>"
                "Wasting in children is a symptom of acute undernutrition usually as a consequence "
                "of insufficient food intake or a high incidence of infectious diseases. Severe Acute "
                "Malnutrition (SAM) is nutritional status for a child who has severe wasting "
                "(weight-for-height) below -3 Z and Moderate Acute Malnutrition (MAM) is nutritional "
                "status for a child that has moderate wasting (weight-for-height) below -2Z."
                .format(age_label)
            )),
            "extended_info": [
                {
                    'indicator': 'Total Children{} weighed in given month:'.format(chosen_filters),
                    'value': indian_formatted_number(valid_total)
                },
                {
                    'indicator': 'Total Children{} with height measured in given month:'
                    .format(chosen_filters),
                    'value': indian_formatted_number(measured_total)
                },
                {
                    'indicator': '% Unmeasured{}:'.format(chosen_filters),
                    'value': '%.2f%%' % percent_unmeasured
                },
                {
                    'indicator': '% Severely Acute Malnutrition{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (severe_total * 100 / float(valid_total or 1))
                },
                {
                    'indicator': '% Moderately Acute Malnutrition{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (moderate_total * 100 / float(valid_total or 1))
                },
                {
                    'indicator': '% Normal{}:'.format(chosen_filters),
                    'value': '%.2f%%' % (normal_total * 100 / float(valid_total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_prevalence_of_severe_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderate=Sum('wasting_moderate'),
        severe=Sum('wasting_severe'),
        normal=Sum('wasting_normal'),
        valid=Sum('height_eligible'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)
    if 'age_tranche' not in config:
        chart_data = chart_data.exclude(age_tranche__in=[0, 6, 72])

    data = {
        'red': OrderedDict(),
        'orange': OrderedDict(),
        'peach': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['red'][miliseconds] = {'y': 0, 'all': 0}
        data['orange'][miliseconds] = {'y': 0, 'all': 0}
        data['peach'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severe = row['severe']
        moderate = row['moderate']
        normal = row['normal']

        underweight = (moderate or 0) + (severe or 0)

        best_worst[location] = underweight * 100 / float(valid or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['peach'][date_in_miliseconds]['y'] += normal
        data['peach'][date_in_miliseconds]['all'] += valid
        data['orange'][date_in_miliseconds]['y'] += moderate
        data['orange'][date_in_miliseconds]['all'] += valid
        data['red'][date_in_miliseconds]['y'] += severe
        data['red'][date_in_miliseconds]['all'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=value) for key, value in six.iteritems(best_worst)],
        key=lambda x: x['percent']
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in six.iteritems(data['peach'])
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
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in six.iteritems(data['orange'])
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
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in six.iteritems(data['red'])
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


@quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_prevalence_of_severe_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderate=Sum('wasting_moderate'),
        severe=Sum('wasting_severe'),
        valid=Sum('height_eligible'),
        normal=Sum('wasting_normal'),
        total_measured=Sum('height_measured_in_month'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)
    if 'age_tranche' not in config:
        data = data.exclude(age_tranche__in=[0, 6, 72])

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

    loc_children = get_child_locations(domain, location_id, show_test)
    result_set = set()

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        severe = row['severe']
        moderate = row['moderate']
        normal = row['normal']
        total_measured = row['total_measured']

        tooltips_data[name]['severe'] += (severe or 0)
        tooltips_data[name]['moderate'] += (moderate or 0)
        tooltips_data[name]['total'] += (valid or 0)
        tooltips_data[name]['normal'] += normal
        tooltips_data[name]['total_measured'] += total_measured

        value = ((moderate or 0) + (severe or 0)) / float(valid or 1)
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
            "Percentage of children between 6 - 60 months enrolled for ICDS services with "
            "weight-for-height below -3 standard deviations of the WHO Child Growth Standards median."
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
            "undernutrition usually as a consequence of insufficient food intake or a high "
            "incidence of infectious diseases."
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
