from __future__ import absolute_import
from __future__ import unicode_literals

import pytz
from datetime import datetime
from django import template

from custom.icds_reports.const import INDIA_TIMEZONE
from custom.icds_reports.reports.issnip_monthly_register import DATA_NOT_ENTERED
from custom.icds_reports.utils import generate_qrcode

register = template.Library()


def get_value(data, prop):
    try:
        return int(data[prop])
    except (ValueError, KeyError, TypeError):
        return 0


def format(data, prop, default=DATA_NOT_ENTERED):
        return data[prop] if data and prop in data and data[prop] is not None else default


@register.filter(name='icds_format')
def icds_format(data, prop):
    return format(data, prop)


@register.filter(name='icds_format_def_zero')
def icds_format_def_zero(data, prop):
    return format(data, prop, 0)


@register.filter(name='icds_type_of_building')
def icds_type_of_building(data):
    housed = ['', 'Owned', 'Rented', 'Neither owned nor rented']
    provided_buildings = [
        '', 'Owned (Panchayat)', 'Owned (Community)', 'Owned (Urban Municipality/ Corporation)',
        'Owned (Rural Development/ DRDA)', 'Owned (ICDS)', 'Owned (Other)'
    ]
    other_buildings = [
        '', 'AWW\'s house', 'AWW Helper\'s house', 'Panchayat building', 'Primary school',
        'Any religious place', 'Any other community building', 'Open Space'
    ]
    if data:
        where_housed = get_value(data, 'where_housed')
        building = get_value(data, 'provided_building')
        other_building = get_value(data, 'other_building')
        if where_housed == 1:
            return provided_buildings[building]
        elif where_housed == 3:
            return other_buildings[other_building]
        else:
            return housed[where_housed]
    else:
        return ''


@register.filter(name='icds_type_of_awc_building')
def icds_type_of_awc_building(data):
    if data:
        return 'Pucca' if data.lower() == 'pucca' else 'Other'
    else:
        return DATA_NOT_ENTERED


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


@register.filter(name='icds_qr_code')
def icds_qr_code(awc_site_code):
    utc_now = datetime.now(pytz.utc)
    india_now = utc_now.astimezone(INDIA_TIMEZONE)
    return generate_qrcode("{} {}".format(
        awc_site_code,
        india_now.strftime('%d %b %Y')
    ))
