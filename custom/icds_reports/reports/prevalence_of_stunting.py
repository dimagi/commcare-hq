from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import LocationTypes
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


def get_prevalence_of_stunning_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            moderate=Sum('stunting_moderate'),
            severe=Sum('stunting_severe'),
            normal=Sum('stunting_normal'),
            valid=Sum('height_eligible'),
            total_measured=Sum('height_measured_in_month'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}

    moderate_total = 0
    severe_total = 0
    valid_total = 0

    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        severe = row['severe']
        moderate = row['moderate']
        normal = row['normal']
        total_measured = row['total_measured']

        moderate_total += (moderate or 0)
        severe_total += (severe or 0)
        valid_total += (valid or 0)

        value = ((moderate or 0) + (severe or 0)) * 100 / float(valid or 1)
        row_values = {
            'severe': severe or 0,
            'moderate': moderate or 0,
            'total': valid or 0,
            'normal': normal or 0,
            'total_measured': total_measured or 0,
        }
        if value < 25:
            row_values.update({'fillKey': '0%-25%'})
        elif 25 <= value < 38:
            row_values.update({'fillKey': '25%-38%'})
        elif value >= 38:
            row_values.update({'fillKey': '38%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-25%': PINK})
    fills.update({'25%-38%': ORANGE})
    fills.update({'38%-100%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "severe",
            "label": "Percent of Children Stunted (6 - 60 months)",
            "fills": fills,
            "rightLegend": {
                "average": "%.2f" % (((moderate_total + severe_total) * 100) / float(valid_total or 1)),
                "info": _((
                    "Percentage of children (6-60 months) enrolled for ICDS services with height-for-age below "
                    "-2Z standard deviations of the WHO Child Growth Standards median."
                    "<br/><br/>"
                    "Stunting in children is a sign of chronic undernutrition and has long lasting harmful "
                    "consequences on the growth of a child"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_prevalence_of_stunning_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderate=Sum('stunting_moderate'),
        severe=Sum('stunting_severe'),
        valid=Sum('height_eligible'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'red': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['red'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severe = row['severe']
        moderate = row['moderate']

        underweight = (moderate or 0) + (severe or 0)

        best_worst[location] = underweight * 100 / float(valid or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['red'][date_in_miliseconds]['y'] += underweight
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
                    } for key, value in data['red'].iteritems()
                ],
                "key": "Moderate or severely stunted growth",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_prevalence_of_stunning_sector_data(domain, config, loc_level, show_test=False):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderate=Sum('stunting_moderate'),
        severe=Sum('stunting_severe'),
        valid=Sum('height_eligible'),
        normal=Sum('stunting_normal'),
        total_measured=Sum('height_measured_in_month'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    tooltips_data = defaultdict(lambda: {
        'severe': 0,
        'moderate': 0,
        'total': 0,
        'normal': 0,
        'total_measured': 0
    })

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        severe = row['severe']
        moderate = row['moderate']
        normal = row['normal']
        total_measured = row['total_measured']

        row_values = {
            'severe': severe or 0,
            'moderate': moderate or 0,
            'total': valid or 0,
            'normal': normal or 0,
            'total_measured': total_measured or 0,
        }

        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += value

        value = ((moderate or 0) + (severe or 0)) * 100 / float(valid or 1)

        if value < 25.0:
            loc_data['green'] += 1
        elif 25.0 <= value < 38.0:
            loc_data['orange'] += 1
        elif value >= 38.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "tooltips_data": tooltips_data,
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-25%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": PINK
            },
            {
                "values": chart_data['orange'],
                "key": "25%-38%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "38%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }
