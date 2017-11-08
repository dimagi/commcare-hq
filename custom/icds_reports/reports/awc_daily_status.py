from __future__ import absolute_import
from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports.const import LocationTypes, ChartColors
from custom.icds_reports.models import AggAwcDailyView
from custom.icds_reports.utils import apply_exclude

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
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
                'period': 'Daily'
            },
            "data": map_data,
        }
    ]


@quickcache(['domain', 'config', 'loc_level', 'show_test'], timeout=30 * 60)
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
        'open_in_day': OrderedDict(),
        'launched': OrderedDict()
    }

    dates = [dt for dt in rrule(DAILY, dtstart=last, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['open_in_day'][miliseconds] = {'y': 0, 'all': 0}
        data['launched'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })
    for row in chart_data:
        date = row['date']
        in_day = row['in_day'] or 0
        location = row['%s_name' % loc_level]
        valid = row['all'] or 0

        if date.month == (month - relativedelta(months=1)).month:
            best_worst[location]['in_day'] = in_day
            best_worst[location]['all'] = valid

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['open_in_day'][date_in_miliseconds]['y'] += in_day
        data['launched'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [
            dict(
                loc_name=key,
                value=value['in_day']
            ) for key, value in best_worst.iteritems()
        ],
        key=lambda x: x['value'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'],
                        'all': value['all']
                    } for key, value in data['launched'].iteritems()
                ],
                "key": "Number of AWCs launched",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.PINK
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'],
                        'all': value['all']
                    } for key, value in data['open_in_day'].iteritems()
                ],
                "key": "Total AWCs open yesterday",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "all_locations": top_locations,
        "top_five": top_locations[:5],
        "bottom_five": top_locations[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }


@quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test'], timeout=30 * 60)
def get_awc_daily_status_sector_data(domain, config, loc_level, location_id, show_test=False):
    group_by = ['%s_name' % loc_level]

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

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'in_day': 0,
        'all': 0
    })

    loc_children = SQLLocation.objects.get(location_id=location_id).get_children()
    result_set = set()

    for row in data:
        valid = row['all']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        in_day = row['in_day']
        row_values = {
            'in_day': in_day or 0,
            'all': valid or 0
        }
        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += value

        value = (in_day or 0) / float(valid or 1)

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
            "Percentage of Angwanwadi Centers that were open yesterday."
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
