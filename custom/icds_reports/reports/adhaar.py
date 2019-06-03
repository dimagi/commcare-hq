from __future__ import absolute_import, division
from __future__ import unicode_literals
from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY

from django.db.models.aggregates import Sum

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.messages import percent_aadhaar_seeded_beneficiaries_help_text
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude, generate_data_for_map, indian_formatted_number, \
    get_child_locations, person_has_aadhaar_column, person_is_beneficiary_column
import six


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'beta'], timeout=30 * 60)
def get_adhaar_data_map(domain, config, loc_level, show_test=False, beta=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggAwcMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            in_month=Sum(person_has_aadhaar_column(beta)),
            all=Sum(person_is_beneficiary_column(beta)),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
        get_data_for(config),
        loc_level,
        'in_month',
        'all',
        25,
        50
    )

    fills = OrderedDict()
    fills.update({'0%-25%': MapColors.RED})
    fills.update({'25%-50%': MapColors.ORANGE})
    fills.update({'50%-100%': MapColors.PINK})
    fills.update({'defaultFill': MapColors.GREY})

    return {
        "slug": "adhaar",
        "label": "Percent Aadhaar-seeded Beneficiaries",
        "fills": fills,
        "rightLegend": {
            "average": average,
            "info": percent_aadhaar_seeded_beneficiaries_help_text(),
            "extended_info": [
                {
                    'indicator': (
                        'Total number of ICDS beneficiaries whose Aadhaar has been captured:'
                    ),
                    'value': indian_formatted_number(in_month_total)
                },
                {
                    'indicator': (
                        '% of ICDS beneficiaries whose Aadhaar has been captured:'
                    ),
                    'value': '%.2f%%' % (in_month_total * 100 / float(valid_total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test', 'beta'], timeout=30 * 60)
def get_adhaar_sector_data(domain, config, loc_level, location_id, show_test=False, beta=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum(person_has_aadhaar_column(beta)),
        all=Sum(person_is_beneficiary_column(beta)),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })

    loc_children = get_child_locations(domain, location_id, show_test)
    result_set = set()

    for row in data:
        valid = row['all']
        name = row['%s_name' % loc_level]
        result_set.add(name)

        in_month = row['in_month']

        row_values = {
            'in_month': in_month or 0,
            'all': valid or 0
        }
        for prop, value in six.iteritems(row_values):
            tooltips_data[name][prop] += value

        value = (in_month or 0) / float(valid or 1)

        chart_data['blue'].append([
            name,
            value
        ])

    for sql_location in loc_children:
        if sql_location.name not in result_set:
            chart_data['blue'].append([sql_location.name, 0])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "info": percent_aadhaar_seeded_beneficiaries_help_text(),
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


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'beta'], timeout=30 * 60)
def get_adhaar_data_chart(domain, config, loc_level, show_test=False, beta=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum(person_has_aadhaar_column(beta)),
        all=Sum(person_is_beneficiary_column(beta)),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict(),
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['all']

        best_worst[location]['in_month'] = in_month
        best_worst[location]['all'] = (valid or 0)

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['blue'][date_in_miliseconds]['y'] += in_month
        data['blue'][date_in_miliseconds]['all'] += valid

    all_locations = [
        {
            'loc_name': key,
            'percent': (value['in_month'] * 100) / float(value['all'] or 1),
        } for key, value in six.iteritems(best_worst)
    ]
    all_locations_sorted_by_name = sorted(all_locations, key=lambda x: x['loc_name'])
    all_locations_sorted_by_percent_and_name = sorted(
        all_locations_sorted_by_name, key=lambda x: x['percent'], reverse=True)

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in six.iteritems(data['blue'])
                ],
                "key": "Percentage of beneficiaries with Aadhaar numbers",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ChartColors.BLUE
            }
        ],
        "all_locations": all_locations_sorted_by_percent_and_name,
        "top_five": all_locations_sorted_by_percent_and_name[:5],
        "bottom_five": all_locations_sorted_by_percent_and_name[-5:],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'Sector'
    }
