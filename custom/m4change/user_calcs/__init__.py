from couchdbkit import ResourceNotFound
from corehq.apps.users.models import CommCareUser

def update_value_for_date(date, dates):
    if date not in dates:
        dates[date] = 1
    else:
        dates[date] += 1


def is_valid_user_by_case(case):
    if hasattr(case, "user_id"):
        return (hasattr(case, "user_id") and case.user_id not in [None, "", "demo_user"])
    return False


def is_user_in_CCT_by_case(case):
    if is_valid_user_by_case(case):
        try:
            user = CommCareUser.get(case.user_id) or None
            return (user is not None and hasattr(user, "user_data") and user.user_data.get("CCT", None) == "true")
        except ResourceNotFound:
            return False
    return False


def get_date_delivery(form):
    return form.get("form", {}).get("date_delivery", None)


def get_date_modified(form):
    return form.get("form", {}).get("case", {}).get("@date_modified", None)


def get_case_date_delivery(case):
    return case.date_delivery


def get_case_date_modified(case):
    return case.modified_on.date() if case.modified_on is not None else None


def form_passes_filter_date_delivery(form, namespaces):
    return (form.xmlns in namespaces and get_date_delivery(form) is not None)


def form_passes_filter_date_modified(form, namespaces):
    return (form.xmlns in namespaces and get_date_modified(form) is not None)


def case_passes_filter_date_delivery(case):
    return (hasattr(case, "date_delivery") and get_case_date_delivery(case) is not None)


def case_passes_filter_date_modified(case):
    return (hasattr(case, "modified_on") and get_case_date_modified(case) is not None)
