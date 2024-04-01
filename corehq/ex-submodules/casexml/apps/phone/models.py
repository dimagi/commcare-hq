import json
import logging
import uuid
from collections import defaultdict, namedtuple
from copy import copy
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

import architect
import six
from memoized import memoized

from casexml.apps.case import const
from casexml.apps.phone.change_publishers import publish_synclog_saved
from casexml.apps.phone.checksum import CaseStateHash, Checksum
from casexml.apps.phone.exceptions import (
    IncompatibleSyncLogType,
    MissingSyncLog,
)
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    SafeSaveDocument,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    SetProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.logging import notify_exception

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.util.global_request import get_request_domain
from corehq.util.soft_assert import soft_assert
from toposort import toposort_flatten


def _get_logger():
    # for some strange reason if you define logger the normal way it gets silenced in tests.
    # this is a hacky workaround to that.
    return logging.getLogger(__name__)


class OTARestoreUser(object):
    """
    This is the OTA restore user's interface that's used for OTA restore to properly
    find cases and generate the user XML for both a web user and mobile user.

    Note: When adding methods to this user, you'll need to ensure that it is
    functional with both a CommCareUser and WebUser.
    """
    def __init__(self, domain, couch_user, loadtest_factor=1, request_user=None):
        self.domain = domain
        self._loadtest_factor = loadtest_factor
        self._couch_user = couch_user
        self.request_user = request_user  # user making the request

    @property
    def user_id(self):
        return self._couch_user.user_id

    @property
    def loadtest_factor(self):
        """
        Gets the loadtest factor for a domain and user. Is always 1
        unless both the LOADTEST_USER privilege is available for the
        domain, and the user has a non-zero, non-null factor set.
        """
        # This method is called by `RestoreState.get_safe_loadtest_factor()`,
        # which sets guard rails by checking the user's case load.
        if domain_has_privilege(self.domain, privileges.LOADTEST_USERS):
            return self._loadtest_factor or 1
        return 1

    @property
    def full_username(self):
        return self._couch_user.username

    @property
    def username(self):
        return self._couch_user.raw_username

    @property
    def password(self):
        return self._couch_user.password

    @property
    def user_session_data(self):
        return self._couch_user.get_user_session_data(self.domain)

    @property
    def date_joined(self):
        return self._couch_user.date_joined

    @property
    @memoized
    def project(self):
        return Domain.get_by_name(self.domain)

    @property
    def request_user_id(self):
        # can be None in tests
        return self.request_user.user_id if self.request_user else None

    @property
    def locations(self):
        raise NotImplementedError()

    @property
    def sql_location(self):
        "User's primary SQLLocation"
        return self._couch_user.get_sql_location(self.domain)

    def get_role(self, domain):
        return self._couch_user.get_role(domain)

    def get_sql_locations(self, domain):
        return self._couch_user.get_sql_locations(domain)

    def get_location_ids(self, domain):
        return self._couch_user.get_location_ids(domain)

    def get_fixture_data_items(self):
        raise NotImplementedError()

    def get_commtrack_location_id(self):
        raise NotImplementedError()

    def get_owner_ids(self):
        raise NotImplementedError()

    def get_call_center_indicators(self, config):
        raise NotImplementedError()

    def get_case_sharing_groups(self):
        raise NotImplementedError()

    def get_fixture_last_modified(self):
        raise NotImplementedError()

    def get_ucr_filter_value(self, ucr_filter, ui_filter):
        return ucr_filter.get_filter_value(self._couch_user, ui_filter)

    @memoized
    def get_locations_to_sync(self):
        from corehq.apps.locations.fixtures import get_location_fixture_queryset_for_user
        return get_location_fixture_queryset_for_user(self)


class OTARestoreWebUser(OTARestoreUser):

    def __init__(self, domain, couch_user, **kwargs):
        from corehq.apps.users.models import WebUser

        assert isinstance(couch_user, WebUser)
        super(OTARestoreWebUser, self).__init__(domain, couch_user, **kwargs)

    @property
    def locations(self):
        return []

    def get_fixture_data_items(self):
        return []

    def get_commtrack_location_id(self):
        return None

    def get_owner_ids(self):
        return [self.user_id]

    def get_call_center_indicators(self, config):
        return None

    def get_case_sharing_groups(self):
        return []

    def get_fixture_last_modified(self):
        from corehq.apps.fixtures.models import UserLookupTableStatus

        return UserLookupTableStatus.DEFAULT_LAST_MODIFIED

    def get_usercase_id(self):
        return self._couch_user.get_usercase_id(self.domain)


