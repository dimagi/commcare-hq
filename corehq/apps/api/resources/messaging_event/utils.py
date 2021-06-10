from base64 import b64decode
from collections import namedtuple

from django.http import QueryDict
from tastypie.exceptions import BadRequest


def get_limit_offset(param_name, request_data, default, max_value=None):
    value = request_data.get(param_name, default)
    try:
        value = int(value)
    except ValueError:
        raise BadRequest(f"Invalid {param_name} '{value}' provided. Please provide a positive integer.")

    if value <= 0:
        raise BadRequest(f"Invalid {param_name} '{value}' provided. Please provide a positive integer.")

    if max_value:
        value = min(value, max_value)
    return value


def sort_query(query, request_params):
    """Always order by date and ID to ensure consistent result order
    across requests.

    This is required for the cursor pagination.
    """
    order_by = request_params.get("order_by")

    if not order_by:
        order_by_args = ["date", "id"]
    else:
        if order_by not in ("date", "-date"):
            raise BadRequest(f"No matching '{order_by}' field for ordering")
        order_by_args = [order_by, "id"]

    return query.order_by(*order_by_args)


class CursorParams(namedtuple("CursorParams", "params, domain, is_cursor")):
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
