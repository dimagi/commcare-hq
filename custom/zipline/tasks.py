import json
import requests
from celery.task import task
from custom.zipline.api import get_order_update_critical_section_key
from custom.zipline.models import EmergencyOrder, EmergencyOrderStatusUpdate
from django.conf import settings
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_datetime
from requests.auth import HTTPBasicAuth
import six


ZIPLINE_STATUS_RECEIVED = 'received'
ZIPLINE_STATUS_REJECTED = 'rejected'
ZIPLINE_STATUS_ERROR = 'error'

# The timeout (in seconds) to use when making requests to Zipline
REQUEST_TIMEOUT = 120

# See send_emergency_order_request()
RETRY_INTERVAL = 5
MAX_ATTEMPTS = 3


@task(serializer='pickle', ignore_result=True)
def send_emergency_order_request(order_id, attempt=1):
    try:
        with CriticalSection(
            [get_order_update_critical_section_key(order_id)],
            timeout=(REQUEST_TIMEOUT + 10)
        ):
            order = EmergencyOrder.objects.get(pk=order_id)
            order.status = _send_emergency_order_request(order, attempt)
            order.save()
    except Exception as e:
        notify_exception(
            None,
            message='[ZIPLINE] Error while sending order',
            details={
                'order_id': order_id,
                'attempt': attempt,
            }
        )
        create_error_record(order, 'Internal error: {}'.format(str(e)))
        handle_emergency_order_request_retry(order, attempt)


def _send_emergency_order_request(order, attempt):
    """
    Sends the emergency order request to Zipline.
    :param order: the EmergencyOrder that should be sent
    :param attempt: the current attempt number; in the event of errors, a total of MAX_ATTEMPTS will
    be made, separated by a wait time of RETRY_INTERVAL minutes
    :return: the new status to be set on the order
    """
    order.zipline_request_attempts += 1

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
        create_error_record(order, 'Received HTTP Response {} from Zipline'.format(response.status_code))
        return EmergencyOrderStatusUpdate.STATUS_ERROR

    response_text = response.text
    try:
        response_json = json.loads(response_text)
    except (TypeError, ValueError):
        notify_exception(
            None,
            message='[ZIPLINE] Invalid JSON response received',
            details={
                'order_id': order.pk,
                'attempt': attempt,
            }
        )
        create_error_record(order, 'Could not parse JSON response from Zipline: {}'.format(response_text))
        handle_emergency_order_request_retry(order, attempt)
        return EmergencyOrderStatusUpdate.STATUS_ERROR

    status = response_json.get('status')
    if status == ZIPLINE_STATUS_RECEIVED:
        handle_request_received(order)
        return EmergencyOrderStatusUpdate.STATUS_RECEIVED
    elif status == ZIPLINE_STATUS_REJECTED:
        reason = response_json.get('reason')
        handle_request_rejected(order, reason)
        return EmergencyOrderStatusUpdate.STATUS_REJECTED
    elif status == ZIPLINE_STATUS_ERROR:
        description = response_json.get('description')
        create_error_record(order, 'Error received from Zipline: {}'.format(description))
        return EmergencyOrderStatusUpdate.STATUS_ERROR
    else:
        create_error_record(order, 'Unrecognized status received from Zipline: {}'.format(status))
        handle_emergency_order_request_retry(order, attempt)
        return EmergencyOrderStatusUpdate.STATUS_ERROR


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
            {'productCode': code, 'quantityOrdered': info.get('quantity')}
            for code, info in six.iteritems(order.products_requested)
        ],
    }


def handle_request_received(order):
    """
    Handles a received response from Zipline.
    :param order: the EmergencyOrder for the request
    """
    order.received_status = EmergencyOrderStatusUpdate.create_for_order(
        order.pk,
        EmergencyOrderStatusUpdate.STATUS_RECEIVED
    )


def handle_request_rejected(order, reason):
    """
    Handles a rejected response from Zipline.
    :param order: the EmergencyOrder for the request
    """
    order.rejected_status = EmergencyOrderStatusUpdate.create_for_order(
        order.pk,
        EmergencyOrderStatusUpdate.STATUS_REJECTED,
        additional_text=reason
    )


def create_error_record(order, error_message):
    EmergencyOrderStatusUpdate.create_for_order(
        order.pk,
        EmergencyOrderStatusUpdate.STATUS_ERROR,
        additional_text=error_message
    )


def handle_emergency_order_request_retry(order, current_attempt):
    """
    Handles retrying an emergency order.
    :param order: the EmergencyOrder to retry
    :param current_attempt: the current attempt number
    """
    if current_attempt < MAX_ATTEMPTS:
        send_emergency_order_request.apply_async(
            args=[order.pk],
            kwargs={'attempt': (current_attempt + 1)},
            countdown=(60 * RETRY_INTERVAL)
        )