class OTARestoreCommCareUser(OTARestoreUser):

    def __init__(self, domain, couch_user, **kwargs):
        from corehq.apps.users.models import CommCareUser

        assert isinstance(couch_user, CommCareUser)
        super(OTARestoreCommCareUser, self).__init__(domain, couch_user, **kwargs)

    @property
    def locations(self):
        return self._couch_user.locations

    def get_fixture_data_items(self):
        from corehq.apps.fixtures.models import LookupTableRow

        return LookupTableRow.objects.iter_by_user(self._couch_user)

    def get_commtrack_location_id(self):
        from corehq.apps.commtrack.util import get_commtrack_location_id

        return get_commtrack_location_id(self._couch_user, self.project)

    def get_owner_ids(self):
        return self._couch_user.get_owner_ids(self.domain)

    def get_call_center_indicators(self, config):
        from corehq.apps.callcenter.indicator_sets import CallCenterIndicators

        return CallCenterIndicators(
            self.project.name,
            self.project.default_timezone,
            self.project.call_center_config.case_type,
            self._couch_user,
            indicator_config=config
        )

    def get_case_sharing_groups(self):
        return self._couch_user.get_case_sharing_groups()

    def get_fixture_last_modified(self):
        from corehq.apps.fixtures.models import UserLookupTableType

        return self._couch_user.fixture_status(UserLookupTableType.LOCATION)

    def get_usercase_id(self):
        return self._couch_user.get_usercase_id()


class SyncLogAssertionError(AssertionError):

    def __init__(self, case_id, *args, **kwargs):
        self.case_id = case_id
        super(SyncLogAssertionError, self).__init__(*args, **kwargs)


LOG_FORMAT_SIMPLIFIED = 'simplified'
LOG_FORMAT_LIVEQUERY = 'livequery'


class UCRSyncLog(Document):
    report_uuid = StringProperty()
    datetime = DateTimeProperty()


class AbstractSyncLog(SafeSaveDocument):
    date = DateTimeProperty()
    domain = StringProperty()
    user_id = StringProperty()
    request_user_id = StringProperty()  # ID of user making request
    build_id = StringProperty()  # only works with app-aware sync
    app_id = StringProperty()  # only works with app-aware sync

    previous_log_id = StringProperty()  # previous sync log, forming a chain
    duration = IntegerProperty()  # in seconds
    log_format = StringProperty()

    # owner_ids_on_phone stores the ids the phone thinks it's the owner of.
    # This typically includes the user id,
    # as well as all groups that that user is a member of.
    owner_ids_on_phone = StringListProperty()

    # for debugging / logging
    previous_log_rev = StringProperty()  # rev of the previous log at the time of creation
    last_submitted = DateTimeProperty()  # last time a submission caused this to be modified
    rev_before_last_submitted = StringProperty()  # rev when the last submission was saved
    last_cached = DateTimeProperty()  # last time this generated a cached response
    hash_at_last_cached = StringProperty()  # the state hash of this when it was last cached

    # save state errors and hashes here
    had_state_error = BooleanProperty(default=False)
    error_date = DateTimeProperty()
    error_hash = StringProperty()
    cache_payload_paths = DictProperty()

    last_ucr_sync_times = SchemaListProperty(UCRSyncLog)

    strict = True  # for asserts

    @classmethod
    def wrap(cls, data):
        ret = super(AbstractSyncLog, cls).wrap(data)
        if hasattr(ret, 'has_assert_errors'):
            ret.strict = False
        return ret

    def save(self):
        self._synclog_sql = save_synclog_to_sql(self)

    def delete(self):
        if getattr(self, '_synclog_sql', None):
            self._synclog_sql.delete()

    def case_count(self):
        """
        How many cases are associated with this. Used in reports.
        """
        raise NotImplementedError()

    def phone_is_holding_case(self, case_id):
        raise NotImplementedError()

    def get_footprint_of_cases_on_phone(self):
        """
        Gets the phone's flat list of all case ids on the phone,
        owned or not owned but relevant.
        """
        raise NotImplementedError()

    def get_state_hash(self):
        return CaseStateHash(Checksum(self.get_footprint_of_cases_on_phone()).hexdigest())

    def update_phone_lists(self, xform, case_list):
        """
        Given a form an list of touched cases, update this sync log to reflect the updated
        state on the phone.
        """
        raise NotImplementedError()

    @classmethod
    def from_other_format(cls, other_sync_log):
        """
        Convert to an instance of a subclass from another subclass. Subclasses can
        override this to provide conversion functions.
        """
        raise IncompatibleSyncLogType('Unable to convert from {} to {}'.format(
            type(other_sync_log), cls,
        ))


