from pytz import timezone


def format_date(datetime):
    return timezone('Africa/Dar_es_Salaam').localize(datetime).strftime('%Y-%m-%d %H:%M:%S')


def status_date_or_empty_string(status):
    if status:
        return format_date(status.timestamp)
    else:
        return ''


def convert_products_dict_to_list(products_dict):
    return [
        '{} {}'.format(product_code, d['quantity'])
        for product_code, d in products_dict.iteritems()
    ]


def delivery_lead_time(start_status, end_status):
    if start_status and end_status:
        return '%.2f' % ((end_status.timestamp - start_status.timestamp).seconds / 60.0)
    else:
        return ''


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
