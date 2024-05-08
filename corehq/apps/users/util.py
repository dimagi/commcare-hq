import datetime
import numbers
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import html
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege

from casexml.apps.case.const import (
    ARCHIVED_CASE_OWNER_ID,
    UNOWNED_EXTENSION_OWNER_ID,
)

from corehq import privileges
from corehq.apps.callcenter.const import CALLCENTER_USER
from corehq.const import USER_CHANGE_VIA_AUTO_DEACTIVATE
from corehq.util.quickcache import quickcache

# SYSTEM_USER_ID is used when submitting xml to make system-generated case updates
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.parsing import json_format_datetime

SYSTEM_USER_ID = 'system'
DEMO_USER_ID = 'demo_user'
WEIRD_USER_IDS = [
    'commtrack-system',    # internal HQ/commtrack system forms
    DEMO_USER_ID,           # demo mode
    'demo_user_group_id',  # demo mode with case sharing enabled
    UNOWNED_EXTENSION_OWNER_ID,
    SYSTEM_USER_ID,
    ARCHIVED_CASE_OWNER_ID,
    CALLCENTER_USER
]
USER_FIELDS_TO_IGNORE_FOR_HISTORY = [
    '_id', '_rev', 'reporting_metadata', 'password',
    'devices', 'last_device', 'device_ids'
]


def generate_mobile_username(username, domain, is_unique=True):
    """
    Returns the email formatted mobile username if successfully generated
    Handles exceptions raised by .validation.validate_mobile_username with user facing messages
    Any additional validation should live in .validation.validate_mobile_username
    :param username: accepts both incomplete ('example-user') or complete ('example-user@domain.commcarehq.org')
    :param domain: required str, domain name
    :param is_unique: if true then username should not already exist
    :return: str, email formatted mobile username
    Example use: generate_mobile_username('username', 'domain') -> 'username@domain.commcarehq.org'
    """
    from .validation import validate_mobile_username
    username = get_complete_username(username, domain)
    validate_mobile_username(username, domain, is_unique)
    return username


def get_complete_username(username, domain):
    """
    :param username: accepts both incomplete ('example-user') or complete ('example-user@domain.commcarehq.org')
    :param domain: domain associated with the mobile user
    :return: the complete username ('example-user@domain.commcarehq.org')
    """
    # this method is not responsible for validation, and therefore does the most basic email format check
    if '@' not in username:
        username = format_username(username, domain)

    return username


def cc_user_domain(domain):
    sitewide_domain = settings.HQ_ACCOUNT_ROOT
    return ("%s.%s" % (domain, sitewide_domain)).lower()


def format_username(username, domain):
    username = re.sub(r'\s+', '.', str(username or '')).lower()
    return "%s@%s" % (username, cc_user_domain(domain))


def normalize_username(username, domain=None):
    """
    DEPRECATED: use generate_mobile_username instead

    Returns a lower-case username. Checks that it is a valid e-mail
    address, or a valid "local part" of an e-mail address.

    :raises ValidationError on invalid e-mail
    """
    from django.core.validators import validate_email

    if not username:
        raise ValidationError("Invalid username: {}".format(username))

    username = str(username)
    username = re.sub(r'\s+', '.', username).lower()
    if domain:
        username = format_username(username, domain)
        validate_email(username)
    else:
        # if no domain, make sure that the username is a valid "local part" of an email address
        validate_email("%s@dimagi.com" % username)

    return username


def raw_username(username):
    """
    Strips the @domain.commcarehq.org from the username if it's there
    """
    sitewide_domain = settings.HQ_ACCOUNT_ROOT
    username = str(username or '')
    username = username.lower()
    try:
        u, d = username.split("@")
    except Exception:
        return username
    if d.endswith('.' + sitewide_domain):
        return u
    else:
        return username


@quickcache(['username'], timeout=60 * 60 * 24 * 3)
def username_to_user_id(username):
    '''
    Takes a username and returns the couch user id for that user

    :param username: The username name of a user

    :returns: The couch user id
    '''
    from corehq.apps.users.models import CouchUser

    user = CouchUser.get_by_username(username)
    if not user:
        return None

    return user._id


