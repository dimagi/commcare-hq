import random

from corehq.apps.prototype.utils.fake_case_data.dates import get_past_date, format_date
from corehq.apps.prototype.utils.fake_case_data.issues import is_mostly_false


def get_owner_info():
    return random.choice((
        ('edwenak', 'Karen Edwena [CHW]'), ('eddyv', 'Vahan Eddy [CHW]'),
        ('hartmanns', 'Sophia Hartmann [CHW]'),
        ('jonathong', 'Grace Jonathon [CHW]'), ('emilial', 'Luna Emilia [CHW]'),
        ('cobaz', 'Zak Coba [CHW]'), ('test', 'Test User'),
    ))


def maybe_get_other_username(username):
    if is_mostly_false():
        return get_owner_info()[0]
    return username


def get_case_system_info():
    is_closed = is_mostly_false()
    closed_date = get_past_date() if is_closed else None
    last_modified_date = get_past_date(closed_date)
    username, owner_name = get_owner_info()
    return last_modified_date, {
        "closed": is_closed,
        "closed_date": format_date(closed_date),
        "closed_by_username": maybe_get_other_username(username) if is_closed else None,
        "last_modified_date": format_date(last_modified_date),
        "last_modified_by_user_username": maybe_get_other_username(username),
        "opened_by": username,
        "owner_name": owner_name,
        "opened_date": format_date(get_past_date(last_modified_date)),
    }
