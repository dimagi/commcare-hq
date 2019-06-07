from __future__ import absolute_import
from __future__ import unicode_literals

from couchdbkit.exceptions import ResourceNotFound
from jsonobject.exceptions import WrappingAttributeError

from corehq.apps.commtrack.const import COMMTRACK_USERNAME
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import SYSTEM_USER_ID, DEMO_USER_ID
from corehq.const import ONE_DAY
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
    elif user_id:
        try:
            user = CouchUser.get(user_id)
            if user.is_web_user():
                return WEB_USER_TYPE
            elif user.is_commcare_user():
                return MOBILE_USER_TYPE
        except (ResourceNotFound, WrappingAttributeError):
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
