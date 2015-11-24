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
