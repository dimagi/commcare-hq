from __future__ import absolute_import
from django import template

from custom.icds_reports.reports.issnip_monthly_register import DATA_NOT_ENTERED

register = template.Library()


def get_value(data, prop):
    try:
        return int(data[prop])
    except (ValueError, KeyError, TypeError):
        return 0


def format(data, prop, default='Data Not Entered'):
        return data[prop] if data and prop in data and data[prop] is not None else default


@register.filter(name='icds_format')
def icds_format(data, prop):
    return format(data, prop)


@register.filter(name='icds_format_def_zero')
def icds_format_def_zero(data, prop):
    return format(data, prop, 0)


@register.filter(name='icds_type_of_building')
def icds_type_of_building(data):
    housed = ['', 'Owned', 'Rented']
    provided_buildings = [
        '', 'Panchayat', 'Community', 'Urban Municipality/Corporation', 'Rural Development/ DRDA',
        'ICDS', 'Other'
    ]
    if data:
        where_housed = get_value(data, 'where_housed')
        building = get_value(data, 'provided_building')
        if where_housed == 3:
            return provided_buildings[building]
        else:
            return housed[where_housed]
    else:
        return ''


@register.filter(name='icds_toilet_type')
def icds_toilet_type(value):
    types = ['', 'Pit type (Latrine)', 'Only urinal', 'Flush system', 'Other']
    return types[int(value)] if value else ''


@register.filter(name='icds_material_available')
def icds_material_available(data):
    if data:
        kit_available = data['preschool_kit_available'] if 'preschool_kit_available' in data else None
        kit_usable = data['preschool_kit_usable'] if 'preschool_kit_usable' in data else None
        if kit_available and kit_usable:
            return 'Yes'
        elif kit_available in [None, ''] or kit_usable is [None, '']:
            return DATA_NOT_ENTERED
        else:
            return 'No'
    else:
        return DATA_NOT_ENTERED


@register.filter(name='icds_yesno')
def icds_yesno(data):
    if data in [1, '1', 'yes']:
        return 'Yes'
    elif data in [0, '0', 'no']:
        return 'No'
    else:
        return DATA_NOT_ENTERED