def save_synclog_to_sql(synclog_json_object):
    synclog = synclog_to_sql_object(synclog_json_object)
    synclog.save()
    return synclog


def delete_synclogs(current_synclog):
    if current_synclog.user_id and current_synclog.device_id and current_synclog.app_id:
        SyncLogSQL.objects.filter(
            user_id=current_synclog.user_id,
            device_id=current_synclog.device_id,
            app_id=current_synclog.app_id,
            date__lt=current_synclog.date
        ).delete()
    elif current_synclog.user_id and current_synclog.is_formplayer:
        query = SyncLogSQL.objects.filter(
            user_id=current_synclog.user_id,
            date__lt=current_synclog.date,
        )
        device_id_filter = Q(device_id=current_synclog.device_id)
        if toggles.CLEAN_OLD_FORMPLAYER_SYNCS.enabled(
                current_synclog.user_id,
                toggles.NAMESPACE_OTHER
        ):
            # see comment in get_alt_device_id about the purpose of this short-lived code
            alt_device_id = get_alt_device_id(current_synclog.device_id)
            device_id_filter = device_id_filter | Q(device_id=alt_device_id)
        query.filter(device_id_filter).delete()
    elif current_synclog.previous_log_id:
        SyncLogSQL.objects.filter(synclog_id=current_synclog.previous_log_id).delete()


def get_alt_device_id(device_id):
    # this function and its usage can be deleted on or after March 31
    # https://github.com/dimagi/formplayer/pull/808 changed the device_id format
    # and this logic helps us purge both old and new format device_ids
    try:
        parts = device_id.split('*')
        if len(parts) == 4:
            return '*'.join([parts[0], parts[1].replace('.', '_'), parts[2], parts[3]])
        else:
            return device_id
    # this is a short lived piece of code and an optimization
    # and it's more important to us that it never causes an error
    # than it is that it works
    except Exception:
        return device_id


def synclog_to_sql_object(synclog_json_object):
    # Returns a SyncLogSQL object, a saved instance from DB or
    #   instantiated SQL object to be saved
    # synclog_json_object should be a SyncLog instance
    synclog = getattr(synclog_json_object, '_synclog_sql', None)
    if not synclog and synclog_json_object._id:
        synclog = SyncLogSQL.objects.filter(synclog_id=synclog_json_object._id).first()

    is_new_synclog_sql = not synclog_json_object._id or not synclog

    if is_new_synclog_sql:
        synclog_id = uuid.UUID(synclog_json_object._id) if synclog_json_object._id else uuid.uuid1()
        synclog_json_object._id = synclog_id.hex.lower()
        synclog = SyncLogSQL(
            domain=synclog_json_object.domain,
            user_id=synclog_json_object.user_id,
            synclog_id=synclog_id,
            date=synclog_json_object.date,
            log_format=synclog_json_object.log_format,
            build_id=synclog_json_object.build_id,
            app_id=synclog_json_object.app_id,
            device_id=synclog_json_object.device_id,
            duration=synclog_json_object.duration,
            had_state_error=synclog_json_object.had_state_error,
            error_date=synclog_json_object.error_date,
            error_hash=synclog_json_object.error_hash,
            is_formplayer=synclog_json_object.is_formplayer,
            case_count=synclog_json_object.case_count(),
            request_user_id=synclog_json_object.request_user_id,
            auth_type=synclog_json_object.auth_type,
        )
    field_mapping = [
        ('previous_log_id', 'previous_synclog_id'),
        ('last_submitted', 'last_submitted'),
    ]
    for from_field, to_field in field_mapping:
        setattr(synclog, to_field, getattr(synclog_json_object, from_field, None))
    synclog.doc = synclog_json_object.to_json()
    return synclog


