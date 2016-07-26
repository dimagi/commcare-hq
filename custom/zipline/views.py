import json
from corehq.apps.domain.views import DomainViewMixin
from custom.zipline.api import get_order_update_critical_section_key
from custom.zipline.models import EmergencyOrder
from dateutil.parser import parse as parse_timestamp
from dimagi.utils.couch import CriticalSection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.utils.decorators import method_decorator


class OrderStatusValidationError(Exception):

    def __init__(self, message, *args, **kwargs):
        self.error_message = message
        super(OrderStatusValidationError, self).__init__(message, *args, **kwargs)


class ZiplineOrderStatusView(View, DomainViewMixin):

    urlname = 'zipline_order_status'

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(ZiplineOrderStatusView, self).dispatch(*args, **kwargs)

    def get_error_response(self, description):
        return JsonResponse({
            'status': 'error',
            'description': description,
        })

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

    def validate_and_clean_string(self, data, field_name):
        value = data.get(field_name)
        error_msg = "Field '{}' is required and expected to be a string".format(field_name)

        if not isinstance(value, basestring):
            raise OrderStatusValidationError(error_msg)

    def get_validate_and_clean_method(self, status):
        return {
        }.get(status)

    def get_process_method(self, status):
        return {
        }.get(status)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except (TypeError, ValueError):
            return self.get_error_response('Could not parse JSON')

        if not isinstance(data, dict):
            return self.get_error_response('JSON object expected')

        try:
            self.validate_and_clean_int(data, 'orderId')
            self.validate_and_clean_timestamp(data, 'timestamp')
            self.validate_and_clean_string(data, 'status')
        except OrderStatusValidationError as e:
            return self.get_error_response(e.error_message)

        order_id = data['orderId']
        status = data['status']

        validate_and_clean = self.get_validate_and_clean_method(status)
        process = self.get_process_method(status)

        if validate_and_clean is None or process is None:
            return self.get_error_response("Unkown status received: '{}'".format(status))

        try:
            validate_and_clean(data)
        except OrderStatusValidationError as e:
            return self.get_error_response(e.error_message)

        with CriticalSection([get_order_update_critical_section_key(order_id)]):
            try:
                order = EmergencyOrder.objects.get(pk=order_id)
            except EmergencyOrder.DoesNotExist:
                return self.get_error_response('Order not found')

            if order.domain != self.domain:
                return self.get_error_response('Order not found')

            response_dict = process(order, data)

        return JsonResponse(response_dict)
