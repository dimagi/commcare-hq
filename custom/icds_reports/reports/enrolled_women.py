from collections import OrderedDict, defaultdict
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import LocationTypes
from custom.icds_reports.models import AggCcsRecordMonthly
from custom.icds_reports.utils import apply_exclude

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


def get_enrolled_women_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggCcsRecordMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            valid=Sum('pregnant'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        average.append(valid)
        row_values = {
            'valid': valid or 0,
            'fillKey': 'Women'
        }

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'Women': BLUE})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "enrolled_women",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / float(len(average) or 1),
                "average_format": 'number',
                "info": _((
                    "Total number of pregnant women who are enrolled for ICDS services."
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_enrolled_women_sector_data(domain, config, loc_level, show_test=False):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggCcsRecordMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        valid=Sum('pregnant'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    loc_data = {
        'blue': 0,
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'blue': []
    }

    tooltips_data = defaultdict(lambda: {
        'valid': 0
    })

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['blue'].append([tmp_name, loc_data['blue']])
            loc_data = {
                'blue': 0
            }

        row_values = {
            'valid': valid or 0,
        }
        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += value

        loc_data['blue'] += valid
        tmp_name = name
        rows_for_location += 1

    chart_data['blue'].append([tmp_name, loc_data['blue']])

    return {
        "tooltips_data": tooltips_data,
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "Number Of Women",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ]
    }
