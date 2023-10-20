from xml.etree import cElementTree as ElementTree
from casexml.apps.case.xml import V1, V2
from casexml.apps.phone.models import (
    get_properly_wrapped_sync_log,
    OTARestoreWebUser,
    OTARestoreCommCareUser,
)

from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.phone.utils import get_restore_config

from corehq.apps.users.models import CommCareUser, WebUser


def create_restore_user(
        domain='restore-domain',
        username='mclovin',
        password='***',
        is_mobile_user=True,
        first_name='',
        last_name='',
        phone_number=None):

    user_cls = CommCareUser if is_mobile_user else WebUser
    restore_user_cls = OTARestoreCommCareUser if is_mobile_user else OTARestoreWebUser
    user = restore_user_cls(
        domain,
        user_cls.create(
            domain=domain,
            username=username,
            password=password,
            created_by=None,
            created_via=None,
            first_name=first_name,
            user_data={'something': 'arbitrary'},
        )
    )
    if phone_number:
        user._couch_user.add_phone_number(phone_number)
    return user


def deprecated_synclog_id_from_restore_payload(restore_payload):
    """DEPRECATED use <MockDevice>.sync().restore_id"""
    element = ElementTree.fromstring(restore_payload)
    return element.findall('{%s}Sync' % SYNC_XMLNS)[0].findall('{%s}restore_id' % SYNC_XMLNS)[0].text


def deprecated_synclog_from_restore_payload(restore_payload):
    """DEPRECATED use <MockDevice>.sync().get_log()"""
    return get_properly_wrapped_sync_log(
        deprecated_synclog_id_from_restore_payload(restore_payload))


def deprecated_generate_restore_payload(project, user, restore_id="", version=V1, state_hash="",
                             items=False, overwrite_cache=False,
                             force_cache=False, **kw):
    """
    DEPRECATED use result of <MockDevice>.sync() to inspect restore payloads
    """
    return get_restore_config(
        project, user, restore_id, version, state_hash, items, overwrite_cache,
        force_cache, **kw
    ).get_payload().as_string()


def call_fixture_generator(gen, restore_user, project=None, last_sync=None, app=None, device_id=''):
    """
    Convenience function for use in unit tests

    TODO move to MockDevice since most arguments are members of that class
    """
    from casexml.apps.phone.restore import RestoreState
    from casexml.apps.phone.restore import RestoreParams
    from corehq.apps.domain.models import Domain
    params = RestoreParams(version=V2, app=app, device_id=device_id)
    restore_state = RestoreState(
        project or Domain(name=restore_user.domain),
        restore_user,
        params,
        is_async=False,
        overwrite_cache=False
    )
    if last_sync:
        params.sync_log_id = last_sync._id
        restore_state._last_sync_log = last_sync
    return gen(restore_state)
