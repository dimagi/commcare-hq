from corehq.apps.users.models import CouchUser
from corehq.util.couch import stale_ok


def get_user_id_by_username(username):
    result = CouchUser.view(
        'users/by_username',
        key=username,
        include_docs=False,
        reduce=False,
        stale=stale_ok(),
    )
    row = result.one()
    if row:
        return row["id"]
    return None


def get_display_name_for_user_id(domain, user_id, default=None):
    if user_id:
        user = CouchUser.get_by_user_id(user_id, domain)
        if user:
            return user.full_name
    return default
