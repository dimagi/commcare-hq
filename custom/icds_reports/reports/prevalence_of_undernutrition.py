from __future__ import absolute_import, division
from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports.const import LocationTypes, ChartColors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude, chosen_filters_to_labels, indian_formatted_number
import six


RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_prevalence_of_undernutrition_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            normal=Sum('nutrition_status_normal'),
            valid=Sum('wer_eligible'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        if 'age_tranche' not in config:
            queryset = queryset.exclude(age_tranche=72)
        return queryset

    data_for_map = defaultdict(lambda: {
        'moderately_underweight': 0,
        'severely_underweight': 0,
        'normal': 0,
        'total': 0,
        'original_name': []
    })

    moderately_underweight_total = 0
    severely_underweight_total = 0
    normal_total = 0
    valid_total = 0

    for row in get_data_for(config):
        valid = row['valid'] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        severely_underweight = row['severely_underweight'] or 0
        moderately_underweight = row['moderately_underweight'] or 0
        normal = row['normal'] or 0

        moderately_underweight_total += moderately_underweight
        severely_underweight_total += severely_underweight_total
        normal_total += normal
        valid_total += valid

        data_for_map[on_map_name]['severely_underweight'] += severely_underweight
        data_for_map[on_map_name]['moderately_underweight'] += moderately_underweight
        data_for_map[on_map_name]['normal'] += normal
        data_for_map[on_map_name]['total'] += valid
        if name != on_map_name:
            data_for_map[on_map_name]['original_name'].append(name)

    for data_for_location in six.itervalues(data_for_map):
        numerator = data_for_location['moderately_underweight'] + data_for_location['severely_underweight']
        value = numerator * 100 / (data_for_location['total'] or 1)
        if value < 20:
            data_for_location.update({'fillKey': '0%-20%'})
        elif 20 <= value < 35:
            data_for_location.update({'fillKey': '20%-35%'})
        elif value >= 35:
            data_for_location.update({'fillKey': '35%-100%'})

    fills = OrderedDict()
    fills.update({'0%-20%': PINK})
    fills.update({'20%-35%': ORANGE})
    fills.update({'35%-100%': RED})
    fills.update({'defaultFill': GREY})

    average = (
        (moderately_underweight_total or 0) + (severely_underweight_total or 0)
    ) * 100 / float(valid_total or 1)

    sum_of_indicators = moderately_underweight_total + severely_underweight_total + normal_total
    percent_unweighed = (valid_total - sum_of_indicators) * 100 / float(valid_total or 1)

    gender_label, age_label, chosen_filters = chosen_filters_to_labels(config, default_interval='0 - 5 years')

    return [
        {
            "slug": "moderately_underweight",
            "label": "Percent of Children{gender} Underweight ({age})".format(
                gender=gender_label,
                age=age_label
            ),
            "fills": fills,
            "rightLegend": {
                "average": average,
                "info": _((
                    "Percentage of children between {} enrolled for ICDS services with weight-for-age "
                    "less than -2 standard deviations of the WHO Child Growth Standards median. "
                    "<br/><br/>"
                    "Children who are moderately or severely underweight have a higher risk of mortality"
                    .format(age_label)
                )),
                "extended_info": [
                    {
                        'indicator': 'Total Children{} weighed in given month:'.format(chosen_filters),
                        'value': indian_formatted_number(valid_total)
                    },
                    {
                        'indicator': '% Unweighed{}:'.format(chosen_filters),
                        'value': '%.2f%%' % percent_unweighed
                    },
                    {
                        'indicator': '% Severely Underweight{}:'.format(chosen_filters),
                        'value': '%.2f%%' % (severely_underweight_total * 100 / float(valid_total or 1))
                    },
                    {
                        'indicator': '% Moderately Underweight{}:'.format(chosen_filters),
                        'value': '%.2f%%' % (moderately_underweight_total * 100 / float(valid_total or 1))
                    },
                    {
                        'indicator': '% Normal{}:'.format(chosen_filters),
                        'value': '%.2f%%' % (normal_total * 100 / float(valid_total or 1))
                    }
                ]
            },
            "data": dict(data_for_map)
        }
    ]


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
def get_prevalence_of_undernutrition_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderately_underweight=Sum('nutrition_status_moderately_underweight'),
        normal=Sum('nutrition_status_normal'),
        severely_underweight=Sum('nutrition_status_severely_underweight'),
        valid=Sum('valid_in_month'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    if 'age_tranche' not in config:
        chart_data = chart_data.exclude(age_tranche=72)

    data = {
        'peach': OrderedDict(),
        'orange': OrderedDict(),
        'red': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['peach'][miliseconds] = {'y': 0, 'all': 0}
        data['orange'][miliseconds] = {'y': 0, 'all': 0}
        data['red'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']
        normal = row['normal']

        underweight = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / float(valid or 1)

        best_worst[location] = underweight

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['peach'][date_in_miliseconds]['y'] += normal
        data['peach'][date_in_miliseconds]['all'] += valid
        data['orange'][date_in_miliseconds]['y'] += moderately_underweight
        data['orange'][date_in_miliseconds]['all'] += valid
        data['red'][date_in_miliseconds]['y'] += severely_underweight
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
                "key": "% Normal",
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
                "key": "% Moderately Underweight (-2 SD)",
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
                "key": "% Severely Underweight (-3 SD) ",
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
def get_prevalence_of_undernutrition_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderately_underweight=Sum('nutrition_status_moderately_underweight'),
        severely_underweight=Sum('nutrition_status_severely_underweight'),
        valid=Sum('wer_eligible'),
        normal=Sum('nutrition_status_normal')
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    if 'age_tranche' not in config:
        data = data.exclude(age_tranche=72)

    chart_data = {
        'blue': []
    }

    tooltips_data = defaultdict(lambda: {
        'severely_underweight': 0,
        'moderately_underweight': 0,
        'total': 0,
        'normal': 0
    })

    loc_children = SQLLocation.objects.get(location_id=location_id).get_children()
    result_set = set()

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']
        normal = row['normal']

        tooltips_data[name]['severely_underweight'] += severely_underweight
        tooltips_data[name]['moderately_underweight'] += moderately_underweight
        tooltips_data[name]['total'] += (valid or 0)
        tooltips_data[name]['normal'] += normal

        chart_data['blue'].append([
            name,
            ((moderately_underweight or 0) + (severely_underweight or 0)) / float(valid or 1)
        ])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "info": _((
            "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age "
            "less than -2 standard deviations of the WHO Child Growth Standards median. "
            "<br/><br/>"
            "Children who are moderately or severely underweight have a higher risk of mortality"
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
