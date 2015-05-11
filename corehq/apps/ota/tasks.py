from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.xml import V1
from casexml.apps.phone.restore import RestoreParams, RestoreCacheSettings, RestoreConfig
from corehq.apps.users.models import CommCareUser
from soil import DownloadBase


@task
def prime_restore(domain, usernames_or_ids, version=V1, cache_timeout_hours=None,
                  overwrite_cache=False, check_cache_only=False):
    """
    Task to generate and cache a restore payload for each user passed in.

    :param domain:              The domain name for the users
    :param usernames_or_ids:    List of usernames or user IDs
    :param version:             Restore format version
    :param cache_timeout_hours: Hours to cache the payload
    :param overwrite_cache:     If True overwrite any existing cache
    :param check_cache_only:    Don't generate the payload, just check if it is already cached
    """
    total = len(usernames_or_ids)
    DownloadBase.set_progress(prime_restore, 0, total)

    ret = {'messages': []}
    for i, username_or_id in enumerate(usernames_or_ids):
        couch_user = get_user(username_or_id, domain)
        if not couch_user:
            ret['messages'].append('WARNING: User not found: {}'.format(username_or_id))
            continue
        elif couch_user.domain != domain:
            ret['messages'].append("WARNING: User '{}' not from domain '{}'".format(
                username_or_id,
                domain
            ))
            continue

        try:
            project = couch_user.project
            restore_config = RestoreConfig(
                domain=project,
                user=couch_user.to_casexml_user(),
                params=RestoreParams(
                    version=version,
                    include_item_count=True,
                ),
                cache_settings=RestoreCacheSettings(
                    force_cache=True,
                    cache_timeout=cache_timeout_hours * 60 * 60,
                    overwrite_cache=overwrite_cache
                )
            )

            if check_cache_only:
                cached_payload = _get_cached_payload(restore_config)
                ret['messages'].append(u'Restore cache {} for user: {}'.format(
                    'EXISTS' if cached_payload else 'does not exist',
                    couch_user.human_friendly_name,
                ))
            else:
                restore_config.get_payload()

                cached_payload = _get_cached_payload(restore_config)
                if cached_payload:
                    ret['messages'].append('SUCCESS: Restore cached successfully for user: {}'.format(
                        couch_user.human_friendly_name,
                    ))
                else:
                    ret['messages'].append('ERROR: Restore completed by cache still empty for user: {}'.format(
                        couch_user.human_friendly_name,
                    ))
        except Exception as e:
            ret['messages'].append('ERROR: Error processing user: {}'.format(str(e)))

        DownloadBase.set_progress(prime_restore, i + 1, total)

    return ret


def _get_cached_payload(restore_config):
    original = restore_config.overwrite_cache
    try:
        # must set this to False before attempting to check the cache
        restore_config.overwrite_cache = False
        payload = restore_config.get_cached_payload()
    finally:
        restore_config.overwrite_cache = original
    return payload


def get_user(username_or_id, domain):
    if '@' in username_or_id:
        return get_user_from_username(username_or_id)
    else:
        try:
            couch_user = CommCareUser.get(username_or_id)
            return couch_user
        except ResourceNotFound:
            username_or_id = '{}@{}.commcarehq.org'.format(username_or_id, domain)
            return get_user_from_username(username_or_id)


def get_user_from_username(username):
    try:
        return CommCareUser.get_by_username(username)
    except ResourceNotFound:
        return None
