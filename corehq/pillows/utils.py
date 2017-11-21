from __future__ import absolute_import
from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.apps.users.models import CouchUser, LastBuild, LastSync
from corehq.apps.users.util import SYSTEM_USER_ID, DEMO_USER_ID
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.quickcache import quickcache

SYSTEM_USER_TYPE = "system"
DEMO_USER_TYPE = "demo"
COMMCARE_SUPPLY_USER_TYPE = "supply"
WEB_USER_TYPE = "web"
MOBILE_USER_TYPE = "mobile"
UNKNOWN_USER_TYPE = "unknown"
USER_TYPES = (
    SYSTEM_USER_TYPE,
    DEMO_USER_TYPE,
    COMMCARE_SUPPLY_USER_TYPE,
    WEB_USER_TYPE,
    MOBILE_USER_TYPE,
    UNKNOWN_USER_TYPE,
)

DELETED_DOC_TYPES = {
    'CommCareCase': [
        'CommCareCase-Deleted',
    ],
    'XFormInstance': [
        'XFormInstance-Deleted',
        'XFormArchived',
        # perhaps surprisingly - 'XFormDeprecated' is not a deletion, since it has that
        # type from its creation. The new form gets saved on top of the form being deprecated
        # which should work out fine for the way this is intended to be used
    ],
}


def get_deleted_doc_types(doc_type):
    """
    Return a list of doc types that represent deletions of this type. This is useful for
    things like pillows that need to catch a deletion and do something to remove
    the data from a report/index.
    """
    return DELETED_DOC_TYPES.get(doc_type, [])


ONE_DAY = 60 * 60 * 24


@quickcache(['user_id'], timeout=ONE_DAY)
def get_user_type(user_id):
    if user_id == SYSTEM_USER_ID:
        # Every form with user_id == system also has username == system.
        # But there are some forms where username == system but the user_id is different.
        # Any chance those should be included?
        return SYSTEM_USER_TYPE
    elif user_id == DEMO_USER_ID:
        return DEMO_USER_TYPE
    elif user_id == COMMTRACK_USERNAME:
        return COMMCARE_SUPPLY_USER_TYPE
    else:
        try:
            user = CouchUser.get(user_id)
            if user.is_web_user():
                return WEB_USER_TYPE
            elif user.is_commcare_user():
                return MOBILE_USER_TYPE
        except:
            pass
    return UNKNOWN_USER_TYPE


def get_all_expected_es_indices():
    yield CASE_INDEX_INFO
    yield XFORM_INDEX_INFO
    yield REPORT_CASE_INDEX_INFO
    yield REPORT_XFORM_INDEX_INFO
    yield APP_INDEX_INFO
    yield DOMAIN_INDEX_INFO
    yield USER_INDEX_INFO
    yield GROUP_INDEX_INFO
    yield SMS_INDEX_INFO
    yield CASE_SEARCH_INDEX_INFO
    yield LEDGER_INDEX_INFO


def format_form_meta_for_es(form_metadata):
    form_metadata['appVersion'] = form_metadata['appVersion'].get('#text')
    return form_metadata


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
    last_builds = filter(
        lambda build: build.app_id == app_id,
        user.reporting_metadata.last_builds,
    )
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


def filter_by_app(data_list, app_id):
    """
    returns the last sync, submission, or build for the given app id
    :param data_list: list from user's reporting metadata (last syncs, last submissions, or last builds)
    """
    last_items = filter(
        lambda sync: sync.app_id == app_id,
        data_list,
    )
    if last_items:
        assert len(last_items) == 1, 'Must only have one {} per app'.format(last_items[0].__class__)
        last_item = last_items[0]
    else:
        last_item = None
    return last_item


def update_last_sync(app_id, sync_date, user, version):
    """
    This function does not save the user.
    :return: True if user updated
    """
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
