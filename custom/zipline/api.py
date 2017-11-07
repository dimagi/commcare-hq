from __future__ import absolute_import
from custom.zipline.models import (EmergencyOrder, EmergencyOrderStatusUpdate,
    update_product_quantity_json_field)
from datetime import datetime
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception
from django.db import transaction


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

    order = EmergencyOrder(
        domain=domain,
        requesting_user_id=user.get_id,
        requesting_phone_number=phone_number,
        location=location,
        location_code=location.site_code,
        timestamp=datetime.utcnow()
    )
    update_product_quantity_json_field(order.products_requested, products)
    order.save()

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
        with CriticalSection([get_order_update_critical_section_key(order.pk)]), transaction.atomic():
            # refresh the object now that we're in the CriticalSection
            order = EmergencyOrder.objects.get(pk=order.pk)
            update_order_products_confirmed(order, products)


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


def update_order_products_confirmed(order, products):
    update_product_quantity_json_field(order.products_confirmed, products)
    confirmed_status = EmergencyOrderStatusUpdate.create_for_order(
        order.pk,
        EmergencyOrderStatusUpdate.STATUS_CONFIRMED,
        products=products
    )
    if not order.confirmed_status:
        order.confirmed_status = confirmed_status
    order.save()


def log_zipline_exception(message, details=None):
    message = "[ZIPLINE] {}".format(message)
    notify_exception(None, message=message, details=details)
