from tastypie.exceptions import BadRequest


def get_limit_offset(param_name, request_data, default, max_value=None):
    value = request_data.get(param_name, default)
    try:
        value = int(value)
    except ValueError:
        raise BadRequest(f"Invalid {param_name} '{value}' provided. Please provide a positive integer.")

    if value < 0:
        raise BadRequest(f"Invalid {param_name} '{value}' provided. Please provide a positive integer.")

    if max_value:
        value = min(value, max_value)
    return value


def sort_query(query, request_data):
    order_by = request_data.get("order_by")

    if not order_by:
        order_by_args = ["date", "id"]
    else:
        if order_by not in ("date", "-date"):
            raise BadRequest(f"No matching '{order_by}' field for ordering")
        order_by_args = [order_by, "id"]

    return query.order_by(*order_by_args)
