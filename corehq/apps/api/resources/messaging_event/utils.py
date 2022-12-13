from base64 import b64decode

from attr import attrib, attrs
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _
from tastypie.exceptions import BadRequest


LIMIT_PARAM_ERROR_MESSAGE = _("Invalid limit '{value}' provided. Please provide a positive integer.")


def get_limit_offset(param_name, request_data, default, max_value=None):
    value = request_data.get(param_name, default)

    try:
        value = int(value)
    except ValueError:
        raise BadRequest(LIMIT_PARAM_ERROR_MESSAGE.format(param_name=param_name, value=value))

    if value <= 0:
        raise BadRequest(LIMIT_PARAM_ERROR_MESSAGE.format(param_name=param_name, value=value))

    if max_value:
        value = min(value, max_value)
    return value


def sort_query(query, request_params):
    """Always order by date and ID to ensure consistent result order
    across requests.

    This is required for the cursor pagination.
    """
    order_by = get_order_by_field(request_params)
    return query.order_by(order_by, "id")


def get_order_by_field(request_params):
    order_by = request_params.get("order_by")

    if not order_by:
        return "date_last_activity"

    if order_by not in ("date_last_activity", "-date_last_activity"):
        # ("date", "-date") were removed due to the large index required to make this efficient
        raise BadRequest(_("No matching '{field_name}' field for ordering").format(field_name=order_by))

    return order_by


@attrs
class CursorParams():
    params = attrib()
    domain = attrib()
    is_cursor = attrib()

    def __getitem__(self, key):
        return self.params[key]

    def __contains__(self, key):
        return key in self.params

    def items(self):
        return self.params.items()

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def get_request_params(request):
    """Get the query params from the request. If the request is using a cursor
    decode the cursor and return those values as the query params.
    :returns: CursorParams tuple"""
    request_params = request.GET.dict()
    if 'cursor' in request_params:
        params_string = b64decode(request_params['cursor']).decode('utf-8')
        return CursorParams(
            QueryDict(params_string).dict(), request.domain, True
        )
    return CursorParams(request_params, request.domain, False)
