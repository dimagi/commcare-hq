from __future__ import absolute_import
from pytz import timezone

from corehq.util.timezones.conversions import ServerTime
from custom.zipline.models import EmergencyOrderStatusUpdate


def format_date(datetime):
    return ServerTime(datetime).user_time(timezone('Africa/Dar_es_Salaam')).done().strftime('%Y-%m-%d %H:%M:%S')


def format_status(status):
    return dict(EmergencyOrderStatusUpdate.STATUS_CHOICES).get(status, '')


def status_date_or_empty_string(status):
    if status:
        return format_date(status.timestamp)
    else:
        return ''


def zipline_status_date_or_empty_string(status):
    if status:
        return format_date(status.zipline_timestamp)
    else:
        return ''


def convert_products_dict_to_list(products_dict):
    return [
        '{} {}'.format(product_code, d['quantity'])
        for product_code, d in products_dict.iteritems()
    ]


def products_requested(emergency_order):
    return ' '.join(convert_products_dict_to_list(emergency_order.products_requested))


def products_delivered(emergency_order):
    return ' '.join(convert_products_dict_to_list(emergency_order.products_delivered))


def products_requested_not_confirmed(emergency_order):
    result_dict = {}
    for product_code, d in emergency_order.products_requested.iteritems():
        requested_quantity = int(d['quantity'])
        confirmed_quantity = 0
        if product_code in emergency_order.products_confirmed:
            confirmed_quantity = int(emergency_order.products_confirmed[product_code]['quantity'])

        result_dict[product_code] = {'quantity': requested_quantity - confirmed_quantity}
    products_requested_not_confirmed_dict = {
        product_code: d
        for product_code, d in result_dict.iteritems()
        if d['quantity'] > 0
    }
    return ' '.join(convert_products_dict_to_list(products_requested_not_confirmed_dict))
