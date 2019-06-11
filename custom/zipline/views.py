from __future__ import absolute_import
from __future__ import unicode_literals
import json
import re
from corehq.apps.api.decorators import api_user_basic_auth
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.util.python_compatibility import soft_assert_type_text
from custom.zipline.api import get_order_update_critical_section_key, ProductQuantity
from custom.zipline.models import (EmergencyOrder, EmergencyOrderStatusUpdate,
    update_product_quantity_json_field, EmergencyOrderPackage)
from dateutil.parser import parse as parse_timestamp
from decimal import Decimal
from dimagi.utils.couch import CriticalSection
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.utils.decorators import method_decorator
import six


ZIPLINE_PERMISSION = 'ZIPLINE'


def get_error_response(description):
    return JsonResponse({
        'status': 'error',
        'description': description,
    })


class OrderStatusValidationError(Exception):

    def __init__(self, message, *args, **kwargs):
        self.error_message = message
        super(OrderStatusValidationError, self).__init__(message, *args, **kwargs)


class ZiplineOrderStatusView(View, DomainViewMixin):
    urlname = 'zipline_order_status'

    @method_decorator(api_user_basic_auth(ZIPLINE_PERMISSION))
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(ZiplineOrderStatusView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (TypeError, ValueError):
            return get_error_response('Could not parse JSON')

        if not isinstance(data, dict):
            return get_error_response('JSON object expected')

        status = data.get('status')

        view = {
            EmergencyOrderStatusUpdate.STATUS_APPROVED: ApprovedStatusUpdateView,
            EmergencyOrderStatusUpdate.STATUS_CANCELLED: CancelledStatusUpdateView,
            EmergencyOrderStatusUpdate.STATUS_DISPATCHED: DispatchedStatusUpdateView,
            EmergencyOrderStatusUpdate.STATUS_DELIVERED: DeliveredStatusUpdateView,
            EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT: CancelledInFlightStatusUpdateView,
            EmergencyOrderStatusUpdate.STATUS_APPROACHING_ETA: ApproachingEtaStatusUpdateView,
            EmergencyOrderStatusUpdate.STATUS_ETA_DELAYED: EtaDelayedStatusUpdateView,
        }.get(status)

        if view is None:
            return get_error_response("Unknown status received: '{}'".format(status))

        return view.as_view()(request, *args, **kwargs)


class BaseZiplineStatusUpdateView(View, DomainViewMixin):

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(BaseZiplineStatusUpdateView, self).dispatch(*args, **kwargs)

    def validate_and_clean_int(self, data, field_name):
        value = data.get(field_name)
        error_msg = "Field '{}' is required and expected to be an int".format(field_name)

        try:
            value = int(value)
        except (TypeError, ValueError):
            raise OrderStatusValidationError(error_msg)

        data[field_name] = value

    def validate_and_clean_timestamp(self, data, field_name):
        value = data.get(field_name)
        error_msg = "Field '{}' is required and expected to be an ISO 8601 UTC timestamp".format(field_name)

        if not value:
            raise OrderStatusValidationError(error_msg)

        try:
            value = parse_timestamp(value)
        except ValueError:
            raise OrderStatusValidationError(error_msg)

        data[field_name] = value

    def validate_string(self, data, field_name):
        value = data.get(field_name)
        error_msg = "Field '{}' is required and expected to be a string".format(field_name)

        if not isinstance(value, six.string_types):
            raise OrderStatusValidationError(error_msg)
        soft_assert_type_text(value)

    def validate_and_clean_time(self, data, field_name):
        value = data.get(field_name)
        error_msg = "Field '{}' is required and expected to be a 24-hour time string HH:MM".format(field_name)

        if not isinstance(value, six.string_types):
            raise OrderStatusValidationError(error_msg)
        soft_assert_type_text(value)

        if not re.match(r'^\d\d?:\d\d$', value):
            raise OrderStatusValidationError(error_msg)

        try:
            value = parse_timestamp(value).time()
        except ValueError:
            raise OrderStatusValidationError(error_msg)

        data[field_name] = value

    def validate_decimal(self, data, field_name):
        value = data.get(field_name)
        error_msg = "Field '{}' is required and expected to be a numeric string".format(field_name)

        if not isinstance(value, six.string_types):
            raise OrderStatusValidationError(error_msg)
        soft_assert_type_text(value)

        try:
            Decimal(value)
        except:
            raise OrderStatusValidationError(error_msg)

    def validate_and_clean_products(self, data, field_name):
        value = data.get(field_name)
        result = []
        data_type_error = \
            "Field '{}' is required and expected to be a non-empty list of JSON objects".format(field_name)

        if not isinstance(value, list):
            raise OrderStatusValidationError(data_type_error)

        if len(value) == 0:
            raise OrderStatusValidationError(data_type_error)

        for item in value:
            if not isinstance(item, dict):
                raise OrderStatusValidationError(data_type_error)

            self.validate_string(item, 'productCode')
            self.validate_decimal(item, 'quantity')
            result.append(ProductQuantity(item['productCode'], item['quantity']))

        data[field_name] = result

    def validate_status_is_not(self, status, order, data):
        error_msg = "Cannot set a status of {} because status is already {}".format(data['status'], status)
        if order.status == status:
            raise OrderStatusValidationError(error_msg)

    def validate_and_clean_payload(self, order, data):
        """
        Validates and cleans parameters in the data dict.
        :param order: the order that this request pertains to
        :param data: the cleaned json payload in this request
        """
        raise NotImplementedError()

    def process_status_update(self, order, data):
        """
        Processes the status update.
        :param order: the order that this request pertains to
        :param data: the cleaned json payload in this request
        """
        raise NotImplementedError()

    def send_sms_for_status_update(self, order, data):
        """
        Sends the necessary SMS, if any, for the status update.
        :param order: the order that this request pertains to
        :param data: the cleaned json payload in this request
        """
        raise NotImplementedError()

    def all_flights_cancelled(self, order):
        """
        :param order: the EmergencyOrder to check
        :return: True if all of the packages for this order have been cancelled
        in flight.
        """
        packages_cancelled = EmergencyOrderStatusUpdate.objects.filter(
            order_id=order.pk,
            status=EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT,
        ).values_list('package_number').distinct().count()

        return packages_cancelled == order.total_packages

    def all_flights_done(self, order):
        """
        :param order: the EmergencyOrder to check
        :return: True if all of the packages for this order have either been delivered
        or cancelled in flight and at least one of them has been delivered.
        """
        packages_delivered_or_cancelled = EmergencyOrderStatusUpdate.objects.filter(
            order_id=order.pk,
            status__in=(
                EmergencyOrderStatusUpdate.STATUS_DELIVERED,
                EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT,
            )
        )

        package_numbers = set()
        statuses = set()

        for status_update in packages_delivered_or_cancelled:
            package_numbers.add(status_update.package_number)
            statuses.add(status_update.status)

        return (
            len(package_numbers) == order.total_packages and
            EmergencyOrderStatusUpdate.STATUS_DELIVERED in statuses
        )

    def get_dispatched_status_or_none(self, order, package_number):
        result = EmergencyOrderStatusUpdate.objects.filter(
            order_id=order.pk,
            package_number=package_number,
            status=EmergencyOrderStatusUpdate.STATUS_DISPATCHED
        ).order_by('-zipline_timestamp')[:1]

        result = list(result)

        if len(result) > 0:
            return result[0]

        return None

    def carry_forward_dispatched_data(self, order, package_number):
        dispatched_status = self.get_dispatched_status_or_none(order, package_number)
        if dispatched_status:
            return {
                'package_id': dispatched_status.package_id,
                'vehicle_id': dispatched_status.vehicle_id,
                'products': [ProductQuantity(code, data.get('quantity'))
                             for code, data in six.iteritems(dispatched_status.products)],
            }
        else:
            return {}

    def get_package_object(self, order, package_number):
        # This always gets invoked from within a CriticalSection, so no need to
        # add locking here
        package, _ = EmergencyOrderPackage.objects.get_or_create(
            order=order,
            package_number=package_number,
        )
        return package

    def post(self, request, *args, **kwargs):
        # request.body already confirmed to be a valid json dict in ZiplineOrderStatusView
        data = json.loads(request.body.decode('utf-8'))

        try:
            self.validate_and_clean_int(data, 'orderId')
            self.validate_and_clean_timestamp(data, 'timestamp')
        except OrderStatusValidationError as e:
            return get_error_response(e.error_message)

        order_id = data['orderId']

        with CriticalSection([get_order_update_critical_section_key(order_id)]), transaction.atomic():
            try:
                order = EmergencyOrder.objects.get(pk=order_id)
            except EmergencyOrder.DoesNotExist:
                return get_error_response('Order not found')

            if order.domain != self.domain:
                return get_error_response('Order not found')

            try:
                self.validate_and_clean_payload(order, data)
            except OrderStatusValidationError as e:
                return get_error_response(e.error_message)

            send_sms_response, response_dict = self.process_status_update(order, data)

        if send_sms_response:
            # This should be done outside of the transaction to prevent issues with QueuedSMS pk's
            # being available immediately.
            self.send_sms_for_status_update(order, data)

        return JsonResponse(response_dict)


class ApprovedStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        self.validate_and_clean_int(data, 'totalPackages')

    def process_status_update(self, order, data):
        approved_status = EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_APPROVED,
            zipline_timestamp=data['timestamp']
        )

        send_sms_response = False
        if not order.approved_status:
            send_sms_response = True
            order.status = EmergencyOrderStatusUpdate.STATUS_APPROVED
            order.total_packages = data['totalPackages']
            order.approved_status = approved_status
            order.save()

        return send_sms_response, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass


class CancelledStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        pass

    def process_status_update(self, order, data):
        cancelled_status = EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_CANCELLED,
            zipline_timestamp=data['timestamp']
        )

        send_sms_response = False
        if not order.cancelled_status:
            send_sms_response = True
            order.status = EmergencyOrderStatusUpdate.STATUS_CANCELLED
            order.cancelled_status = cancelled_status
            order.save()

        return send_sms_response, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass


class DispatchedStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        self.validate_and_clean_int(data, 'packageNumber')
        self.validate_string(data, 'packageId')
        self.validate_string(data, 'vehicleId')
        self.validate_and_clean_time(data, 'eta')
        self.validate_and_clean_products(data, 'products')

    def process_status_update(self, order, data):
        dispatched_status = EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_DISPATCHED,
            zipline_timestamp=data['timestamp'],
            package_number=data['packageNumber'],
            package_id=data['packageId'],
            vehicle_id=data['vehicleId'],
            products=data['products'],
            eta=data['eta']
        )

        if not order.dispatched_status:
            order.status = EmergencyOrderStatusUpdate.STATUS_DISPATCHED
            order.dispatched_status = dispatched_status
            order.save()

        package = self.get_package_object(order, data['packageNumber'])
        if package.status not in (
            EmergencyOrderStatusUpdate.STATUS_DELIVERED,
            EmergencyOrderStatusUpdate.STATUS_CANCELLED,
        ):
            package.status = EmergencyOrderStatusUpdate.STATUS_DISPATCHED

        if not package.dispatched_status:
            package.dispatched_status = dispatched_status
            update_product_quantity_json_field(package.products, data['products'])
            package.update_calculated_fields()

        package.save()

        return True, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass


class DeliveredStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        self.validate_and_clean_int(data, 'packageNumber')

    def process_status_update(self, order, data):
        dispatched_data = self.carry_forward_dispatched_data(order, data['packageNumber'])
        delivered_status = EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_DELIVERED,
            zipline_timestamp=data['timestamp'],
            package_number=data['packageNumber'],
            **dispatched_data
        )

        update_product_quantity_json_field(order.products_delivered, dispatched_data['products'])

        if not order.delivered_status and self.all_flights_done(order):
            order.status = EmergencyOrderStatusUpdate.STATUS_DELIVERED
            order.delivered_status = delivered_status

        order.save()

        package = self.get_package_object(order, data['packageNumber'])
        if not package.delivered_status:
            package.status = EmergencyOrderStatusUpdate.STATUS_DELIVERED
            package.delivered_status = delivered_status
            package.save()

        return True, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass


class CancelledInFlightStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        self.validate_and_clean_int(data, 'packageNumber')

    def process_status_update(self, order, data):
        cancelled_in_flight_status = EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT,
            zipline_timestamp=data['timestamp'],
            package_number=data['packageNumber'],
            **self.carry_forward_dispatched_data(order, data['packageNumber'])
        )

        if not order.delivered_status and self.all_flights_done(order):
            order.status = EmergencyOrderStatusUpdate.STATUS_DELIVERED
            order.delivered_status = EmergencyOrderStatusUpdate.objects.filter(
                order_id=order.pk,
                status=EmergencyOrderStatusUpdate.STATUS_DELIVERED
            ).order_by('-zipline_timestamp')[0]
            order.save()
        elif not order.cancelled_status and self.all_flights_cancelled(order):
            order.status = EmergencyOrderStatusUpdate.STATUS_CANCELLED
            order.cancelled_status = cancelled_in_flight_status
            order.save()

        package = self.get_package_object(order, data['packageNumber'])
        if not package.cancelled_status:
            package.status = EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT
            package.cancelled_status = cancelled_in_flight_status
            package.save()

        return True, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass


class ApproachingEtaStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        self.validate_and_clean_int(data, 'packageNumber')
        self.validate_and_clean_int(data, 'minutesRemaining')

    def process_status_update(self, order, data):
        EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_APPROACHING_ETA,
            zipline_timestamp=data['timestamp'],
            package_number=data['packageNumber'],
            eta_minutes_remaining=data['minutesRemaining'],
            **self.carry_forward_dispatched_data(order, data['packageNumber'])
        )

        return True, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass


class EtaDelayedStatusUpdateView(BaseZiplineStatusUpdateView):

    def validate_and_clean_payload(self, order, data):
        self.validate_and_clean_int(data, 'packageNumber')
        self.validate_and_clean_time(data, 'newEta')

    def process_status_update(self, order, data):
        EmergencyOrderStatusUpdate.create_for_order(
            order.pk,
            EmergencyOrderStatusUpdate.STATUS_ETA_DELAYED,
            zipline_timestamp=data['timestamp'],
            package_number=data['packageNumber'],
            eta=data['newEta'],
            **self.carry_forward_dispatched_data(order, data['packageNumber'])
        )

        return True, {'status': 'success'}

    def send_sms_for_status_update(self, order, data):
        pass
