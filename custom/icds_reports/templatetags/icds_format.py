from __future__ import absolute_import
from django import template

register = template.Library()


@register.filter(name='icds_format')
def icds_format(data, prop):
    if data:
        return data[prop] if data[prop] is not None else 'Data Not Entered'
    else:
        return ''


@register.filter(name='icds_type_of_building')
def icds_type_of_building(data):
    housed = ['', 'Owned', 'Rented']
    provided_buildings = [
        '', 'Panchayat', 'Community', 'Urban Municipality/Corporation', ' Rural Development/ DRDA',
        'ICDS', 'Other'
    ]
    if data:
        where_housed = data['where_housed'] or 0
        building = data['provided_building'] or 0
        if where_housed == 3:
            return provided_buildings[building]
        else:
            return housed[where_housed]
    else:
        return ''


@register.filter(name='icds_toilet_type')
def icds_toilet_type(value):
    types = ['', 'Pit type (Latrine)', 'Only urinal', 'Flush system', 'Other']
    return types[value] if value else ''


@register.filter(name='icds_material_available')
def icds_material_available(data):
    if data:
        kit_available = data['preschool_kit_available']
        kit_usable = data['preschool_kit_usable']
        return 'Yes' if kit_available and kit_usable else 'No'
    else:
        return 'No'
