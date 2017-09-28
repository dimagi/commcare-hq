from collections import OrderedDict, defaultdict
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
                    "nutrients and encourages exclusive breastfeeding practice"
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
        'blue': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0, 'birth': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        birth = row['birth']

        best_worst[location] = (birth or 0) * 100 / float(in_month or 1)

        date_in_miliseconds = int(date.strftime("%s")) * 1000
        data_for_month = data['blue'][date_in_miliseconds]

        data_for_month['all'] += in_month
        data_for_month['birth'] += birth
        data_for_month['y'] = data_for_month['birth'] / float(data_for_month['all'] or 1)

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
                        'all': val['all'],
                        'birth': val['birth']
                    } for key, val in data['blue'].iteritems()
                ],
                "key": "% Early Initiation of Breastfeeding",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[:5],
        "bottom_three": top_locations[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_early_initiation_breastfeeding_data(domain, config, loc_level, show_test=False):
    group_by = ['%s_name' % loc_level]

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

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'in_month': 0,
        'birth': 0,
    })

    for row in data:
        in_month = row['in_month']
        name = row['%s_name' % loc_level]

        birth = row['birth']

        value = (birth or 0) / float(in_month or 1)

        tooltips_data[name]['birth'] += birth
        tooltips_data[name]['in_month'] += (in_month or 0)

        chart_data['blue'].append([
            name, value
        ])

    return {
        "tooltips_data": tooltips_data,
        "info": _((
            "Percentage of children who were put to the breast within one hour of birth."
            "<br/><br/>"
            "Early initiation of breastfeeding ensure the newborn recieves the 'first milk' rich in "
            "nutrients and encourages exclusive breastfeeding practice"
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