@architect.install('partition', type='range', subtype='date', constraint='week', column='date')
class SyncLogSQL(models.Model):

    synclog_id = models.UUIDField(unique=True, primary_key=True, default=uuid.uuid1)
    domain = models.CharField(max_length=255, null=True, blank=True, default=None, db_index=True)
    user_id = models.CharField(max_length=255, default=None, db_index=True)
    date = models.DateTimeField(db_index=True, null=True, blank=True)
    previous_synclog_id = models.UUIDField(max_length=255, default=None, null=True, blank=True)
    doc = models.JSONField()
    log_format = models.CharField(
        max_length=10,
        choices=[
            (format, format)
            for format in [LOG_FORMAT_SIMPLIFIED, LOG_FORMAT_LIVEQUERY]
        ]
    )
    build_id = models.CharField(max_length=255, null=True, blank=True)
    app_id = models.CharField(max_length=255, null=True)
    device_id = models.CharField(max_length=255, null=True)
    duration = models.PositiveIntegerField(null=True, blank=True)
    last_submitted = models.DateTimeField(db_index=True, null=True, blank=True)
    had_state_error = models.BooleanField(default=False)
    error_date = models.DateTimeField(null=True, blank=True)
    error_hash = models.CharField(max_length=255, null=True, blank=True)

    is_formplayer = models.BooleanField(null=True, db_index=True)
    case_count = models.IntegerField(null=True)
    request_user_id = models.CharField(max_length=255, null=True)
    auth_type = models.CharField(max_length=128, null=True)

    def save(self, *args, **kwargs):
        super(SyncLogSQL, self).save(*args, **kwargs)
        try:
            publish_synclog_saved(self)
        except Exception:
            notify_exception(
                None,
                message='Could not publish change for SyncLog',
                details={'pk': self.pk}
            )


class IndexTree(DocumentSchema):
    """
    Document type representing a case dependency tree (which is flattened to a single dict)
    """
    # a flat mapping of cases to dicts of their indices. The keys in each dict are the index identifiers
    # and the values are the referenced case IDs
    indices = SchemaDictProperty()

    @property
    @memoized
    def reverse_indices(self):
        return _reverse_index_map(self.indices)

    def __repr__(self):
        return json.dumps(self.indices, indent=2)

    @staticmethod
    def get_all_dependencies(case_id, child_index_tree, extension_index_tree):
        """Takes a child and extension index tree and returns a set of all dependencies of <case_id>

        Traverse each incoming index, return each touched case.
        Traverse each outgoing index in the extension tree, return each touched case
        """
        all_cases = set()
        cases_to_check = set([case_id])
        while cases_to_check:
            case_to_check = cases_to_check.pop()
            all_cases.add(case_to_check)
            incoming_extension_indices = extension_index_tree.get_cases_that_directly_depend_on_case(
                case_to_check
            )
            incoming_child_indices = child_index_tree.get_cases_that_directly_depend_on_case(case_to_check)
            all_incoming_indices = incoming_extension_indices | incoming_child_indices
            new_outgoing_cases_to_check = set(extension_index_tree.indices.get(case_to_check, {}).values())
            new_cases_to_check = (new_outgoing_cases_to_check | all_incoming_indices) - all_cases

            cases_to_check |= new_cases_to_check

        return all_cases

    @staticmethod
    @memoized
    def get_all_outgoing_cases(case_id, child_index_tree, extension_index_tree):
        """traverse all outgoing child and extension indices"""
        all_cases = set([case_id])
        new_cases = set([case_id])
        while new_cases:
            case_to_check = new_cases.pop()
            parent_cases = set(child_index_tree.indices.get(case_to_check, {}).values())
            host_cases = set(extension_index_tree.indices.get(case_to_check, {}).values())
            new_cases = (new_cases | parent_cases | host_cases) - all_cases
            all_cases = all_cases | parent_cases | host_cases
        return all_cases

    @staticmethod
    @memoized
    def traverse_incoming_extensions(case_id, extension_index_tree, closed_cases):
        """traverse open incoming extensions"""
        all_cases = set([case_id])
        new_cases = set([case_id])
        while new_cases:
            case_to_check = new_cases.pop()
            open_incoming_extension_indices = {
                case for case in
                extension_index_tree.get_cases_that_directly_depend_on_case(case_to_check)
                if case not in closed_cases
            }
            for incoming_case in open_incoming_extension_indices:
                new_cases.add(incoming_case)
                all_cases.add(incoming_case)
        return all_cases

    def get_cases_that_directly_depend_on_case(self, case_id):
        return self.reverse_indices.get(case_id, set([]))

    def delete_index(self, from_case_id, index_name):
        prior_ids = self.indices.pop(from_case_id, {})
        prior_ids.pop(index_name, None)
        if prior_ids:
            self.indices[from_case_id] = prior_ids
        self._clear_index_caches()

    def set_index(self, from_case_id, index_name, to_case_id):
        prior_ids = self.indices.get(from_case_id, {})
        prior_ids[index_name] = to_case_id
        self.indices[from_case_id] = prior_ids
        self._clear_index_caches()

    def _clear_index_caches(self):
        try:
            # self.reverse_indices is a memoized property, so we can't just call self.reverse_indices.reset_cache
            self._reverse_indices_cache.clear()
        except AttributeError:
            pass

        self.get_all_outgoing_cases.reset_cache()
        self.traverse_incoming_extensions.reset_cache()

    def apply_updates(self, other_tree):
        """
        Apply updates from another IndexTree and return a copy with those applied.

        If an id is found in the new one, use that id's indices, otherwise, use this ones,
        (defaulting to nothing).
        """
        assert isinstance(other_tree, IndexTree)
        new = IndexTree(
            indices=copy(self.indices),
        )
        new.indices.update(other_tree.indices)
        return new


