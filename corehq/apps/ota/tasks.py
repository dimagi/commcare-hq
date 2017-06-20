from celery.task import task
from celery import group
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.xml import V1
from casexml.apps.phone.restore import RestoreParams, RestoreCacheSettings, RestoreConfig
from corehq.apps.users.models import CommCareUser
from corehq.apps.ota.exceptions import PrimeRestoreException, PrimeRestoreUserException


def queue_prime_restore(domain, usernames_or_ids, version=V1, cache_timeout_hours=None,
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
    tasks = [
        prime_restore.s(
            username_or_id,
            domain,
            version,
            cache_timeout_hours,
            overwrite_cache,
            check_cache_only,
        ) for username_or_id in usernames_or_ids
    ]

    return group(tasks)()


@task(queue='prime_restore_queue')
def prime_restore(username_or_id, domain, version, cache_timeout_hours,
                  overwrite_cache, check_cache_only):
    couch_user = get_user(username_or_id, domain)

    try:
        project = couch_user.project
        restore_config = RestoreConfig(
            project=project,
            restore_user=couch_user.to_ota_restore_user(),
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
            ret = u'Restore cache {} for user: {}'.format(
                'EXISTS' if cached_payload else 'does not exist',
                couch_user.human_friendly_name,
            )
        else:
            restore_config.get_payload()

            cached_payload = _get_cached_payload(restore_config)
            if cached_payload:
                ret = u'Restore cached successfully for user: {}'.format(
                    couch_user.human_friendly_name,
                )
            else:
                raise PrimeRestoreException(u"Restore completed by cache still empty")

    except Exception as e:
        raise PrimeRestoreException(u'Error processing user: {}. Error was: {}'.format(
            couch_user.human_friendly_name, str(e)
        ))

    return {"messages": ret}


def _get_cached_payload(restore_config):
    original = restore_config.overwrite_cache
    try:
        # must set this to False before attempting to check the cache
        restore_config.overwrite_cache = False
        payload = restore_config.get_cached_response()
    finally:
        restore_config.overwrite_cache = original
    return payload


def get_user(username_or_id, domain):
    if '@' in username_or_id:
        user = get_user_from_username(username_or_id)
    else:
        try:
            couch_user = CommCareUser.get(username_or_id)
            user = couch_user
        except ResourceNotFound:
            username_or_id = '{}@{}.commcarehq.org'.format(username_or_id, domain)
            user = get_user_from_username(username_or_id)

    _raise_user_errors(domain, user, username_or_id)
    return user


def get_user_from_username(username):
    try:
        return CommCareUser.get_by_username(username)
    except ResourceNotFound:
        return None


def _raise_user_errors(domain, couch_user, username_or_id):
    if not couch_user:
        raise PrimeRestoreUserException(u'User not found: {}'.format(username_or_id))
    elif couch_user.domain != domain:
        raise PrimeRestoreUserException(u"User '{}' not from domain '{}'".format(
            username_or_id,
            domain
        ))
