from custom.zipline.models import EmergencyOrder, EmergencyOrderStatusUpdate
from datetime import datetime
from decimal import Decimal
from dimagi.utils.couch import CriticalSection


class ProductQuantity(object):
    """
    A simple class to describe a product and the quantity of it to be ordered.
    """

    def __init__(self, code, quantity):
        """
        :param code: the product code of the product being requested
        :param quantity: the quantity of the product being requested
        """
        self.code = code
        self.quantity = quantity


def initiate_emergency_order(domain, user, phone_number, location, products):
    """
    :param domain: the domain in which the order is being requested
    :param user: the user who is initiating the emergency order request
    :param phone_number: the phone_number (string) of the user who is initiating the emergency order request
    :param location: the SQLLocation where the products should be delivered
    :param products: a list of ProductQuantity objects representing the products to be ordered
    """
    from custom.zipline.tasks import send_emergency_order_request

    order = EmergencyOrder.objects.create(
        domain=domain,
        requesting_user_id=user.get_id,
        requesting_phone_number=phone_number,
        location=location,
        location_code=location.site_code,
        products_requested=[{'code': p.code, 'quantity': p.quantity} for p in products],
        timestamp=datetime.utcnow()
    )

    send_emergency_order_request(order.pk)


def process_receipt_confirmation(domain, user, location, products):
    """
    Processes a receipt confirmation of delivered commodities.
    :param domain: the domain
    :param user: the user that sent the receipt confirmation
    :param location: the SQLLocation that the confirmation is coming from
    :param products: a list of ProductQuantity objects representing the products
    and quantities that are being reported to have been received
    """
    order = find_order_to_apply_confirmation(domain, location)
    if order:
        update_order_products_confirmed(order.pk, products)


def find_order_to_apply_confirmation(domain, location):
    """
    Tries to find the EmergencyOrder that the receipt confirmation applies to.
    :param domain: the domain to search
    :param location: the SQLLocation that the confirmation is coming from
    :return: the EmergencyOrder that the confirmation should apply to, or None
    if none is found
    """
    result = EmergencyOrder.objects.filter(
        domain=domain,
        location=location
    ).order_by('-timestamp')[:1]
    result = list(result)

    if len(result) > 0:
        return result[0]

    return None


def get_order_update_critical_section_key(order_id):
    """
    :param order_id: the pk of the order
    :return: the key to be used with CriticalSection for preventing multiple
    threads from updating the same order at the same time
    """
    return 'zipline-updating-order-id-{}'.format(order_id)


def update_order_products_delivered(order_id, products):
    with CriticalSection(get_order_update_critical_section_key(order_id)):
        order = EmergencyOrder.objects.get(pk=order_id)
        _update_order_product_info(order.products_delivered, products)
        order.save()


def update_order_products_confirmed(order_id, products):
    with CriticalSection(get_order_update_critical_section_key(order_id)):
        order = EmergencyOrder.objects.get(pk=order_id)
        _update_order_product_info(order.products_confirmed, products)
        confirmed_status = EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_CONFIRMED,
            products=products
        )
        if not order.confirmed_status:
            order.confirmed_status = confirmed_status
        order.save()


def _update_order_product_info(json_field, products):
    """
    Updates the product quantities stored in the given field.
    If the products are already present, the quantity is added to the current
    quantity for that product.
    :param json_field: the dictionary that should be updated (for example,
    order.products_delivered)
    :param products: a list of ProductQuantity objects representing the products
    and quantities to update
    """
    for product in products:
        if product.code not in products_json:
            products_json[product.code] = '0'

        current_value = Decimal(products_json[product.code])
        new_value = current_value + Decimal(product.quantity)
        products_json[product.code] = '{0:f}'.format(new_value)