def _reverse_index_map(index_map):
    reverse_indices = defaultdict(set)
    for case_id, indices in index_map.items():
        for indexed_case_id in indices.values():
            reverse_indices[indexed_case_id].add(case_id)
    return dict(reverse_indices)


class SimplifiedSyncLog(AbstractSyncLog):
    """
    New, simplified sync log class that is used by ownership cleanliness restore.

    Just maintains a flat list of case IDs on the phone rather than the case/dependent state
    lists from the SyncLog class.
    """
    log_format = StringProperty(default=LOG_FORMAT_SIMPLIFIED)
    case_ids_on_phone = SetProperty(six.text_type)
    # this is a subset of case_ids_on_phone used to flag that a case is only around because it has dependencies
    # this allows us to purge it if possible from other actions
    dependent_case_ids_on_phone = SetProperty(six.text_type)
    owner_ids_on_phone = SetProperty(six.text_type)
    index_tree = SchemaProperty(IndexTree)  # index tree of subcases / children
    extension_index_tree = SchemaProperty(IndexTree)  # index tree of extensions
    closed_cases = SetProperty(six.text_type)
    extensions_checked = BooleanProperty(default=False)
    device_id = StringProperty()
    auth_type = StringProperty()

    _purged_cases = None

    @property
    def purged_cases(self):
        if self._purged_cases is None:
            self._purged_cases = set()
        return self._purged_cases

    @property
    def is_formplayer(self):
        return self.device_id and self.device_id.startswith("WebAppsLogin")

    def case_count(self):
        return len(self.case_ids_on_phone)

    def phone_is_holding_case(self, case_id):
        """
        Whether the phone currently has a case, according to this sync log
        """
        return case_id in self.case_ids_on_phone

    def get_footprint_of_cases_on_phone(self):
        return list(self.case_ids_on_phone)

    @property
    def primary_case_ids(self):
        return self.case_ids_on_phone - self.dependent_case_ids_on_phone

    def purge(self, case_id, xform_id=None):
        """
        This happens in 3 phases, and recursively tries to purge outgoing indices of purged cases.
        Definitions:
        -----------
        A case is *relevant* if:
        - it is open and owned or,
        - it has a relevant child or,
        - it has a relevant extension or,
        - it is the extension of a relevant case.

        A case is *available* if:
        - it is open and not an extension case or,
        - it is open and is the extension of an available case.

        A case is *live* if:
        - it is owned and available or,
        - it has a live child or,
        - it has a live extension or,
        - it is the extension of a live case.

        Algorithm:
        ----------
        1. Mark *relevant* cases
            Mark all open cases owned by the user relevant. Traversing all outgoing child
            and extension indexes, as well as all incoming extension indexes, mark all
            touched cases relevant.

        2. Mark *available* cases
            Mark all relevant cases that are open and have no outgoing extension indexes
            as available. Traverse incoming extension indexes which don't lead to closed
            cases, mark all touched cases as available.

        3. Mark *live* cases
            Mark all relevant, owned, available cases as live. Traverse incoming
            extension indexes which don't lead to closed cases, mark all touched
            cases as live.
        """
        _get_logger().debug("purging: {}".format(case_id))
        self.dependent_case_ids_on_phone.add(case_id)
        relevant = self._get_relevant_cases(case_id)
        available = self._get_available_cases(relevant)
        live = self._get_live_cases(available)
        to_remove = (relevant - self.purged_cases) - live
        self._remove_cases_purge_indices(to_remove, case_id, xform_id)

    def _get_relevant_cases(self, case_id):
        """
        Mark all open cases owned by the user relevant. Traversing all outgoing child
        and extension indexes, as well as all incoming extension indexes,
        mark all touched cases relevant.
        """
        relevant = IndexTree.get_all_dependencies(
            case_id,
            child_index_tree=self.index_tree,
            extension_index_tree=self.extension_index_tree,
        )
        _get_logger().debug("Relevant cases of {}: {}".format(case_id, relevant))
        return relevant

    def _get_available_cases(self, relevant):
        """
        Mark all relevant cases that are open and have no outgoing extension indexes
        as available. Traverse incoming extension indexes which don't lead to closed
        cases, mark all touched cases as available
        """
        incoming_extensions = self.extension_index_tree.reverse_indices
        available = {case for case in relevant
                     if case not in self.closed_cases
                     and (not self.extension_index_tree.indices.get(case) or self.index_tree.indices.get(case))}
        new_available = set() | available
        while new_available:
            case_to_check = new_available.pop()
            for incoming_extension in incoming_extensions.get(case_to_check, []):
                closed = incoming_extension in self.closed_cases
                purged = incoming_extension in self.purged_cases
                if not closed and not purged:
                    new_available.add(incoming_extension)
            available = available | new_available
        _get_logger().debug("Available cases: {}".format(available))

        return available

    def _get_live_cases(self, available):
        """
        Mark all relevant, owned, available cases as live. Traverse incoming
        extension indexes which don't lead to closed cases, mark all touched
        cases as available.
        """
        primary_case_ids = self.primary_case_ids
        live = available & primary_case_ids
        new_live = set() | live
        checked = set()
        while new_live:
            case_to_check = new_live.pop()
            checked.add(case_to_check)
            new_live = new_live | IndexTree.get_all_outgoing_cases(
                case_to_check,
                self.index_tree,
                self.extension_index_tree
            ) - self.purged_cases
            new_live = new_live | IndexTree.traverse_incoming_extensions(
                case_to_check,
                self.extension_index_tree,
                frozenset(self.closed_cases),
            ) - self.purged_cases
            new_live = new_live - checked
            live = live | new_live

        _get_logger().debug("live cases: {}".format(live))

        return live

    def _remove_cases_purge_indices(self, all_to_remove, checked_case_id, xform_id):
        """Remove all cases marked for removal. Traverse child cases and try to purge those too."""

        _get_logger().debug("cases to to_remove: {}".format(all_to_remove))
        for to_remove in all_to_remove:
            indices = self.index_tree.indices.get(to_remove, {})
            self._remove_case(to_remove, all_to_remove, checked_case_id, xform_id)
            for referenced_case in indices.values():
                is_dependent_case = referenced_case in self.dependent_case_ids_on_phone
                already_primed_for_removal = referenced_case in all_to_remove
                if is_dependent_case and not already_primed_for_removal and referenced_case != checked_case_id:
                    self.purge(referenced_case, xform_id)

    def _remove_case(self, to_remove, all_to_remove, checked_case_id, xform_id):
        """Removes case from index trees, case_ids_on_phone and dependent_case_ids_on_phone if pertinent"""
        _get_logger().debug('removing: {}'.format(to_remove))

        deleted_indices = self.index_tree.indices.pop(to_remove, {})
        deleted_indices.update(self.extension_index_tree.indices.pop(to_remove, {}))

        try:
            self.case_ids_on_phone.remove(to_remove)
        except KeyError:
            should_fail_softly = not xform_id or _domain_has_legacy_toggle_set()
            if should_fail_softly:
                pass
            else:
                # this is only a soft assert for now because of http://manage.dimagi.com/default.asp?181443
                # we should convert back to a real Exception when we stop getting any of these
                _assert = soft_assert(notify_admins=True, exponential_backoff=False)
                _assert(False, 'case already remove from synclog', {
                    'case_id': to_remove,
                    'synclog_id': self._id,
                    'form_id': xform_id
                })
        else:
            self.purged_cases.add(to_remove)

        if to_remove in self.dependent_case_ids_on_phone:
            self.dependent_case_ids_on_phone.remove(to_remove)

    def _add_primary_case(self, case_id):
        self.case_ids_on_phone.add(case_id)
        if case_id in self.dependent_case_ids_on_phone:
            self.dependent_case_ids_on_phone.remove(case_id)

    def _add_index(self, index, case_update):
        _get_logger().debug('adding index {} --<{}>--> {} ({}).'.format(
            index.case_id, index.relationship, index.referenced_id, index.identifier))
        if index.relationship == const.CASE_INDEX_EXTENSION:
            self._add_extension_index(index, case_update)
        else:
            self._add_child_index(index)

    def _add_extension_index(self, index, case_update):
        assert index.relationship == const.CASE_INDEX_EXTENSION
        self.extension_index_tree.set_index(index.case_id, index.identifier, index.referenced_id)

        case_child_indices = [idx for idx in case_update.indices_to_add
                              if idx.relationship == const.CASE_INDEX_CHILD
                              and idx.referenced_id == index.referenced_id]
        if not case_child_indices and not case_update.is_live:
            # this case doesn't also have child indices, and it is not owned, so it is dependent
            self.dependent_case_ids_on_phone.add(index.case_id)

    def _add_child_index(self, index):
        assert index.relationship == const.CASE_INDEX_CHILD
        self.index_tree.set_index(index.case_id, index.identifier, index.referenced_id)

    def _delete_index(self, index):
        self.index_tree.delete_index(index.case_id, index.identifier)
        self.extension_index_tree.delete_index(index.case_id, index.identifier)

    def update_phone_lists(self, xform, case_list):
        # HELPME
        #
        # This method has been flagged for refactoring due to its complexity and
        # frequency of touches in changesets
        #
        # If you are writing code that touches this method, your changeset
        # should leave the method better than you found it.
        #
        # Please remove this flag when this method no longer triggers an 'E' or 'F'
        # classification from the radon code static analysis

        made_changes = False
        _get_logger().debug('updating sync log for {}'.format(self.user_id))
        _get_logger().debug('case ids before update: {}'.format(', '.join(self.case_ids_on_phone)))
        _get_logger().debug('dependent case ids before update: {}'.format(
            ', '.join(self.dependent_case_ids_on_phone)))
        _get_logger().debug('index tree before update: {}'.format(self.index_tree))
        _get_logger().debug('extension index tree before update: {}'.format(self.extension_index_tree))

        # this is a variable used via closures in the function below
        owner_id_map = {}

        def get_latest_owner_id(case_id, action=None):
            # "latest" just means as this forms actions are played through
            if action is not None:
                owner_id_from_action = action.updated_known_properties.get("owner_id")
                if owner_id_from_action is not None:
                    owner_id_map[case_id] = owner_id_from_action
            return owner_id_map.get(case_id, None)

        all_updates = {}
        for case in case_list:
            if case.case_id not in all_updates:
                _get_logger().debug('initializing update for case {}'.format(case.case_id))
                all_updates[case.case_id] = CaseUpdate(case_id=case.case_id,
                                                       owner_ids_on_phone=self.owner_ids_on_phone)

            case_update = all_updates[case.case_id]
            case_update.was_live_previously = case.case_id in self.primary_case_ids
            actions = case.get_actions_for_form(xform)
            for action in actions:
                _get_logger().debug('{}: {}'.format(case.case_id, action.action_type))
                owner_id = get_latest_owner_id(case.case_id, action)
                if owner_id is not None:
                    case_update.final_owner_id = owner_id
                if action.action_type == const.CASE_ACTION_INDEX:
                    for index in action.indices:
                        if index.referenced_id:
                            case_update.indices_to_add.append(
                                ShortIndex(case.case_id, index.identifier, index.referenced_id, index.relationship)
                            )
                        else:
                            case_update.indices_to_delete.append(
                                ShortIndex(case.case_id, index.identifier, None, None)
                            )
                elif action.action_type == const.CASE_ACTION_CLOSE:
                    case_update.is_closed = True

        non_live_updates = []
        for case in case_list:
            case_update = all_updates[case.case_id]
            if case_update.is_live:
                _get_logger().debug('case {} is live.'.format(case_update.case_id))
                if case.case_id not in self.case_ids_on_phone:
                    self._add_primary_case(case.case_id)
                    made_changes = True
                elif case.case_id in self.dependent_case_ids_on_phone:
                    self.dependent_case_ids_on_phone.remove(case.case_id)
                    made_changes = True

                for index in case_update.indices_to_add:
                    self._add_index(index, case_update)
                    made_changes = True
                for index in case_update.indices_to_delete:
                    self._delete_index(index)
                    made_changes = True
            else:
                # process the non-live updates after all live are already processed
                non_live_updates.append(case_update)
                # populate the closed cases list before processing non-live updates
                if case_update.is_closed:
                    self.closed_cases.add(case_update.case_id)

        # generate list of case IDs ordered topologically by case indices
        tree = defaultdict(set)
        for update in non_live_updates:
            tree[update.case_id]  # prime for case
            for index in update.indices_to_add:
                tree[index.referenced_id].add(update.case_id)
        ordered_case_ids = toposort_flatten(tree)

        non_live_updates_by_case_id = defaultdict(list)
        for update in non_live_updates:
            non_live_updates_by_case_id[update.case_id].append(update)

        for case_id in ordered_case_ids:
            if case_id not in non_live_updates_by_case_id:
                continue
            _get_logger().debug('case {} is NOT live.'.format(case_id))
            is_dependent = (
                self.index_tree.get_cases_that_directly_depend_on_case(case_id)
                or self.extension_index_tree.get_cases_that_directly_depend_on_case(case_id)
            )
            if is_dependent:
                _get_logger().debug('adding dependent case %s', case_id)
                self.case_ids_on_phone.add(case_id)
                self.dependent_case_ids_on_phone.add(case_id)

                for update in non_live_updates_by_case_id[case_id]:
                    for index in update.indices_to_add:
                        self._add_index(index, update)

                made_changes = True

            for update in non_live_updates_by_case_id[case_id]:
                if update.has_extension_indices_to_add():
                    # non-live cases with extension indices should be added and processed
                    self.case_ids_on_phone.add(update.case_id)
                    for index in update.indices_to_add:
                        self._add_index(index, update)
                    made_changes = True

        _get_logger().debug('case ids mid update: {}'.format(', '.join(self.case_ids_on_phone)))
        _get_logger().debug('dependent case ids mid update: {}'.format(
            ', '.join(self.dependent_case_ids_on_phone)))
        _get_logger().debug('index tree mid update: {}'.format(self.index_tree))
        _get_logger().debug('extension index tree mid update: {}'.format(self.extension_index_tree))

        for update in non_live_updates:
            if update.case_id in self.case_ids_on_phone:
                # try purging the case
                self.purge(update.case_id, xform_id=xform.form_id)
                if update.case_id in self.case_ids_on_phone:
                    # if unsuccessful, process the rest of the update
                    for index in update.indices_to_add:
                        self._add_index(index, update)
                    for index in update.indices_to_delete:
                        self._delete_index(index)
                made_changes = True

        _get_logger().debug('case ids after update: {}'.format(', '.join(self.case_ids_on_phone)))
        _get_logger().debug('dependent case ids after update: {}'.format(
            ', '.join(self.dependent_case_ids_on_phone)))
        _get_logger().debug('index tree after update: {}'.format(self.index_tree))
        _get_logger().debug('extension index tree after update: {}'.format(self.extension_index_tree))
        if made_changes or not self.last_submitted:
            _get_logger().debug('made changes')
            self.last_submitted = datetime.utcnow()
            self.rev_before_last_submitted = self._rev
        return made_changes


