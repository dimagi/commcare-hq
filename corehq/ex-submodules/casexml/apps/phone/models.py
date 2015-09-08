from collections import defaultdict, namedtuple
from copy import copy
from datetime import datetime
import json
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from casexml.apps.phone.exceptions import IncompatibleSyncLogType
from corehq.toggles import LEGACY_SYNC_SUPPORT
from corehq.util.global_request import get_request
from corehq.util.soft_assert import soft_assert
from dimagi.ext.couchdbkit import *
from django.db import models
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch import LooselyEqualDocumentSchema
from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex, IndexHoldingMixIn
from casexml.apps.phone.checksum import Checksum, CaseStateHash
import logging

logger = logging.getLogger('phone.models')


class User(object):
    """
    This is a basic user model that's used for OTA restore to properly
    find cases and generate the user XML.
    """
    # todo: this model is now useless since casexml and HQ are no longer separate repos.
    # we should remove this abstraction layer and switch all the restore code to just
    # work off CouchUser objects

    def __init__(self, user_id, username, password, date_joined, first_name=None,
                 last_name=None, phone_number=None, user_data=None,
                 additional_owner_ids=None, domain=None, loadtest_factor=1):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.phone_number = phone_number
        self.password = password
        self.date_joined = date_joined
        self.user_data = user_data or {}
        self.additional_owner_ids = additional_owner_ids or []
        self.domain = domain
        self.loadtest_factor = loadtest_factor

    @property
    def user_session_data(self):
        # todo: this is redundant with the implementation in CouchUser.
        # this will go away when the two are reconciled
        from corehq.apps.custom_data_fields.models import SYSTEM_PREFIX
        session_data = copy(self.user_data)
        session_data.update({
            '{}_first_name'.format(SYSTEM_PREFIX): self.first_name,
            '{}_last_name'.format(SYSTEM_PREFIX): self.last_name,
            '{}_phone_number'.format(SYSTEM_PREFIX): self.phone_number,
        })
        return session_data

    def get_owner_ids(self):
        ret = [self.user_id]
        ret.extend(self.additional_owner_ids)
        return list(set(ret))

    @classmethod
    def from_django_user(cls, django_user):
        return cls(user_id=str(django_user.pk), username=django_user.username,
                   password=django_user.password, date_joined=django_user.date_joined,
                   user_data={})


class CaseState(LooselyEqualDocumentSchema, IndexHoldingMixIn):
    """
    Represents the state of a case on a phone.
    """

    case_id = StringProperty()
    type = StringProperty()
    indices = SchemaListProperty(CommCareCaseIndex)

    @classmethod
    def from_case(cls, case):
        if isinstance(case, dict):
            return cls.wrap({
                'case_id': case['_id'],
                'type': case['type'],
                'indices': case['indices'],
            })

        return cls(
            case_id=case.get_id,
            type=case.type,
            indices=case.indices,
        )

    def __repr__(self):
        return "case state: %s (%s)" % (self.case_id, self.indices)


class SyncLogAssertionError(AssertionError):

    def __init__(self, case_id, *args, **kwargs):
        self.case_id = case_id
        super(SyncLogAssertionError, self).__init__(*args, **kwargs)


LOG_FORMAT_LEGACY = 'legacy'
LOG_FORMAT_SIMPLIFIED = 'simplified'


