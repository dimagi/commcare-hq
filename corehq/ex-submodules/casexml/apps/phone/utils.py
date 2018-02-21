from __future__ import absolute_import

import re
import weakref
from uuid import uuid4
from xml.etree import cElementTree as ElementTree
from collections import defaultdict

from couchdbkit.exceptions import BulkSaveError

from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure
from casexml.apps.case.xml import V1, V2, V2_NAMESPACE
from casexml.apps.phone.exceptions import CouldNotPruneSyncLogs
from casexml.apps.phone.models import get_properly_wrapped_sync_log
from casexml.apps.phone.restore_caching import RestorePayloadPathCache
from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from casexml.apps.stock.mock import Balance
from dimagi.utils.decorators.memoized import memoized
from six.moves import range


def delete_sync_logs(before_date, limit=1000, num_tries=10):
    # Todo: convert to SQL including get_synclog_ids_before_date
    from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclog_ids_before_date
    from casexml.apps.phone.models import SyncLog
    from dimagi.utils.couch.database import iter_bulk_delete_with_doc_type_verification

    for i in range(num_tries):
        try:
            sync_log_ids = get_synclog_ids_before_date(before_date, limit)
            return iter_bulk_delete_with_doc_type_verification(
                SyncLog.get_db(), sync_log_ids, 'SyncLog', chunksize=25)
        except BulkSaveError:
            pass

    raise CouldNotPruneSyncLogs()


ITEMS_COMMENT_PREFIX = b'<!--items='
ITESM_COMMENT_REGEX = re.compile(br'(<!--items=(\d+)-->)')


def get_cached_items_with_count(cached_bytes):
    """Get the number of items encoded in cached XML elements byte string

    The string, if it contains an item count, should be prefixed with
    b'<!--items=' followed by one or more numeric digits (0-9), then
    b'-->', and finally the cached XML elements.

    Example: b'<!--items=42--><fixture>...</fixture>'

    If the string does not start with b'<!--items=' then it is assumed
    to contain only XML elements.

    :returns: Two-tuple: (xml_elements_bytes, num_items)
    """
    match = ITESM_COMMENT_REGEX.match(cached_bytes)
    if match:
        offset = len(match.group(1))
        num_items = int(match.group(2))
        return cached_bytes[offset:], num_items
    # TODO parse and count elements in cached bytes?
    return cached_bytes, 1


def get_restore_config(project, user, restore_id="", version=V1, state_hash="",
                       items=False, overwrite_cache=False, force_cache=False,
                       device_id=None, case_sync=None):
    from casexml.apps.phone.restore import (
        RestoreCacheSettings, RestoreConfig, RestoreParams)

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


class MockDevice(object):

    def __init__(self, project, user, restore_options=None,
                 sync=False, default_case_type="case", default_owner_id=None):
        self.id = uuid4().hex
        self.project = project
        self.user = user
        self.user_id = user.user_id
        self.restore_options = restore_options or {}
        self.case_blocks = []
        self.case_factory = CaseFactory(
            self.project.name,
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
            if cases is not None:
                raise ValueError("pass one: cases or kwargs")
            if "case_id" not in case_kwargs:
                if not case_kwargs.get('create'):
                    raise ValueError("case_id is required for update")
                case_kwargs["case_id"] = uuid4().hex
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
        latest sync log on the device and can be used when the result of
        a restore on this device is not important.
        """
        if args or kw:
            self.change_cases(*args, **kw)
        if self.case_blocks:
            # post device case changes
            token = self.last_sync.restore_id if self.last_sync else None
            form = self.case_factory.post_case_blocks(
                self.case_blocks,
                device_id=self.id,
                form_extras={"last_sync_token": token},
                user_id=self.user_id,
            )[0]
            self.case_blocks = []
            return form

    def get_restore_config(self, **options):
        for name, value in self.restore_options.items():
            options.setdefault(name, value)
        if "device_id" in options:
            raise ValueError("illegal parameter: device_id")
        options["device_id"] = self.id
        options.setdefault('version', V2)
        if self.last_sync is not None and 'restore_id' not in options:
            options['restore_id'] = self.last_sync.restore_id
        return get_restore_config(self.project, self.user, **options)

    def sync(self, **config):
        """Synchronize device with HQ"""
        form = self.post_changes()
        # restore
        restore_config = self.get_restore_config(**config)
        payload = restore_config.get_payload().as_string()
        self.last_sync = SyncResult(self, restore_config, payload, form)
        return self.last_sync

    def restore(self, **config):
        """Run an initial sync to the device"""
        self.last_sync = None
        return self.sync(**config)


class SyncResult(object):

    def __init__(self, device, config, payload, form):
        self.device = device
        self.config = config
        self.payload = payload
        self.form = form
        self.xml = ElementTree.fromstring(payload)

    @property
    def device(self):
        return self._device()

    @device.setter
    def device(self, value):
        self._device = weakref.ref(value)

    @property
    @memoized
    def restore_id(self):
        return (self.xml
                .findall('{%s}Sync' % SYNC_XMLNS)[0]
                .findall('{%s}restore_id' % SYNC_XMLNS)[0].text)

    def get_log(self):
        """Get the latest sync log from the database

        Unlike the `log` property, this method does not cache its
        result. A sync log is updated when new cases are processed as
        part of a form submission referencing the sync log. Therefore
        a sync log returned by this method and the one returned by the
        `log` property may reference different cases. See
        `casexml.apps.case.xform.process_cases_with_casedb` and
        `casexml.apps.case.util.update_sync_log_with_checks`.
        """
        return get_properly_wrapped_sync_log(self.restore_id)

    @property
    @memoized
    def log(self):
        """Sync log for this sync result

        NOTE the value returned here is cached, so it may not reflect
        the latest state of the sync log in the database. Use
        `get_log()` for that.
        """
        return self.get_log()

    @property
    @memoized
    def cases(self):
        """Dict of cases, keyed by case ID, from the sync body"""
        return {case.case_id: case for case in (CaseBlock.from_xml(node)
                for node in self.xml.findall("{%s}case" % V2_NAMESPACE))}

    @property
    @memoized
    def ledgers(self):
        """Dict of ledgers, keyed by entity ID, from the sync body"""
        ledgers = defaultdict(list)
        balance_nodes = self.xml.findall("{%s}balance" % COMMTRACK_REPORT_XMLNS)
        for balance_node in balance_nodes:
            balance_obj = Balance.from_xml(balance_node)
            ledgers[balance_obj.entity_id].append(balance_obj)
        return dict(ledgers)

    def has_cached_payload(self, version):
        """Check if a cached payload exists for this sync result"""
        return bool(RestorePayloadPathCache(
            domain=self.config.domain,
            user_id=self.config.restore_user.user_id,
            sync_log_id=self.restore_id,
            device_id=self.device.id,
        ).get_value())
