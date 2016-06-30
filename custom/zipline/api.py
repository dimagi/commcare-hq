from custom.zipline.models import EmergencyOrder
from datetime import datetime
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


def get_order_update_critical_section_key(order_id):
    """
    :param order_id: the pk of the order
    :return: the key to be used with CriticalSection for preventing multiple
    threads from updating the same order at the same time
    """
    return 'zipline-updating-order-id-{}'.format(order_id)
