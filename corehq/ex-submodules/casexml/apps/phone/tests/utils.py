from xml.etree import ElementTree
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure
from casexml.apps.case.xml import V1, V2, V2_NAMESPACE
from casexml.apps.phone.models import (
    get_properly_wrapped_sync_log,
    get_sync_log_class_by_format,
    OTARestoreWebUser,
    OTARestoreCommCareUser,
)
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings, restore_cache_key
from casexml.apps.phone.tests.dbaccessors import get_all_sync_logs_docs
from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.phone.const import RESTORE_CACHE_KEY_PREFIX

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
            first_name=first_name,
            user_data={
                'something': 'arbitrary'
            }
        )
    )
    if phone_number:
        user._couch_user.add_phone_number(phone_number)
    return user


def synclog_id_from_restore_payload(restore_payload):
    element = ElementTree.fromstring(restore_payload)
    return element.findall('{%s}Sync' % SYNC_XMLNS)[0].findall('{%s}restore_id' % SYNC_XMLNS)[0].text


def synclog_from_restore_payload(restore_payload):
    return get_properly_wrapped_sync_log(synclog_id_from_restore_payload(restore_payload))


def get_exactly_one_wrapped_sync_log():
    """
    Gets exactly one properly wrapped sync log, or fails hard.
    """
    [doc] = list(get_all_sync_logs_docs())
    return get_sync_log_class_by_format(doc['log_format']).wrap(doc)


def generate_restore_payload(project, user, restore_id="", version=V1, state_hash="",
                             items=False, overwrite_cache=False,
                             force_cache=False, **kw):
    """
    Gets an XML payload suitable for OTA restore.

        user:          who the payload is for
        restore_id:    last sync token for this user
        version:       the restore API version

        returns: the xml payload of the sync operation
    """
    return get_restore_config(
        project, user, restore_id, version, state_hash, items, overwrite_cache,
        force_cache, **kw
    ).get_payload().as_string()


def get_next_sync_log(*args, **kw):
    """Perform a sync and return the new sync log

    Expects same arguments as `generate_restore_payload`
    """
    payload = generate_restore_payload(*args, **kw)
    return synclog_from_restore_payload(payload)


def get_restore_config(project, user, restore_id="", version=V1, state_hash="",
                       items=False, overwrite_cache=False, force_cache=False,
                       device_id=None, case_sync=None):
    return RestoreConfig(
        project=project,
        restore_user=user,
        case_sync=case_sync,
        params=RestoreParams(
            sync_log_id=restore_id,
            version=version,
            state_hash=state_hash,
            include_item_count=items,
            device_id=device_id,
        ),
        cache_settings=RestoreCacheSettings(
            overwrite_cache=overwrite_cache,
            force_cache=force_cache,
        )
    )


def generate_restore_response(project, user, restore_id="", version=V1, state_hash="", items=False):
    config = RestoreConfig(
        project=project,
        restore_user=user,
        params=RestoreParams(
            sync_log_id=restore_id,
            version=version,
            state_hash=state_hash,
            include_item_count=items
        )
    )
    return config.get_response()


def has_cached_payload(sync_log, version, prefix=RESTORE_CACHE_KEY_PREFIX):
    return bool(get_redis_default_cache().get(restore_cache_key(
        sync_log.domain,
        prefix,
        sync_log.user_id,
        version=version,
        sync_log_id=sync_log._id,
    )))


def call_fixture_generator(gen, restore_user, project=None, last_sync=None, app=None, device_id=''):
    """
    Convenience function for use in unit tests
    """
    from casexml.apps.phone.restore import RestoreState
    from casexml.apps.phone.restore import RestoreParams
    from corehq.apps.domain.models import Domain
    params = RestoreParams(version=V2, app=app, device_id=device_id)
    restore_state = RestoreState(
        project or Domain(name=restore_user.domain),
        restore_user,
        params,
        async=False,
        overwrite_cache=False
    )
    if last_sync:
        params.sync_log_id = last_sync._id
        restore_state._last_sync_log = last_sync
    return gen(restore_state)


class MockDevice(object):

    def __init__(self, project, user, restore_options,
            sync=False, default_case_type="case", default_owner_id=None):
        self.project = project
        self.user = user
        self.user_id = user.user_id
        self.restore_options = restore_options
        self.case_blocks = []
        self.case_factory = CaseFactory(
            case_defaults={
                'user_id': self.user_id,
                'owner_id': default_owner_id or self.user_id,
                'case_type': default_case_type,
            },
        )
        self.last_sync = None
        if sync:
            self.sync()

    def change_cases(self, cases=None, **case_kwargs):
        """Enqueue case changes to be synced

        Does not post changes to HQ. Use `post_changes()` for that,
        possibly after enqueuing changes with this method.

        :param cases: A `CaseBlock` or `CaseStructure` or a list of the
        same (all must have same type). `CaseStructure` objects will be
        converted to case XML with defaults from this device's case
        factory. `CaseBlock` objects will be posted as is (no defaults).
        :param **case_kwargs: Arguments to be passed to
        `CaseFactory.get_case_block(...)`, which implies using defaults
        from this device's case factory.
        """
        factory = self.case_factory
        if case_kwargs:
            assert cases is None, "pass one: cases or kwargs"
            self.case_blocks.append(factory.get_case_block(**case_kwargs))
            return
        if isinstance(cases, (CaseStructure, CaseBlock)):
            cases = [cases]
        elif not isinstance(cases, list):
            raise ValueError(repr(cases))
        if all(isinstance(s, CaseStructure) for s in cases):
            self.case_blocks.extend(factory.get_case_blocks(cases))
        else:
            self.case_blocks.extend(b.as_xml() for b in cases)

    def post_changes(self, *args, **kw):
        """Post enqueued changes from device to HQ

        Calls `change_cases(*args, **kw)` with any arguments (if given)
        for convenience.

        This is the first half of a full sync. It does not affect the
        latest sync log on the device or HQ and can be used when the
        result of a restore on this device is not important.
        """
        if args or kw:
            self.change_cases(*args, **kw)
        if self.case_blocks:
            # post device case changes
            token = self.last_sync.log._id
            self.case_factory.post_case_blocks(
                self.case_blocks,
                form_extras={"last_sync_token": token},
            )
            self.case_blocks = []

    def sync(self, **config):
        """Synchronize device with HQ"""
        self.post_changes()
        # restore
        for name, value in self.restore_options.items():
            config.setdefault(name, value)
        config.setdefault('version', V2)
        if self.last_sync is not None and 'restore_id' not in config:
            config['restore_id'] = self.last_sync.log._id
        restore_config = get_restore_config(self.project, self.user, **config)
        payload = restore_config.get_payload().as_string()
        self.last_sync = SyncResult(restore_config, payload)
        return self.last_sync


class SyncResult(object):

    def __init__(self, config, payload):
        self.config = config
        self.payload = payload
        self.xml = ElementTree.fromstring(payload)

    def get_log(self):
        restore_id = (self.xml
            .findall('{%s}Sync' % SYNC_XMLNS)[0]
            .findall('{%s}restore_id' % SYNC_XMLNS)[0].text)
        return get_properly_wrapped_sync_log(restore_id)

    @property
    @memoized
    def log(self):
        return self.get_log()

    @property
    @memoized
    def cases(self):
        return {case.case_id: case for case in (CaseBlock.from_xml(node)
                for node in self.xml.findall("{%s}case" % V2_NAMESPACE))}

    def has_cached_payload(self, *args, **kw):
        return has_cached_payload(self.log, *args, **kw)
