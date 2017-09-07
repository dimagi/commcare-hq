from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import LocationTypes
from custom.icds_reports.models import AggAwcDailyView
from custom.icds_reports.utils import apply_exclude

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


def get_awc_daily_status_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['date'] = datetime(*filters['month'])
        del filters['month']
        queryset = AggAwcDailyView.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_day=Sum('daily_attendance_open'),
            all=Sum('num_launched_awcs'),
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)

        return queryset

    map_data = {}

    in_day_total = 0
    valid_total = 0

    for row in get_data_for(config):
        valid = row['all']
        name = row['%s_name' % loc_level]

        in_day = row['in_day']

        in_day_total += (in_day or 0)
        valid_total += (valid or 0)

        value = (in_day or 0) * 100 / (valid or 1)
        row_values = {
            'in_day': in_day or 0,
            'all': valid or 0
        }
        if value < 50:
            row_values.update({'fillKey': '0%-50%'})
        elif 50 <= value < 75:
            row_values.update({'fillKey': '50%-75%'})
        elif value >= 75:
            row_values.update({'fillKey': '75%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-50%': RED})
    fills.update({'50%-75%': ORANGE})
    fills.update({'75%-100%': PINK})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "awc_daily_statuses",
            "label": "Percent AWCs Open Yesterday",
            "fills": fills,
            "rightLegend": {
                "average": (in_day_total or 0) * 100 / float(valid_total or 1),
                "info": _((
                    "Percentage of Angwanwadi Centers that were open yesterday."
                )),
                'period': 'Daily',
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_awc_daily_status_data_chart(domain, config, loc_level, show_test=False):
    month = datetime(*config['month'])
    last = datetime(*config['month']) - relativedelta(days=30)

    config['date__range'] = (last, month)
    del config['month']

    chart_data = AggAwcDailyView.objects.filter(
        **config
    ).values(
        'date', '%s_name' % loc_level
    ).annotate(
        in_day=Sum('daily_attendance_open'),
        all=Sum('num_launched_awcs'),
    ).order_by('date')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(DAILY, dtstart=last, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['green'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['date']
        in_day = row['in_day'] or 0
        location = row['%s_name' % loc_level]
        valid = row['all'] or 0

        if location in best_worst:
            best_worst[location].append(in_day / (valid or 1))
        else:
            best_worst[location] = [in_day / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += in_day
        data['blue'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['green'].iteritems()
                ],
                "key": "Number of AWCs launched",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": PINK
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "Total AWCs open yesterday",
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


def get_awc_daily_status_sector_data(domain, config, loc_level, show_test=False):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['date'] = datetime(*config['month'])
    del config['month']
    data = AggAwcDailyView.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_day=Sum('daily_attendance_open'),
        all=Sum('num_launched_awcs'),
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
        'in_day': 0,
        'all': 0
    })

    for row in data:
        valid = row['all']
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
        in_day = row['in_day']
        row_values = {
            'in_day': in_day or 0,
            'all': valid or 0
        }
        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += value

        value = (in_day or 0) * 100 / float(valid or 1)

        if value < 50.0:
            loc_data['red'] += 1
        elif 50.0 <= value < 75.0:
            loc_data['orange'] += 1
        elif value >= 75.0:
            loc_data['green'] += 1

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
                "key": "0%-50%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "50%-75%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "75%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": PINK
            }
        ]
    }
