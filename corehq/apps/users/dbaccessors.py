from corehq.util.quickcache import quickcache
from corehq.apps.users.util import format_username


@quickcache(['username', 'domain'])
def get_user_id(username, domain):
    cc_username = format_username(username, domain)
    result = CouchUser.view(
        'users/by_username',
        key=cc_username,
        include_docs=False,
        reduce=False,
    )
    row = result.one()
    if row:
        return row["id"]