def user_id_to_username(user_id, use_name_if_available=False):
    from corehq.apps.users.models import CouchUser
    if not user_id:
        return None
    if isinstance(user_id, numbers.Number):
        # couch chokes on numbers so just short-circuit this
        return None
    elif user_id == DEMO_USER_ID:
        return DEMO_USER_ID
    try:
        user_object = CouchUser.get_db().get(user_id)
    except ResourceNotFound:
        return None

    if use_name_if_available and (user_object.get('first_name', '') or user_object.get('last_name', '')):
        return ' '.join([user_object.get('first_name', ''), user_object.get('last_name', '')]).strip()
    else:
        return raw_username(user_object['username']) if "username" in user_object else None


def cached_user_id_to_username(user_id):
    if not user_id:
        return None

    key = 'user_id_username_cache_{id}'.format(id=user_id)
    ret = cache.get(key)
    if ret:
        return ret
    else:
        ret = user_id_to_username(user_id)
        cache.set(key, ret)
        return ret


@quickcache(['user_id'])
def cached_user_id_to_user_display(user_id):
    return user_id_to_username(user_id, use_name_if_available=True)


def cached_owner_id_to_display(owner_id):
    from corehq.apps.users.cases import get_wrapped_owner
    from corehq.apps.users.models import CouchUser
    key = 'owner_id_to_display_cache_{id}'.format(id=owner_id)
    ret = cache.get(key)
    if ret:
        return ret
    owner = get_wrapped_owner(owner_id)
    if owner is None:
        return None
    else:
        ret = raw_username(owner.username) if isinstance(owner, CouchUser) else owner.name
        cache.set(key, ret)
        return ret


def django_user_from_couch_id(id):
    """
    From a couch id of a profile object, get the django user
    """
    # get the couch doc
    from corehq.apps.users.models import CouchUser
    couch_rep = CouchUser.get_db().get(id)
    django_id = couch_rep["django_user"]["id"]
    return User.objects.get(id=django_id)


def doc_value_wrapper(doc_cls, value_cls):
    """
    Wrap both the doc and the value
    Code copied from couchdbkit.schema.base.QueryMixin.__view

    """
    #from corehq.apps.users.models import CouchUser
    def wrapper(row):

        data = row.get('value')
        docid = row.get('id')
        doc = row.get('doc')

        data['_id'] = docid
        if 'rev' in data:
            data['_rev'] = data.pop('rev')
        value_cls._allow_dynamic_properties = True
        doc_cls._allow_dynamic_properties = True
        value_inst = value_cls.wrap(data)
        doc_inst = doc_cls.wrap(doc)
        return doc_inst, value_inst
    return wrapper


def can_add_extra_mobile_workers(request):
    from corehq.apps.users.models import CommCareUser
    num_web_users = CommCareUser.total_by_domain(request.domain)
    user_limit = request.plan.user_limit
    if user_limit == -1 or num_web_users < user_limit:
        return True
    return has_privilege(request, privileges.ALLOW_EXCESS_USERS)


def user_display_string(username, first_name='', last_name=''):
    full_name = '{} {}'.format(first_name or '', last_name or '').strip()

    result = mark_safe(html.escape(raw_username(username)))  # nosec: escaped
    if full_name:
        result = format_html('{} "{}"', result, full_name)

    return result


def user_location_data(location_ids):
    # Spec for 'commcare_location_ids' custom data field
    return ' '.join(location_ids)


def update_device_meta(user, device_id, commcare_version=None, device_app_meta=None, fcm_token=None,
                       fcm_token_timestamp=None, save=True):
    from corehq.apps.users.models import CommCareUser

    updated = False
    if device_id and isinstance(user, CommCareUser):
        if not user.is_demo_user:
            # this only updates once per day for each device
            updated = user.update_device_id_last_used(
                device_id,
                commcare_version=commcare_version,
                device_app_meta=device_app_meta,
                fcm_token=fcm_token,
                fcm_token_timestamp=fcm_token_timestamp
            )
            if save and updated:
                user.save(fire_signals=False)
    return updated


