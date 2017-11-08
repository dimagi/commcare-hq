from __future__ import absolute_import
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
from custom.icds_reports.utils import apply_exclude


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
            '%s_name' % loc_level
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            normal=Sum('nutrition_status_normal'),
            valid=Sum('wer_eligible'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        if 'age_tranche' not in config:
            queryset = queryset.exclude(age_tranche=72)
        return queryset

    map_data = {}
    moderately_underweight_total = 0
    severely_underweight_total = 0
    valid_total = 0

    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']
        normal = row['normal']

        value = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / (valid or 1)

        moderately_underweight_total += (moderately_underweight or 0)
        severely_underweight_total += (severely_underweight_total or 0)
        valid_total += (valid or 0)

        row_values = {
            'severely_underweight': severely_underweight or 0,
            'moderately_underweight': moderately_underweight or 0,
            'total': valid or 0,
            'normal': normal
        }
        if value < 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 <= value < 35:
            row_values.update({'fillKey': '20%-35%'})
        elif value >= 35:
            row_values.update({'fillKey': '35%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': PINK})
    fills.update({'20%-35%': ORANGE})
    fills.update({'35%-100%': RED})
    fills.update({'defaultFill': GREY})

    average = (
        (moderately_underweight_total or 0) + (severely_underweight_total or 0)
    ) * 100 / float(valid_total or 1)

    return [
        {
            "slug": "moderately_underweight",
            "label": "Percent of Children Underweight (0-5 years)",
            "fills": fills,
            "rightLegend": {
                "average": average,
                "info": _((
                    "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age "
                    "less than -2 standard deviations of the WHO Child Growth Standards median. "
                    "<br/><br/>"
                    "Children who are moderately or severely underweight have a higher risk of mortality"
                ))
            },
            "data": map_data,
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
        [dict(loc_name=key, percent=value) for key, value in best_worst.iteritems()],
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
                    } for key, value in data['peach'].iteritems()
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
                    } for key, value in data['orange'].iteritems()
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
                    } for key, value in data['red'].iteritems()
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
