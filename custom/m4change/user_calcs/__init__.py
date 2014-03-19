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
