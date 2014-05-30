
def is_valid_user_by_case(case):
    if hasattr(case, "user_id"):
        return (hasattr(case, "user_id") and case.user_id not in [None, "", "demo_user"])
    return False


def get_date_delivery(form):
    return form.form.get("date_delivery", None)


def get_received_on(form):
    return form.received_on.date()


def form_passes_filter_date_delivery(form):
    return get_date_delivery(form) is not None


def string_to_numeric(string, type=int):
    try:
        return type(string)
    except ValueError:
        return 0
