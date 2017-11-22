from __future__ import absolute_import
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import html, safestring

from couchdbkit.resource import ResourceNotFound
from corehq import privileges, toggles
from corehq.util.quickcache import quickcache

from django.core.cache import cache
from django_prbac.utils import has_privilege

from casexml.apps.case.const import UNOWNED_EXTENSION_OWNER_ID, ARCHIVED_CASE_OWNER_ID

# SYSTEM_USER_ID is used when submitting xml to make system-generated case updates
SYSTEM_USER_ID = 'system'
DEMO_USER_ID = 'demo_user'
JAVA_ADMIN_USERNAME = 'admin'
WEIRD_USER_IDS = [
    'commtrack-system',    # internal HQ/commtrack system forms
    DEMO_USER_ID,           # demo mode
    'demo_user_group_id',  # demo mode with case sharing enabled
    UNOWNED_EXTENSION_OWNER_ID,
    SYSTEM_USER_ID,
    ARCHIVED_CASE_OWNER_ID,
]


def cc_user_domain(domain):
    sitewide_domain = settings.HQ_ACCOUNT_ROOT 
    return ("%s.%s" % (domain, sitewide_domain)).lower()


def format_username(username, domain):
    return "%s@%s" % (username.lower(), cc_user_domain(domain))


def normalize_username(username, domain=None):
    """
    Returns a lower-case username. Checks that it is a valid e-mail
    address, or a valid "local part" of an e-mail address.

    :raises ValidationError on invalid e-mail
    """
    from django.core.validators import validate_email

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


def user_id_to_username(user_id):
    from corehq.apps.users.models import CouchUser
    if not user_id:
        return user_id
    elif user_id == DEMO_USER_ID:
        return DEMO_USER_ID
    try:
        login = CouchUser.get_db().get(user_id)
    except ResourceNotFound:
        return None
    return raw_username(login['username']) if "username" in login else None


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
    from corehq.apps.accounting.models import Subscription
    num_web_users = CommCareUser.total_by_domain(request.domain)
    user_limit = request.plan.user_limit
    if user_limit == -1 or num_web_users < user_limit:
        return True
    if not has_privilege(request, privileges.ALLOW_EXCESS_USERS):
        current_subscription = Subscription.get_active_subscription_by_domain(request.domain)
        if current_subscription is None or current_subscription.account.date_confirmed_extra_charges is None:
            return False
    return True


def user_display_string(username, first_name="", last_name=""):
    full_name = u"{} {}".format(first_name or u'', last_name or u'').strip()

    def parts():
        yield u'%s' % html.escape(raw_username(username))
        if full_name:
            yield u' "%s"' % html.escape(full_name)

    return safestring.mark_safe(''.join(parts()))


def user_location_data(location_ids):
    # Spec for 'commcare_location_ids' custom data field
    return ' '.join(location_ids)


def update_device_meta(user, device_id, commcare_version=None, device_app_meta=None, save=True):
    from corehq.apps.users.models import CommCareUser
    from custom.enikshay.user_setup import set_enikshay_device_id

    updated = False
    if device_id and isinstance(user, CommCareUser):
        if not user.is_demo_user:
            # this only updates once per day for each device
            updated = user.update_device_id_last_used(
                device_id,
                commcare_version=commcare_version,
                device_app_meta=device_app_meta,
            )
            if toggles.ENIKSHAY.enabled(user.domain):
                updated = set_enikshay_device_id(user, device_id) or updated
            if save and updated:
                user.save(fire_signals=False)
    return updated


def _last_build_needs_update(last_build, build_date):
    if not (last_build and last_build.build_version_date):
        return True
    if build_date > last_build.build_version_date:
        return True
    return False


def update_latest_builds(user, app_id, date, version):
    """
    determines whether to update the last build attributes in a user's reporting metadata
    """
    from corehq.apps.users.models import LastBuild
    last_builds = [
        build for build in user.reporting_metadata.last_builds if build.app_id == app_id
    ]
    if last_builds:
        assert len(last_builds) == 1, 'Must only have one last build per app'
        last_build = last_builds[0]
    else:
        last_build = None

    changed = False
    if _last_build_needs_update(last_build, date):
        if last_build is None:
            last_build = LastBuild()
            user.reporting_metadata.last_builds.append(last_build)
        last_build.build_version = version
        last_build.app_id = app_id
        last_build.build_version_date = date
        changed = True

    if _last_build_needs_update(user.reporting_metadata.last_build_for_user, date):
        user.reporting_metadata.last_build_for_user = last_build
        changed = True

    return changed


def filter_by_app(obj_list, app_id):
    """
    :param obj_list: list from objects with ``app_id`` property
    :returns: The object with matching app_id
    """
    last_items = list(filter(
        lambda sync: sync.app_id == app_id,
        obj_list,
    ))
    if last_items:
        assert len(last_items) == 1, 'Must only have one {} per app'.format(last_items[0].__class__)
        last_item = last_items[0]
    else:
        last_item = None
    return last_item


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
