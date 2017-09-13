from collections import OrderedDict, defaultdict
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import LocationTypes
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude


RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


def get_awcs_covered_data_map(domain, config, loc_level, show_test=False):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        queryset = AggAwcMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            districts=Sum('num_launched_districts'),
            blocks=Sum('num_launched_blocks'),
            supervisors=Sum('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs'),
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    map_data = {}
    for row in get_data_for(config):
        name = row['%s_name' % loc_level]
        districts = row['districts']
        blocks = row['blocks']
        supervisors = row['supervisors']
        awcs = row['awcs']
        row_values = {
            'districts': districts,
            'blocks': blocks,
            'supervisors': supervisors,
            'awcs': awcs,
            'fillKey': 'Launched',
        }
        map_data.update({name: row_values})

    total_awcs = sum(map(lambda x: (x['awcs'] or 0), map_data.values()))

    fills = OrderedDict()
    fills.update({'Launched': PINK})
    fills.update({'Not launched': GREY})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "awc_covered",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "info": _((
                    "Total AWCs that have launched ICDS CAS <br />" +
                    "Number of AWCs launched: %d" % total_awcs
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_awcs_covered_sector_data(domain, config, loc_level, show_test=False):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])

    data = AggAwcMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        districts=Sum('num_launched_districts'),
        blocks=Sum('num_launched_blocks'),
        supervisors=Sum('num_launched_supervisors'),
        awcs=Sum('num_launched_awcs'),
    ).order_by('%s_name' % loc_level)

    if not show_test:
        data = apply_exclude(domain, data)

    chart_data = {
        'blue': [],
        'green': [],
        'orange': [],
        'red': []
    }

    tooltips_data = defaultdict(lambda: {
        'districts': 0,
        'blocks': 0,
        'supervisors': 0,
        'awcs': 0
    })

    for row in data:
        name = row['%s_name' % loc_level]
        districts = row['districts']
        blocks = row['blocks']
        supervisors = row['supervisors']
        awcs = row['awcs']

        row_values = {
            'districts': districts,
            'blocks': blocks,
            'supervisors': supervisors,
            'awcs': awcs
        }
        for prop, value in row_values.iteritems():
            tooltips_data[name][prop] += (value or 0)

    for name, value_dict in tooltips_data.iteritems():
        chart_data['blue'].append([name, value_dict['districts']])
        chart_data['green'].append([name, value_dict['blocks']])
        chart_data['orange'].append([name, value_dict['supervisors']])
        chart_data['red'].append([name, value_dict['awcs']])

    return {
        "tooltips_data": tooltips_data,
        "chart_data": [
            {
                "values": chart_data['blue'],
                "key": "Districts",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            },
            {
                "values": chart_data['green'],
                "key": "Blocks",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": PINK
            },
            {
                "values": chart_data['orange'],
                "key": "Supervisors",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "AWCs",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }
