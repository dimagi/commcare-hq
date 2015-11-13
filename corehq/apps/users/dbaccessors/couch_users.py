from corehq.apps.users.models import CouchUser


def get_user_id_by_username(self, username):
    result = CouchUser.view(
        'users/by_username',
        key=username,
        include_docs=False,
        reduce=False,
    )
    row = result.one()
    if row:
        return row["id"]
    return None