def _last_build_needs_update(last_build, build_date):
    if not (last_build and last_build.build_version_date):
        return True
    if build_date > last_build.build_version_date:
        return True
    return False


def update_latest_builds(user, app_id, date, version, build_profile_id=None):
    """
    determines whether to update the last build attributes in a user's reporting metadata
    """
    from corehq.apps.users.models import LastBuild
    last_build = filter_by_app(user.reporting_metadata.last_builds, app_id)
    changed = False
    if _last_build_needs_update(last_build, date):
        if last_build is None:
            last_build = LastBuild()
            user.reporting_metadata.last_builds.append(last_build)
        last_build.build_version = version
        last_build.app_id = app_id
        # update only when passed to avoid over writing set value
        if build_profile_id is not None:
            last_build.build_profile_id = build_profile_id
        last_build.build_version_date = date
        changed = True

    if _last_build_needs_update(user.reporting_metadata.last_build_for_user, date):
        user.reporting_metadata.last_build_for_user = last_build
        changed = True

    return changed


def filter_by_app(obj_list, app_id):
    """
    :param obj_list: list from objects with ``app_id`` property
    :returns: The first object with matching app_id
    """
    for item in obj_list:
        if item.app_id == app_id:
            return item


def update_last_sync(user, app_id, sync_date, version):
    """
    This function does not save the user.
    :return: True if user updated
    """
    from corehq.apps.users.models import LastSync
    last_sync = filter_by_app(user.reporting_metadata.last_syncs, app_id)
    if _last_sync_needs_update(last_sync, sync_date):
        if last_sync is None:
            last_sync = LastSync()
            user.reporting_metadata.last_syncs.append(last_sync)
        last_sync.sync_date = sync_date
        last_sync.build_version = version
        last_sync.app_id = app_id

        if _last_sync_needs_update(user.reporting_metadata.last_sync_for_user, sync_date):
            user.reporting_metadata.last_sync_for_user = last_sync

        return True
    return False


def _last_sync_needs_update(last_sync, sync_datetime):
    if not (last_sync and last_sync.sync_date):
        return True
    if sync_datetime > last_sync.sync_date:
        return True
    return False


def log_user_change(by_domain, for_domain, couch_user, changed_by_user, changed_via=None,
                    change_messages=None, fields_changed=None, action=None,
                    by_domain_required_for_log=True, for_domain_required_for_log=True,
                    bulk_upload_record_id=None):
    """
    Log changes done to a user.
    For a new user or a deleted user, log only specific fields.

    :param by_domain: domain where the update was initiated
    :param for_domain: domain for which the update was initiated or the domain whose operations will get
        effected by this change.
        From user's perspective,
        A commcare user is completely owned by the domain
        A web user's membership that let's it perform operations on a domain is owned by the domain.
    :param couch_user: user being changed
    :param changed_by_user: user making the change or SYSTEM_USER_ID
    :param changed_via: changed via medium i.e API/Web
    :param change_messages: Optional dict of change messages
    :param fields_changed: dict of user fields that have changed with their current value
    :param action: action on the user
    :param by_domain_required_for_log: set to False to allow domain less log for specific changes
    :param for_domain_required_for_log: set to False to allow domain less log for specific changes
    :param bulk_upload_record_id: ID of bulk upload record if changed via bulk upload
    """
    from corehq.apps.users.models import UserHistory
    from corehq.apps.users.model_log import UserModelAction

    action = action or UserModelAction.UPDATE
    fields_changed = fields_changed or {}
    change_messages = change_messages or {}

    # domains are essential to filter changes done in and by a domain
    if by_domain_required_for_log and changed_by_user != SYSTEM_USER_ID and not by_domain:
        raise ValueError("missing 'by_domain' argument'")
    if for_domain_required_for_log and not for_domain:
        raise ValueError("missing 'for_domain' argument'")

    # for an update, there should always be fields that have changed or change messages
    if action == UserModelAction.UPDATE and not fields_changed and not change_messages:
        raise ValueError("missing both 'fields_changed' and 'change_messages' argument for update.")

    if changed_by_user == SYSTEM_USER_ID:
        changed_by_id = SYSTEM_USER_ID
        changed_by_repr = SYSTEM_USER_ID
    else:
        changed_by_id = changed_by_user.get_id
        changed_by_repr = changed_by_user.raw_username
    return UserHistory.objects.create(
        by_domain=by_domain,
        for_domain=for_domain,
        user_type=couch_user.doc_type,
        user_repr=couch_user.raw_username,
        changed_by_repr=changed_by_repr,
        user_id=couch_user.get_id,
        changed_by=changed_by_id,
        changes=_get_changed_details(couch_user, action, fields_changed),
        changed_via=changed_via,
        change_messages=change_messages,
        action=action.value,
        user_upload_record_id=bulk_upload_record_id,
    )