class AbstractSyncLog(SafeSaveDocument, UnicodeMixIn):
    date = DateTimeProperty()
    # domain = StringProperty()
    user_id = StringProperty()
    previous_log_id = StringProperty()  # previous sync log, forming a chain
    duration = IntegerProperty()        # in seconds
    log_format = StringProperty()

    # owner_ids_on_phone stores the ids the phone thinks it's the owner of.
    # This typically includes the user id,
    # as well as all groups that that user is a member of.
    owner_ids_on_phone = StringListProperty()

    # for debugging / logging
    last_submitted = DateTimeProperty()  # last time a submission caused this to be modified
    last_cached = DateTimeProperty()  # last time this generated a cached response
    hash_at_last_cached = StringProperty()  # the state hash of this when it was last cached

    # save state errors and hashes here
    had_state_error = BooleanProperty(default=False)
    error_date = DateTimeProperty()
    error_hash = StringProperty()

    strict = True  # for asserts

    def _assert(self, conditional, msg="", case_id=None):
        if not conditional:
            if self.strict:
                raise SyncLogAssertionError(case_id, msg)
            else:
                logging.warn("assertion failed: %s" % msg)
                self.has_assert_errors = True

    @classmethod
    def wrap(cls, data):
        ret = super(AbstractSyncLog, cls).wrap(data)
        if hasattr(ret, 'has_assert_errors'):
            ret.strict = False
        return ret

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

    def get_payload_attachment_name(self, version):
        return 'restore_payload_{version}.xml'.format(version=version)

    def has_cached_payload(self, version):
        return self.get_payload_attachment_name(version) in self._doc.get('_attachments', {})

    def get_cached_payload(self, version, stream=False):
        try:
            return self.fetch_attachment(self.get_payload_attachment_name(version), stream=stream)
        except ResourceNotFound:
            return None

    def set_cached_payload(self, payload, version):
        self.put_attachment(payload, name=self.get_payload_attachment_name(version),
                            content_type='text/xml')

    def invalidate_cached_payloads(self):
        for name in copy(self._doc.get('_attachments', {})):
            self.delete_attachment(name)

    @classmethod
    def from_other_format(cls, other_sync_log):
        """
        Convert to an instance of a subclass from another subclass. Subclasses can
        override this to provide conversion functions.
        """
        raise IncompatibleSyncLogType('Unable to convert from {} to {}'.format(
            type(other_sync_log), cls,
        ))

    # anything prefixed with 'tests_only' is only used in tests
    def tests_only_get_cases_on_phone(self):
        raise NotImplementedError()

    def test_only_clear_cases_on_phone(self):
        raise NotImplementedError()

    def test_only_get_dependent_cases_on_phone(self):
        raise NotImplementedError()


