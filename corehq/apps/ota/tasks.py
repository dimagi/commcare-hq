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

    ret = {'messages': []}
    for i, user_id in enumerate(user_ids):
        try:
            couch_user = CommCareUser.get(user_id)
        except ResourceNotFound:
            ret['messages'].append('User not found: {}'.format(user_id))
            continue

        try:
            get_restore_response(
                couch_user.domain,
                couch_user,
                since=None,
                version=version,
                force_cache=True,
                cache_timeout=cache_timeout,
                overwrite_cache=overwrite_cache
            )
        except Exception as e:
            ret['messages'].append('Error processing user: {}'.format(str(e)))

        DownloadBase.set_progress(prime_restore, i + 1, total)

    return ret
