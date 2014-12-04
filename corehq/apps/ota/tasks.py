from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.xml import V1
from casexml.apps.phone.restore import RestoreConfig
from corehq.apps.users.models import CommCareUser
from soil import DownloadBase


@task
def prime_restore(usernames_or_ids, version=V1, cache_timeout=None, overwrite_cache=False):
    total = len(usernames_or_ids)
    DownloadBase.set_progress(prime_restore, 0, total)

    ret = {'messages': []}
    for i, username_or_id in enumerate(usernames_or_ids):
        couch_user = get_user(username_or_id)
        if not couch_user:
            ret['messages'].append('User not found: {}'.format(username_or_id))
            continue

        try:
            project = couch_user.project
            commtrack_settings = project.commtrack_settings
            stock_settings = commtrack_settings.get_ota_restore_settings() if commtrack_settings else None
            restore_config = RestoreConfig(
                couch_user.to_casexml_user(), None, version, None,
                items=True,
                stock_settings=stock_settings,
                domain=project,
                force_cache=True,
                cache_timeout=cache_timeout,
                overwrite_cache=overwrite_cache
            )
            restore_config.get_payload()

            ret['messages'].append('Restore generated successfully for user: {}'.format(
                couch_user.human_friendly_name,
            ))
        except Exception as e:
            ret['messages'].append('Error processing user: {}'.format(str(e)))

        DownloadBase.set_progress(prime_restore, i + 1, total)

    return ret


def get_user(username_or_id):
    try:
        couch_user = CommCareUser.get(username_or_id)
    except ResourceNotFound:
        try:
            couch_user = CommCareUser.get_by_username(username_or_id)
        except ResourceNotFound:
            return None

    return couch_user