class SyncLog(AbstractSyncLog):
    """
    A log of a single sync operation.
    """
    log_format = StringProperty(default=LOG_FORMAT_LEGACY)
    last_seq = StringProperty()         # the last_seq of couch during this sync

    # we need to store a mapping of cases to indices for generating the footprint
    # cases_on_phone represents the state of all cases the server
    # thinks the phone has on it and cares about.
    cases_on_phone = SchemaListProperty(CaseState)

    # dependant_cases_on_phone represents the possible list of cases
    # also on the phone because they are referenced by a real case's index
    # (or a dependent case's index).
    # This list is not necessarily a perfect reflection
    # of what's on the phone, but is guaranteed to be after pruning
    dependent_cases_on_phone = SchemaListProperty(CaseState)

    @classmethod
    def wrap(cls, data):
        # last_seq used to be int, but is now string for cloudant compatibility
        if isinstance(data.get('last_seq'), (int, long)):
            data['last_seq'] = unicode(data['last_seq'])
        return super(SyncLog, cls).wrap(data)

    @classmethod
    def last_for_user(cls, user_id):
        from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_last_synclog_for_user
        return get_last_synclog_for_user(user_id)

    def case_count(self):
        return len(self.cases_on_phone)

    def get_previous_log(self):
        """
        Get the previous sync log, if there was one.  Otherwise returns nothing.
        """
        if not hasattr(self, "_previous_log_ref"):
            self._previous_log_ref = SyncLog.get(self.previous_log_id) if self.previous_log_id else None
        return self._previous_log_ref

    def phone_has_case(self, case_id):
        """
        Whether the phone currently has a case, according to this sync log
        """
        return self.get_case_state(case_id) is not None

    def get_case_state(self, case_id):
        """
        Get the case state object associated with an id, or None if no such
        object is found
        """
        filtered_list = self._case_state_map()[case_id]
        if filtered_list:
            self._assert(len(filtered_list) == 1,
                         "Should be exactly 0 or 1 cases on phone but were %s for %s" %
                         (len(filtered_list), case_id))
            return CaseState.wrap(filtered_list[0])
        return None

    def phone_has_dependent_case(self, case_id):
        """
        Whether the phone currently has a dependent case, according to this sync log
        """
        return self.get_dependent_case_state(case_id) is not None

    def get_dependent_case_state(self, case_id):
        """
        Get the dependent case state object associated with an id, or None if no such
        object is found
        """
        filtered_list = self._dependent_case_state_map()[case_id]
        if filtered_list:
            self._assert(len(filtered_list) == 1,
                         "Should be exactly 0 or 1 dependent cases on phone but were %s for %s" %
                         (len(filtered_list), case_id))
            return CaseState.wrap(filtered_list[0])
        return None

    @memoized
    def _dependent_case_state_map(self):
        return self._build_state_map('dependent_cases_on_phone')

    @memoized
    def _case_state_map(self):
        return self._build_state_map('cases_on_phone')

    def _build_state_map(self, list_name):
        state_map = defaultdict(list)
        # referencing the property via self._doc is because we don't want to needlessly call wrap
        # (which couchdbkit does not make any effort to cache on repeated calls)
        # deterministically this change shaved off 10 seconds from an ota restore
        # of about 300 cases.
        for case in self._doc[list_name]:
            state_map[case['case_id']].append(case)

        return state_map

    def _get_case_state_from_anywhere(self, case_id):
        return self.get_case_state(case_id) or self.get_dependent_case_state(case_id)

    def archive_case(self, case_id):
        state = self.get_case_state(case_id)
        if state:
            self.cases_on_phone.remove(state)
            self._case_state_map.reset_cache(self)
            all_indices = [i for case_state in self.cases_on_phone + self.dependent_cases_on_phone
                           for i in case_state.indices]
            if any([i.referenced_id == case_id for i in all_indices]):
                self.dependent_cases_on_phone.append(state)
                self._dependent_case_state_map.reset_cache(self)
            return state
        else:
            state = self.get_dependent_case_state(case_id)
            if state:
                all_indices = [i for case_state in self.cases_on_phone + self.dependent_cases_on_phone
                               for i in case_state.indices]
                if not any([i.referenced_id == case_id for i in all_indices]):
                    self.dependent_cases_on_phone.remove(state)
                    self._dependent_case_state_map.reset_cache(self)
                    return state

    def _phone_owns(self, action):
        # whether the phone thinks it owns an action block.
        # the only way this can't be true is if the block assigns to an
        # owner id that's not associated with the user on the phone
        owner = action.updated_known_properties.get("owner_id")
        if owner:
            return owner in self.owner_ids_on_phone
        return True

    def update_phone_lists(self, xform, case_list):
        # for all the cases update the relevant lists in the sync log
        # so that we can build a historical record of what's associated
        # with the phone
        removed_states = {}
        new_indices = set()
        for case in case_list:
            actions = case.get_actions_for_form(xform.get_id)
            for action in actions:
                if action.action_type == const.CASE_ACTION_CREATE:
                    self._assert(not self.phone_has_case(case._id),
                                 'phone has case being created: %s' % case._id)
                    starter_state = CaseState(case_id=case.get_id, indices=[])
                    if self._phone_owns(action):
                        self.cases_on_phone.append(starter_state)
                        self._case_state_map.reset_cache(self)
                    else:
                        removed_states[case._id] = starter_state
                elif action.action_type == const.CASE_ACTION_UPDATE:
                    self._assert(
                        self.phone_is_holding_case(case._id),
                        "phone doesn't have case being updated: %s" % case._id,
                        case._id,
                    )

                    if not self._phone_owns(action):
                        # only action necessary here is in the case of
                        # reassignment to an owner the phone doesn't own
                        state = self.archive_case(case.get_id)
                        if state:
                            removed_states[case._id] = state
                elif action.action_type == const.CASE_ACTION_INDEX:
                    # in the case of parallel reassignment and index update
                    # the phone might not have the case
                    if self.phone_has_case(case.get_id):
                        case_state = self.get_case_state(case.get_id)
                    else:
                        self._assert(self.phone_has_dependent_case(case._id),
                                     "phone doesn't have referenced case: %s" % case._id)
                        case_state = self.get_dependent_case_state(case.get_id)
                    # reconcile indices
                    if case_state:
                        for index in action.indices:
                            new_indices.add(index.referenced_id)
                        case_state.update_indices(action.indices)

                elif action.action_type == const.CASE_ACTION_CLOSE:
                    if self.phone_has_case(case.get_id):
                        state = self.archive_case(case.get_id)
                        if state:
                            removed_states[case._id] = state

        # if we just removed a state and added an index to it
        # we have to put it back in our dependent case list
        readded_any = False
        for index in new_indices:
            if index in removed_states:
                self.dependent_cases_on_phone.append(removed_states[index])
                readded_any = True

        if readded_any:
            self._dependent_case_state_map.reset_cache(self)

        if case_list:
            try:
                self.save()
                self.invalidate_cached_payloads()
            except ResourceConflict:
                logging.exception('doc update conflict saving sync log {id}'.format(
                    id=self._id,
                ))
                raise

    def get_footprint_of_cases_on_phone(self):
        def children(case_state):
            return [self._get_case_state_from_anywhere(index.referenced_id)
                    for index in case_state.indices]

        relevant_cases = set()
        queue = list(self.cases_on_phone)
        while queue:
            case_state = queue.pop()
            # I don't actually understand why something is coming back None
            # here, but we can probably just ignore it.
            if case_state is not None and case_state.case_id not in relevant_cases:
                relevant_cases.add(case_state.case_id)
                queue.extend(children(case_state))
        return relevant_cases

    def phone_is_holding_case(self, case_id):
        """
        Whether the phone is holding (not purging) a case.
        """
        # this is inefficient and could be optimized
        if self.phone_has_case(case_id):
            return True
        else:
            cs = self.get_dependent_case_state(case_id)
            if cs and case_id in self.get_footprint_of_cases_on_phone():
                return True
            return False

    def __unicode__(self):
        return "%s synced on %s (%s)" % (self.user_id, self.date.date(), self.get_id)

    def tests_only_get_cases_on_phone(self):
        return self.cases_on_phone

    def test_only_clear_cases_on_phone(self):
        self.cases_on_phone = []

    def test_only_get_dependent_cases_on_phone(self):
        return self.dependent_cases_on_phone