class CaseUpdate:

    def __init__(self, case_id, owner_ids_on_phone):
        self.case_id = case_id
        self.owner_ids_on_phone = owner_ids_on_phone
        self.was_live_previously = True
        self.final_owner_id = None
        self.is_closed = None
        self.indices_to_add = []
        self.indices_to_delete = []

    @property
    def extension_indices_to_add(self):
        return [index for index in self.indices_to_add
                if index.relationship == const.CASE_INDEX_EXTENSION]

    def has_extension_indices_to_add(self):
        return len(self.extension_indices_to_add) > 0

    @property
    def is_live(self):
        """
        Returns whether an update is live for a specific set of
        owner_ids.
        """
        if self.is_closed:
            return False
        elif self.final_owner_id is None:
            # we likely didn't touch owner_id so just default to
            # whatever it was previously
            return self.was_live_previously
        else:
            return self.final_owner_id in self.owner_ids_on_phone


ShortIndex = namedtuple(
    'ShortIndex',
    ['case_id', 'identifier', 'referenced_id', 'relationship'],
)


def _domain_has_legacy_toggle_set():
    # old versions of commcare (< 2.10ish) didn't purge on form completion
    # so can still modify cases that should no longer be on the phone.
    domain = get_request_domain()
    return toggles.LEGACY_SYNC_SUPPORT.enabled(domain) if domain else False


def get_properly_wrapped_sync_log(doc_id):
    """
    Looks up and wraps a sync log, using the class based on the 'log_format' attribute.
    Defaults to the existing legacy SyncLog class.

    Raises MissingSyncLog if doc_id is not found
    """
    try:
        synclog = SyncLogSQL.objects.filter(synclog_id=doc_id).first()
        if synclog:
            return properly_wrap_sync_log(synclog.doc, synclog)
    except ValidationError:
        # this occurs if doc_id is not a valid UUID
        pass
    raise MissingSyncLog("A SyncLogSQL object with this synclog_id ({})is not found".format(
        doc_id))


def properly_wrap_sync_log(doc, synclog_sql=None):
    synclog = SimplifiedSyncLog.wrap(doc)
    if synclog_sql:
        synclog._synclog_sql = synclog_sql
    return synclog
