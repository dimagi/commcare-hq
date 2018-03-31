from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.couch import stale_ok


def users_have_locations(domain):
    from corehq.apps.users.models import CouchUser
    return bool(CouchUser.get_db().view(
        'users_extra/users_by_location_id',
        startkey=[domain],
        endkey=[domain, {}],
        reduce=True,
        stale=stale_ok(),
    ).one())
