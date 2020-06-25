import copy
from collections import OrderedDict, defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes, ChartColors, MapColors
from custom.icds_reports.models import AggChildHealthMonthly
from custom.icds_reports.utils import apply_exclude, generate_data_for_map, chosen_filters_to_labels, \
    indian_formatted_number
from custom.icds_reports.utils import get_location_launched_status


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_features_flag'], timeout=30 * 60)
def get_immunization_coverage_data_map(domain, config, loc_level, show_test=False, icds_features_flag=False):
    config['month'] = datetime(*config['month'])

    def get_data_for(filters):
        # Retrieving children of age 1-2 years
        filters['age_tranche__lte'] = '24'
        queryset = AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level, '%s_map_location_name' % loc_level
        ).annotate(
            children=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
            all=Sum('fully_immunized_eligible'),
        ).order_by('%s_name' % loc_level, '%s_map_location_name' % loc_level)

        if not show_test:
            queryset = apply_exclude(domain, queryset)

        return queryset
    if icds_features_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    data_for_map, valid_total, in_month_total, average, total = generate_data_for_map(
        get_data_for(config),
        loc_level,
        'children',
        'all',
        20,
        60,
        location_launched_status=location_launched_status
    )

    fills = OrderedDict()
    fills.update({'0%-20%': MapColors.RED})
    fills.update({'20%-60%': MapColors.ORANGE})
    fills.update({'60%-100%': MapColors.PINK})
    if icds_features_flag:
        fills.update({'Not Launched': MapColors.GREY})
    fills.update({'defaultFill': MapColors.GREY})

    gender_ignored, age_ignored, chosen_filters = chosen_filters_to_labels(config)
    return {
        "slug": "institutional_deliveries",
        "label": "Percent Immunization Coverage at 1 year{}".format(chosen_filters),
        "fills": fills,
        "rightLegend": {
            "average": average,
            "info": _((
                "Of the total number of children enrolled for Anganwadi Services who are between"
                " 1-2 years old, the percentage of children who have received the complete immunization"
                " as per the National Immunization Schedule of India that is required by age 1."
                "<br/><br/>"
                "This includes the following immunizations:<br/>"
                "If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>"
                "If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1"
            )),
            "extended_info": [
                {
                    'indicator': 'Total number of ICDS Child beneficiaries between 1-2 years old{}:'
                        .format(chosen_filters),
                    'value': indian_formatted_number(valid_total)
                },
                {
                    'indicator': (
                        'Total number of children between 1-2 years old who have received complete'
                        ' immunizations required by age 1{}:'.format(chosen_filters)
                    ),
                    'value': indian_formatted_number(in_month_total)
                },
                {
                    'indicator': (
                        '% of children between 1-2 years old who have received'
                        ' complete immunizations required by age 1{}:'.format(chosen_filters)
                    ),
                    'value': '%.2f%%' % (in_month_total * 100 / float(valid_total or 1))
                }
            ]
        },
        "data": dict(data_for_map),
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'location_id', 'show_test', 'icds_features_flag'],
                 timeout=30 * 60)
def get_immunization_coverage_sector_data(domain, config, loc_level, location_id,
                                          show_test=False, icds_features_flag=False):
    group_by = ['%s_name' % loc_level]

    config['month'] = datetime(*config['month'])
    # Retrieving children of age 1-2 years
    config['age_tranche__lte'] = '24'
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
        eligible=Sum('fully_immunized_eligible'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
    }

    tooltips_data = defaultdict(lambda: {
        'children': 0,
        'all': 0
    })

    if icds_features_flag:
        location_launched_status = get_location_launched_status(config, loc_level)
    else:
        location_launched_status = None
    for row in data:
        if location_launched_status:
            launched_status = location_launched_status.get(row['%s_name' % loc_level])
            if launched_status is None or launched_status <= 0:
                continue
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']

        row_values = {
            'children': in_month or 0,
            'all': valid or 0
        }
        for prop, value in row_values.items():
            tooltips_data[name][prop] += value

        value = (in_month or 0) / float(valid or 1)
        chart_data['blue'].append([
            name, value
        ])

    chart_data['blue'] = sorted(chart_data['blue'])

    return {
        "tooltips_data": dict(tooltips_data),
        "info": _((
            "Of the total number of children enrolled for Anganwadi Services who are between"
            " 1-2 years old, the percentage of children who have received the complete immunization"
            " as per the National Immunization Schedule of India that is required by age 1."
            "<br/><br/>"
            "This includes the following immunizations:<br/>"
            "If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>"
            "If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1"
        )),
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": MapColors.BLUE
            }
        ]
    }


@icds_quickcache(['domain', 'config', 'loc_level', 'show_test', 'icds_features_flag'], timeout=30 * 60)
def get_immunization_coverage_data_chart(domain, config, loc_level, show_test=False, icds_features_flag=False):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    # Retrieving children of age 1-2 years
    config['age_tranche__lte'] = '24'
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
        eligible=Sum('fully_immunized_eligible'),
    ).order_by('month')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    data = {
        'blue': OrderedDict(),
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0, 'in_month': 0}

    best_worst = defaultdict(lambda: {
        'in_month': 0,
        'all': 0
    })

    if icds_features_flag:
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
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['eligible']

        best_worst[location]['in_month'] = in_month
        best_worst[location]['all'] = (valid or 0)

        date_in_miliseconds = int(date.strftime("%s")) * 1000
        data_for_month = data['blue'][date_in_miliseconds]

        data_for_month['all'] += valid
        data_for_month['in_month'] += in_month
        data_for_month['y'] = data_for_month['in_month'] / float(data_for_month['all'] or 1)

    all_locations = [
        {
            'loc_name': key,
            'percent': (value['in_month'] * 100) / float(value['all'] or 1)
        }
        for key, value in best_worst.items()
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
                        'y': value['y'],
                        'all': value['all'],
                        'in_month': value['in_month']
                    } for key, value in data['blue'].items()
                ],
                "key": "% Children between 1-2 years old who received complete immunizations by 1 year",
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
