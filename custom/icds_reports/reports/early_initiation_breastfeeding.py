from collections import OrderedDict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
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


def get_early_initiation_breastfeeding_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            birth=Sum('bf_at_birth'),
            in_month=Sum('born_in_month'),
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}
    birth_total = 0
    in_month_total = 0
    for row in get_data_for(config):
        name = row['%s_name' % loc_level]

        birth = row['birth']
        in_month = row['in_month']

        birth_total += (birth or 0)
        in_month_total += (in_month or 0)

        value = (birth or 0) * 100 / (in_month or 1)
        row_values = {
            'birth': birth,
            'in_month': in_month,
        }
        if value <= 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 < value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': RED})
    fills.update({'20%-60%': ORANGE})
    fills.update({'60%-100%': PINK})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "early_initiation",
            "label": "Percent Early Initiation of Breastfeeding",
            "fills": fills,
            "rightLegend": {
                "average": (birth_total * 100) / float(in_month_total or 1),
                "info": _((
                    "Percentage of children who were put to the breast within one hour of birth."
                    "<br/><br/>"
                    "Early initiation of breastfeeding ensure the newborn recieves the 'first milk' rich in "
                    "nutrients and encourages exclusive breastfeeding practic"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_early_initiation_breastfeeding_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        birth=Sum('bf_at_birth'),
        in_month=Sum('born_in_month'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'green': OrderedDict(),
        'blue': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['green'][miliseconds] = {'y': 0, 'all': 0}
        data['blue'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]

        birth = row['birth']

        value = (birth or 0) * 100 / float(in_month or 1)

        best_worst[location] = value

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += birth
        data['blue'][date_in_miliseconds]['y'] += in_month

    top_locations = sorted(
        [dict(loc_name=key, percent=val) for key, val in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all']
                    } for key, val in data['green'].iteritems()
                ],
                "key": "Children breastfed within one hour of birth",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": PINK
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all']
                    } for key, val in data['blue'].iteritems()
                ],
                "key": "Total births",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_early_initiation_breastfeeding_data(domain, config, loc_level, show_test=False):
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
        birth=Sum('bf_at_birth'),
        in_month=Sum('born_in_month'),
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

    for row in data:
        in_month = row['in_month']
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

        birth = row['birth']

        value = (birth or 0) * 100 / float(in_month or 1)

        if value >= 60.0:
            loc_data['green'] += 1
        elif 20.0 <= value < 60.0:
            loc_data['orange'] += 1
        elif value < 20.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [

            {
                "values": chart_data['red'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['green'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": PINK
            }
        ]
    }
