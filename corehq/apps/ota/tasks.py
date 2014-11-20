from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from corehq.apps.ota.views import get_restore_response
from corehq.apps.users.models import CommCareUser


@task
def prime_restore(user_id, since=None, version='1.0', state=None, items=False, cache_timeout=None):
    try:
        couch_user = CommCareUser.get(user_id)
    except ResourceNotFound:
        return

    get_restore_response(
        couch_user.domain,
        couch_user,
        since=since,
        version=version,
        state=state,
        items=items,
        force_cache=True,
        cache_timeout=cache_timeout
    )
