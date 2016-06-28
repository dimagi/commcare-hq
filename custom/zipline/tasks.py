import json
import requests
from celery.task import task
from collections import namedtuple
from custom.zipline.models import EmergencyOrder, EmergencyOrderStatusUpdate
from datetime import datetime
from django.conf import settings
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_datetime
from requests.auth import HTTPBasicAuth


ZIPLINE_STATUS_RECEIVED = 'received'
ZIPLINE_STATUS_REJECTED = 'rejected'
ZIPLINE_STATUS_ERROR = 'error'

# The timeout (in seconds) to use when making requests to Zipline
REQUEST_TIMEOUT = 120

# See send_emergency_order_request()
RETRY_INTERVAL = 5
MAX_ATTEMPTS = 3


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
    order = EmergencyOrder.objects.create(
        domain=domain,
        requesting_user_id=user.get_id,
        requesting_phone_number=phone_number,
        location=location,
        location_code=location.site_code,
        product_info=[{'code': p.code, 'quantity': p.quantity} for p in products],
        timestamp=datetime.utcnow()
    )

    send_emergency_order_request(order)


@task(ignore_result=True)
def send_emergency_order_request(order, attempt=1):
    try:
        _send_emergency_order_request(order, attempt)
    except:
        notify_exception(
            None,
            message='[ZIPLINE] Error while sending order',
            details={
                'order_id': order.pk,
                'attempt': attempt,
            }
        )
        handle_emergency_order_request_retry(order, attempt)


def _send_emergency_order_request(order, attempt):
    """
    Sends the emergency order request to Zipline.
    :param order: the EmergencyOrder that should be sent
    :param attempt: the current attempt number; in the event of errors, a total of MAX_ATTEMPTS will
    be made, separated by a wait time of RETRY_INTERVAL minutes
    """
    json_payload = get_json_payload_from_order(order)
    json_payload = json.dumps(json_payload)

    response = requests.post(
        settings.ZIPLINE_API_URL,
        auth=HTTPBasicAuth(settings.ZIPLINE_API_USER, settings.ZIPLINE_API_PASSWORD),
        data=json_payload,
        headers={'Content-Type': 'application/json'},
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        handle_emergency_order_request_retry(order, attempt)
        return

    try:
        response_json = response.json()
    except:
        notify_exception(
            None,
            message='[ZIPLINE] Invalid JSON response received',
            details={
                'order_id': order.pk,
                'attempt': attempt,
            }
        )
        handle_emergency_order_request_retry(order, attempt)
        return

    status = response_json.get('status')
    if status == ZIPLINE_STATUS_RECEIVED:
        handle_request_received(order)
    elif status == ZIPLINE_STATUS_REJECTED:
        handle_request_rejected(order)
    else:
        handle_emergency_order_request_retry(order, attempt)


def get_json_payload_from_order(order):
    """
    Takes an EmergencyOrder and returns a dictionary representing the JSON
    payload that should be sent to represent it.
    :param order: the EmergencyOrder object
    :return: dict
    """
    return {
        'transactionType': 'emergencyOrder',
        'timestamp': json_format_datetime(order.timestamp),
        'orderId': order.pk,
        'locationCode': order.location_code,
        'products': [
            {'productCode': p.get('code'), 'quantityOrdered': p.get('quantity')}
            for p in order.product_info
        ],
    }


def handle_request_received(order):
    """
    Handles a received response from Zipline.
    :param order: the EmergencyOrder for the request
    """
    EmergencyOrderStatusUpdate.create_for_order(order.pk, EmergencyOrderStatusUpdate.STATUS_RECEIVED)


def handle_request_rejected(order):
    """
    Handles a rejected response from Zipline.
    :param order: the EmergencyOrder for the request
    """
    EmergencyOrderStatusUpdate.create_for_order(order.pk, EmergencyOrderStatusUpdate.STATUS_REJECTED)


def handle_emergency_order_request_retry(order, current_attempt):
    """
    Handles retrying an emergency order.
    :param order: the EmergencyOrder to retry
    :param current_attempt: the current attempt number
    """
    if current_attempt < MAX_ATTEMPTS:
        send_emergency_order_request.apply_async(
            args=[order],
            kwargs={'attempt': (current_attempt + 1)},
            countdown=(60 * RETRY_INTERVAL)
        )
