from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.xml import V1
from corehq.apps.users.models import CommCareUser
from soil import DownloadBase


@task
def prime_restore(user_ids, version=V1, cache_timeout=None, overwrite_cache=False):
    from corehq.apps.ota.views import get_restore_response
    total = len(user_ids)
    DownloadBase.set_progress(prime_restore, 0, total)

    for i, user_id in enumerate(user_ids):
        print i, user_id
        try:
            couch_user = CommCareUser.get(user_id)
        except ResourceNotFound:
            return

        get_restore_response(
            couch_user.domain,
            couch_user,
            since=None,
            version=version,
            force_cache=True,
            cache_timeout=cache_timeout,
            overwrite_cache=overwrite_cache
        )
        DownloadBase.set_progress(prime_restore, i + 1, total)