PruneResult = namedtuple('PruneResult', ['seen', 'pruned'])


class IndexTree(DocumentSchema):
    """
    Document type representing a case dependency tree (which is flattened to a single dict)
    """
    # a flat mapping of cases to dicts of their indices. The keys in each dict are the index identifiers
    # and the values are the referenced case IDs
    indices = SchemaDictProperty()

    def __repr__(self):
        return json.dumps(self.indices, indent=2)

    def get_cases_that_directly_depend_on_case(self, case_id, cached_map=None):
        cached_map = cached_map or _reverse_index_map(self.indices)
        return cached_map.get(case_id, [])

    def get_all_cases_that_depend_on_case(self, case_id, cached_map=None):
        """
        Recursively builds a tree of all cases that depend on this case and returns
        a flat set of case ids.

        Allows passing in a cached map of reverse index references if you know you are going
        to call it more than once in a row to avoid rebuilding that.
        """
        def _recursive_call(case_id, all_cases, cached_map):
            all_cases.add(case_id)
            for dependent_case in self.get_cases_that_directly_depend_on_case(case_id, cached_map=cached_map):
                if dependent_case not in all_cases:
                    all_cases.add(dependent_case)
                    _recursive_call(dependent_case, all_cases, cached_map)

        all_cases = set()
        cached_map = cached_map or _reverse_index_map(self.indices)
        _recursive_call(case_id, all_cases, cached_map)
        return all_cases

    def delete_index(self, from_case_id, index_name):
        prior_ids = self.indices.pop(from_case_id, {})
        prior_ids.pop(index_name, None)
        if prior_ids:
            self.indices[from_case_id] = prior_ids

    def set_index(self, from_case_id, index_name, to_case_id):
        prior_ids = self.indices.get(from_case_id, {})
        prior_ids[index_name] = to_case_id
        self.indices[from_case_id] = prior_ids

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
    case_ids_on_phone = SetProperty(unicode)
    # this is a subset of case_ids_on_phone used to flag that a case is only around because it has dependencies
    # this allows us to prune it if possible from other actions
    dependent_case_ids_on_phone = SetProperty(unicode)
    owner_ids_on_phone = SetProperty(unicode)
    index_tree = SchemaProperty(IndexTree)

    def save(self, *args, **kwargs):
        # force doc type to SyncLog to avoid changing the couch view.
        self.doc_type = "SyncLog"
        super(SimplifiedSyncLog, self).save(*args, **kwargs)

    def case_count(self):
        return len(self.case_ids_on_phone)

    def phone_is_holding_case(self, case_id):
        """
        Whether the phone currently has a case, according to this sync log
        """
        return case_id in self.case_ids_on_phone

    def get_footprint_of_cases_on_phone(self):
        return list(self.case_ids_on_phone)

    def prune_case(self, case_id):
        """
        Prunes a case from the tree while also pruning any dependencies as a result of this pruning.
        """
        logger.debug('pruning: {}'.format(case_id))
        self.dependent_case_ids_on_phone.add(case_id)
        reverse_index_map = _reverse_index_map(self.index_tree.indices)
        dependencies = self.index_tree.get_all_cases_that_depend_on_case(case_id, cached_map=reverse_index_map)
        # we can only potentially remove a case if it's already in dependent case ids
        # and therefore not directly owned
        candidates_to_remove = dependencies & self.dependent_case_ids_on_phone
        dependencies_not_to_remove = dependencies - self.dependent_case_ids_on_phone

        def _remove_case(to_remove):
            # uses closures for assertions
            logger.debug('removing: {}'.format(to_remove))
            assert to_remove in self.dependent_case_ids_on_phone
            indices = self.index_tree.indices.pop(to_remove, {})
            if to_remove != case_id:
                # if the case had indexes they better also be in our removal list (except for ourselves)
                for index in indices.values():
                    assert index in candidates_to_remove, \
                        "expected {} in {} but wasn't".format(index, candidates_to_remove)
            try:
                self.case_ids_on_phone.remove(to_remove)
            except KeyError:
                def _should_fail_softly():
                    # old versions of commcare (< 2.10ish) didn't purge on form completion
                    # so can still modify cases that should no longer be on the phone.
                    def _domain_has_toggle_set():
                        request = get_request()
                        domain = request.domain if request else None
                        return LEGACY_SYNC_SUPPORT.enabled(domain) if domain else False

                    def _sync_log_was_old():
                        # todo: this here to avoid having to manually clean up after
                        # http://manage.dimagi.com/default.asp?179664
                        # it should be removed when there are no longer any instances of the assertion
                        if self.date < datetime(2015, 8, 25):
                            _assert = soft_assert(to=['czue' + '@' + 'dimagi.com'], exponential_backoff=False)
                            _assert(False, 'patching sync log {} to remove missing case ID {}!'.format(
                                self._id, to_remove)
                            )
                            return True
                        return False
                    return _domain_has_toggle_set() or _sync_log_was_old()

                if _should_fail_softly():
                    pass
                else:
                    raise

            self.dependent_case_ids_on_phone.remove(to_remove)

        if not dependencies_not_to_remove:
            # this case's entire relevancy chain is in dependent cases
            # this means they can all now be removed.
            this_case_indices = self.index_tree.indices.get(case_id, {})
            for to_remove in candidates_to_remove:
                _remove_case(to_remove)

            for this_case_index in this_case_indices.values():
                if (this_case_index in self.dependent_case_ids_on_phone and
                        this_case_index not in candidates_to_remove):
                    self.prune_case(this_case_index)
        else:
            # we have some possible candidates for removal. we should check each of them.
            candidates_to_remove.remove(case_id)  # except ourself
            for candidate in candidates_to_remove:
                candidate_dependencies = self.index_tree.get_all_cases_that_depend_on_case(
                    candidate, cached_map=reverse_index_map
                )
                if not candidate_dependencies - self.dependent_case_ids_on_phone:
                    _remove_case(candidate)

    def _add_primary_case(self, case_id):
        self.case_ids_on_phone.add(case_id)
        if case_id in self.dependent_case_ids_on_phone:
            self.dependent_case_ids_on_phone.remove(case_id)

    def update_phone_lists(self, xform, case_list):
        made_changes = False
        logger.debug('updating sync log for {}'.format(self.user_id))
        logger.debug('case ids before update: {}'.format(', '.join(self.case_ids_on_phone)))
        logger.debug('dependent case ids before update: {}'.format(', '.join(self.dependent_case_ids_on_phone)))
        logger.debug('index tree before update: {}'.format(self.index_tree))
        skipped = set()
        to_prune = set()
        for case in case_list:
            actions = case.get_actions_for_form(xform.get_id)
            for action in actions:
                logger.debug('{}: {}'.format(case._id, action.action_type))
                owner_id = action.updated_known_properties.get("owner_id")
                phone_owns_case = not owner_id or owner_id in self.owner_ids_on_phone
                log_has_case = case._id not in skipped
                if action.action_type == const.CASE_ACTION_CREATE:
                    if phone_owns_case:
                        self._add_primary_case(case._id)
                        made_changes = True
                    else:
                        skipped.add(case._id)
                elif action.action_type == const.CASE_ACTION_UPDATE:
                    if not phone_owns_case and log_has_case:
                        # we must have just changed the owner_id to something we didn't own
                        # we can try pruning this case since it's no longer relevant
                        to_prune.add(case._id)
                        made_changes = True
                    else:
                        if phone_owns_case and not log_has_case:
                            # this can happen if a create sets the owner id to something invalid
                            # and an update in the same block/form sets it back to valid
                            self._add_primary_case(case._id)
                            made_changes = True
                        if case._id in self.dependent_case_ids_on_phone:
                            self.dependent_case_ids_on_phone.remove(case._id)
                            made_changes = True
                elif action.action_type == const.CASE_ACTION_INDEX:
                    # we should never have to do anything with case IDs here since the
                    # indexed case should already be on the phone.
                    # however, we should update our index tree accordingly
                    for index in action.indices:
                        if index.referenced_id:
                            self.index_tree.set_index(case._id, index.identifier, index.referenced_id)
                            if index.referenced_id not in self.case_ids_on_phone:
                                self.case_ids_on_phone.add(index.referenced_id)
                                self.dependent_case_ids_on_phone.add(index.referenced_id)
                        else:
                            self.index_tree.delete_index(case._id, index.identifier)
                        made_changes = True
                elif action.action_type == const.CASE_ACTION_CLOSE:
                    if log_has_case:
                        # this case is being closed. we can try pruning this case since it's no longer relevant
                        to_prune.add(case._id)
                        made_changes = True

        for case_to_prune in to_prune:
            self.prune_case(case_to_prune)

        logger.debug('case ids after update: {}'.format(', '.join(self.case_ids_on_phone)))
        logger.debug('dependent case ids after update: {}'.format(', '.join(self.dependent_case_ids_on_phone)))
        logger.debug('index tree after update: {}'.format(self.index_tree))
        if made_changes or case_list:
            try:
                if made_changes:
                    logger.debug('made changes, saving.')
                    self.last_submitted = datetime.utcnow()
                    self.save()
                    if case_list:
                        try:
                            self.invalidate_cached_payloads()
                        except ResourceConflict:
                            # this operation is harmless so just blindly retry and don't
                            # reraise if it goes through the second time
                            SimplifiedSyncLog.get(self._id).invalidate_cached_payloads()
            except ResourceConflict:
                logging.exception('doc update conflict saving sync log {id}'.format(
                    id=self._id,
                ))
                raise

    def prune_dependent_cases(self):
        """
        Attempt to prune any dependent cases from the sync log.
        """
        # this is done when migrating from old formats or during initial sync
        # to prune non-relevant dependencies
        for dependent_case_id in list(self.dependent_case_ids_on_phone):
            # need this additional check since the case might have already been pruned/remove
            # as a result of pruning the child case
            if dependent_case_id in self.dependent_case_ids_on_phone:
                # this will be a no-op if the case cannot be pruned due to dependencies
                self.prune_case(dependent_case_id)

    @classmethod
    def from_other_format(cls, other_sync_log):
        """
        Migrate from the old SyncLog format to this one.
        """
        if isinstance(other_sync_log, SyncLog):
            previous_log_footprint = set(other_sync_log.get_footprint_of_cases_on_phone())

            def _add_state_contributions(new_sync_log, case_state, is_dependent=False):
                if case_state.case_id in previous_log_footprint:
                    new_sync_log.case_ids_on_phone.add(case_state.case_id)
                    for index in case_state.indices:
                        new_sync_log.index_tree.set_index(case_state.case_id, index.identifier, index.referenced_id)
                    if is_dependent:
                        new_sync_log.dependent_case_ids_on_phone.add(case_state.case_id)

            ret = cls.wrap(other_sync_log.to_json())
            for case_state in other_sync_log.cases_on_phone:
                _add_state_contributions(ret, case_state)

            dependent_case_ids = set()
            for case_state in other_sync_log.dependent_cases_on_phone:
                if case_state.case_id in previous_log_footprint:
                    _add_state_contributions(ret, case_state, is_dependent=True)
                    dependent_case_ids.add(case_state.case_id)

            # try to prune any dependent cases - the old format does this on
            # access, but the new format does it ahead of time and always assumes
            # its current state is accurate.
            ret.prune_dependent_cases()

            # set and cleanup other properties
            ret.log_format = LOG_FORMAT_SIMPLIFIED
            del ret['last_seq']
            del ret['cases_on_phone']
            del ret['dependent_cases_on_phone']

            ret.migrated_from = other_sync_log.to_json()
            return ret
        else:
            return super(SimplifiedSyncLog, cls).from_other_format(other_sync_log)

    def tests_only_get_cases_on_phone(self):
        # hack - just for tests
        return [CaseState(case_id=id) for id in self.case_ids_on_phone]

    def test_only_clear_cases_on_phone(self):
        self. case_ids_on_phone = set()

    def test_only_get_dependent_cases_on_phone(self):
        # hack - just for tests
        return [CaseState(case_id=id) for id in self.dependent_case_ids_on_phone]