def _get_changed_details(couch_user, action, fields_changed):
    from corehq.apps.users.model_log import UserModelAction

    if action in [UserModelAction.CREATE, UserModelAction.DELETE]:
        changed_details = couch_user.to_json()
    else:
        changed_details = fields_changed.copy()

    for prop in USER_FIELDS_TO_IGNORE_FOR_HISTORY:
        changed_details.pop(prop, None)
    return changed_details


def bulk_auto_deactivate_commcare_users(user_ids, domain):
    """
    Deactivates CommCareUsers in bulk.

    Please pre-chunk ids to a reasonable size. Also please reference the
    save() method in CommCareUser when making changes.

    :param user_ids: list of user IDs
    :param domain: name of domain user IDs belong to
    """
    from corehq.apps.users.models import UserHistory, CommCareUser
    from corehq.apps.users.model_log import UserModelAction

    last_modified = json_format_datetime(datetime.datetime.utcnow())
    user_docs_to_bulk_save = []
    for user_doc in get_docs(CommCareUser.get_db(), keys=user_ids):
        if user_doc['is_active']:
            user_doc['is_active'] = False
            user_doc['last_modified'] = last_modified
            user_docs_to_bulk_save.append(user_doc)

    # bulk save django Users
    user_query = User.objects.filter(
        username__in=[u["username"] for u in user_docs_to_bulk_save]
    )
    user_query.update(is_active=False)

    # bulk save in couch
    CommCareUser.get_db().bulk_save(user_docs_to_bulk_save)

    # bulk create all the UserHistory logs
    UserHistory.objects.bulk_create([
        UserHistory(
            by_domain=domain,
            for_domain=domain,
            user_type=CommCareUser.doc_type,
            user_repr=u['username'].split('@')[0],
            changed_by_repr=SYSTEM_USER_ID,
            user_id=u['_id'],
            changed_by=SYSTEM_USER_ID,
            changes={'is_active': False},
            changed_via=USER_CHANGE_VIA_AUTO_DEACTIVATE,
            change_messages={},
            action=UserModelAction.UPDATE.value,
            user_upload_record_id=None
        )
        for u in user_docs_to_bulk_save
    ])

    # clear caches and fire signals
    for user_doc in user_docs_to_bulk_save:
        commcare_user = CommCareUser.wrap(user_doc)
        commcare_user.clear_quickcache_for_user()
        commcare_user.fire_signals()
        # FYI we don't call the save() method individually because
        # it is ridiculously inefficient! Unfortunately, it's harder to get
        # around caches and signals in a bulk way.


def is_dimagi_email(email):
    return email.endswith('@dimagi.com')


def is_username_available(username):
    """
    Checks if the username is available to use
    :param username: expects complete/email formatted username (e.g., user@example.commcarehq.org)
    :return: boolean
    """
    from corehq.apps.users.dbaccessors import user_exists

    local_username = username
    if '@' in local_username:
        # assume email format since '@' is an invalid character for usernames
        local_username = username.split('@')[0]
    reserved_usernames = ['admin', 'demo_user']
    if local_username in reserved_usernames:
        return False

    exists = user_exists(username)
    return not exists.exists