def get_properly_wrapped_sync_log(doc_id):
    """
    Looks up and wraps a sync log, using the class based on the 'log_format' attribute.
    Defaults to the existing legacy SyncLog class.
    """
    return properly_wrap_sync_log(SyncLog.get_db().get(doc_id))


def properly_wrap_sync_log(doc):
    return get_sync_log_class_by_format(doc.get('log_format')).wrap(doc)


def get_sync_log_class_by_format(format):
    return {
        LOG_FORMAT_LEGACY: SyncLog,
        LOG_FORMAT_SIMPLIFIED: SimplifiedSyncLog,
    }.get(format, SyncLog)


class OwnershipCleanlinessFlag(models.Model):
    """
    Stores whether an owner_id is "clean" aka has a case universe only belonging
    to that ID.

    We use this field to optimize restores.
    """
    domain = models.CharField(max_length=100, db_index=True)
    owner_id = models.CharField(max_length=100, db_index=True)
    is_clean = models.BooleanField(default=False)
    last_checked = models.DateTimeField()
    hint = models.CharField(max_length=100, null=True, blank=True)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        self.last_checked = datetime.utcnow()
        super(OwnershipCleanlinessFlag, self).save(force_insert, force_update, using, update_fields)

    @classmethod
    def get_for_owner(cls, domain, owner_id):
        return cls.objects.get_or_create(domain=domain, owner_id=owner_id)[0]

    class Meta:
        app_label = 'phone'
        unique_together = [('domain', 'owner_id')]
