from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict, namedtuple
from copy import copy
from datetime import datetime
from functools import partial
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import EXTENSION_CASES_SYNC_ENABLED
from corehq.util.datadog.utils import case_load_counter
from casexml.apps.case.const import CASE_INDEX_EXTENSION, CASE_INDEX_CHILD
from casexml.apps.phone.cleanliness import get_case_footprint_info
from casexml.apps.phone.const import ASYNC_RETRY_AFTER
from casexml.apps.phone.data_providers.case.load_testing import get_xml_for_response
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates, CaseStub
from casexml.apps.phone.models import OwnershipCleanlinessFlag, IndexTree
from casexml.apps.phone.tasks import ASYNC_RESTORE_SENT
from corehq.apps.users.cases import get_owner_id
from memoized import memoized
import six
from six.moves import range


PotentialSyncElement = namedtuple("PotentialSyncElement", ['case_stub', 'sync_xml_items'])


# todo: push to state?
chunk_size = 1000


class CleanOwnerSyncPayload(object):
    def __init__(self, timing_context, case_ids_to_sync, restore_state):
        self.restore_state = restore_state
        self.case_accessor = CaseAccessors(self.restore_state.domain)

        self.case_ids_to_sync = case_ids_to_sync
        self.all_maybe_syncing = copy(case_ids_to_sync)
        self.checked_cases = set()
        self.child_indices = defaultdict(set)
        self.extension_indices = defaultdict(set)
        self.all_dependencies_syncing = set()
        self.closed_cases = set()
        self.potential_elements_to_sync = {}

        self.timing_context = timing_context
        self._track_load = case_load_counter("cleanowner_restore", restore_state.domain)

    def extend_response(self, response):
        with self.timing_context('process_case_batches'):
            while self.case_ids_to_sync:
                self.process_case_batch(self._get_next_case_batch())

        with self.timing_context('update_index_trees'):
            self.update_index_trees()

        with self.timing_context('update_case_ids_on_phone'):
            self.update_case_ids_on_phone()

        with self.timing_context('move_no_longer_owned_cases_to_dependent_list_if_necessary'):
            self.move_no_longer_owned_cases_to_dependent_list_if_necessary()

        with self.timing_context('purge_and_get_irrelevant_cases'):
            irrelevant_cases = self.purge_and_get_irrelevant_cases()

        with self.timing_context('compile_response'):
            self.compile_response(irrelevant_cases, response)

    def _get_next_case_batch(self):
        ids = pop_ids(self.case_ids_to_sync, chunk_size)
        self._track_load(len(ids))
        return [
            case for case in self.case_accessor.get_cases(ids)
            if not case.is_deleted and case_needs_to_sync(case, last_sync_log=self.restore_state.last_sync_log)
        ]

    def process_case_batch(self, case_batch):
        updates = get_case_sync_updates(
            self.restore_state.domain, case_batch, self.restore_state.last_sync_log
        )

        for update in updates:
            case = update.case
            self.potential_elements_to_sync[case.case_id] = PotentialSyncElement(
                case_stub=CaseStub(case.case_id, case.type),
                sync_xml_items=get_xml_for_response(update, self.restore_state)
            )
            self._process_case_update(case)
            self._mark_case_as_checked(case)

    def _process_case_update(self, case):
        if case.indices:
            self._update_indices_in_new_synclog(case)
            self._add_unchecked_indices_to_be_checked(case)

        if not _is_live(case, self.restore_state):
            self.all_dependencies_syncing.add(case.case_id)
            if case.closed:
                self.closed_cases.add(case.case_id)

    def _mark_case_as_checked(self, case):
        self.checked_cases.add(case.case_id)

    def _update_indices_in_new_synclog(self, case):
        self.extension_indices[case.case_id] = {
            index.identifier: index.referenced_id
            for index in case.indices
            if index.relationship == CASE_INDEX_EXTENSION
        }
        self.child_indices[case.case_id] = {
            index.identifier: index.referenced_id
            for index in case.indices
            if index.relationship == CASE_INDEX_CHILD
        }

    def _add_unchecked_indices_to_be_checked(self, case):
        for index in case.indices:
            if index.referenced_id not in self.all_maybe_syncing:
                self.case_ids_to_sync.add(index.referenced_id)
        self.all_maybe_syncing |= self.case_ids_to_sync

    def move_no_longer_owned_cases_to_dependent_list_if_necessary(self):
        if not self.restore_state.is_initial:
            removed_owners = (
                set(self.restore_state.last_sync_log.owner_ids_on_phone) - set(self.restore_state.owner_ids)
            )
            if removed_owners:
                # if we removed any owner ids, then any cases that belonged to those owners need
                # to be moved to the dependent list
                case_ids_to_try_purging = self.case_accessor.get_case_ids_by_owners(list(removed_owners))
                for to_purge in case_ids_to_try_purging:
                    if to_purge in self.restore_state.current_sync_log.case_ids_on_phone:
                        self.restore_state.current_sync_log.dependent_case_ids_on_phone.add(to_purge)

    def update_index_trees(self):
        index_tree = IndexTree(indices=self.child_indices)
        extension_index_tree = IndexTree(indices=self.extension_indices)
        if not self.restore_state.is_initial:
            index_tree = self.restore_state.last_sync_log.index_tree.apply_updates(index_tree)
            extension_index_tree = self.restore_state.last_sync_log.extension_index_tree.apply_updates(
                extension_index_tree
            )

        self.restore_state.current_sync_log.index_tree = index_tree
        self.restore_state.current_sync_log.extension_index_tree = extension_index_tree

    def update_case_ids_on_phone(self):
        case_ids_on_phone = self.checked_cases
        primary_cases_syncing = self.checked_cases - self.all_dependencies_syncing
        if not self.restore_state.is_initial:
            case_ids_on_phone |= self.restore_state.last_sync_log.case_ids_on_phone
            # subtract primary cases from dependencies since they must be newly primary
            self.all_dependencies_syncing |= (
                self.restore_state.last_sync_log.dependent_case_ids_on_phone -
                primary_cases_syncing
            )
        self.restore_state.current_sync_log.case_ids_on_phone = case_ids_on_phone
        self.restore_state.current_sync_log.dependent_case_ids_on_phone = self.all_dependencies_syncing
        self.restore_state.current_sync_log.closed_cases = self.closed_cases

    def purge_and_get_irrelevant_cases(self):
        original_case_ids_on_phone = self.restore_state.current_sync_log.case_ids_on_phone.copy()
        self.restore_state.current_sync_log.purge_dependent_cases()
        purged_cases = original_case_ids_on_phone - self.restore_state.current_sync_log.case_ids_on_phone
        # don't sync purged cases that were never on the phone
        if self.restore_state.is_initial:
            irrelevant_cases = purged_cases
        else:
            irrelevant_cases = purged_cases - self.restore_state.last_sync_log.case_ids_on_phone
        return irrelevant_cases

    def compile_response(self, irrelevant_cases, response):
        relevant_sync_elements = [
            potential_sync_element
            for syncable_case_id, potential_sync_element in six.iteritems(self.potential_elements_to_sync)
            if syncable_case_id not in irrelevant_cases
        ]

        with self.timing_context('add_commtrack_elements_to_response'):
            self._add_commtrack_elements_to_response(relevant_sync_elements, response)

        self._add_case_elements_to_response(relevant_sync_elements, response)

    def _add_commtrack_elements_to_response(self, relevant_sync_elements, response):
        commtrack_elements = get_stock_payload(
            self.restore_state.project, self.restore_state.stock_settings,
            [
                potential_sync_element.case_stub
                for potential_sync_element in relevant_sync_elements
            ]
        )
        response.extend(commtrack_elements)

    def _add_case_elements_to_response(self, relevant_sync_elements, response):
        for relevant_case in relevant_sync_elements:
            response.extend(relevant_case.sync_xml_items)


class AsyncCleanOwnerPayload(CleanOwnerSyncPayload):
    """
    Case Sync Payload that updates progress on a celery task
    """
    def __init__(self, timing_context, case_ids_to_sync, restore_state, current_task):
        super(AsyncCleanOwnerPayload, self).__init__(timing_context, case_ids_to_sync, restore_state)
        self.current_task = current_task

    def extend_response(self, response):
        self._update_progress(total=len(self.all_maybe_syncing))
        return super(AsyncCleanOwnerPayload, self).extend_response(response)

    def _mark_case_as_checked(self, case):
        super(AsyncCleanOwnerPayload, self)._mark_case_as_checked(case)
        self._update_progress(done=len(self.checked_cases), total=len(self.all_maybe_syncing))

    def _update_progress(self, done=0, total=0):
        self.current_task.update_state(
            state=ASYNC_RESTORE_SENT,
            meta={
                'done': done,
                'total': total,
                'retry-after': ASYNC_RETRY_AFTER
            }
        )


class CleanOwnerCaseSyncOperation(object):

    def __init__(self, timing_context, restore_state, async_task=None):
        self.timing_context = timing_context
        self.restore_state = restore_state
        self.case_accessor = CaseAccessors(self.restore_state.domain)
        self.async_task = async_task

    @property
    @memoized
    def cleanliness_flags(self):
        return dict(
            OwnershipCleanlinessFlag.objects.filter(
                domain=self.restore_state.domain,
                owner_id__in=self.restore_state.owner_ids
            ).values_list('owner_id', 'is_clean')
        )

    @property
    def payload_class(self):
        if self.async_task is not None:
            return partial(AsyncCleanOwnerPayload, current_task=self.async_task)
        return CleanOwnerSyncPayload

    def is_clean(self, owner_id):
        return self.cleanliness_flags.get(owner_id, False)

    def is_new_owner(self, owner_id):
        return (
            self.restore_state.is_initial or
            owner_id not in self.restore_state.last_sync_log.owner_ids_on_phone
        )

    def extend_response(self, response):
        with self.timing_context('get_case_ids_to_sync'):
            case_ids_to_sync = self.get_case_ids_to_sync()
        sync_payload = self.payload_class(self.timing_context, case_ids_to_sync, self.restore_state)
        return sync_payload.extend_response(response)

    def get_case_ids_to_sync(self):
        case_ids_to_sync = set()
        for owner_id in self.restore_state.owner_ids:
            case_ids_to_sync = case_ids_to_sync | set(self.get_case_ids_for_owner(owner_id))

        if (not self.restore_state.is_initial and
                any([not self.is_clean(owner_id) for owner_id in self.restore_state.owner_ids])):
            # if it's a steady state sync and we have any dirty owners, then we also need to
            # include ALL cases on the phone that have been modified since the last sync as
            # possible candidates to sync (since they may have been closed or reassigned by someone else)

            # don't bother checking ones we've already decided to check
            other_ids_to_check = self.restore_state.last_sync_log.case_ids_on_phone - case_ids_to_sync
            case_ids_to_sync = case_ids_to_sync | set(filter_cases_modified_since(
                self.case_accessor, list(other_ids_to_check), self.restore_state.last_sync_log.date
            ))
        return case_ids_to_sync

    def get_case_ids_for_owner(self, owner_id):
        if EXTENSION_CASES_SYNC_ENABLED.enabled(self.restore_state.domain):
            return self._get_case_ids_for_owners_with_extensions(owner_id)
        else:
            return self._get_case_ids_for_owners_without_extensions(owner_id)

    def _get_case_ids_for_owners_without_extensions(self, owner_id):
        if self.is_clean(owner_id):
            if self.is_new_owner(owner_id):
                # for a clean owner's initial sync the base set is just the open ids
                return set(self.case_accessor.get_open_case_ids_for_owner(owner_id))
            else:
                # for a clean owner's steady state sync, the base set is anything modified since last sync
                return set(self.case_accessor.get_case_ids_modified_with_owner_since(
                    owner_id, self.restore_state.last_sync_log.date
                ))
        else:
            # TODO: we may want to be smarter than this
            # right now just return the whole footprint and do any filtering later
            # Note: This will also return extensions if they exist.
            return get_case_footprint_info(self.restore_state.domain, owner_id).all_ids

    def _get_case_ids_for_owners_with_extensions(self, owner_id):
        """Fetches base and extra cases when extensions are enabled"""
        if not self.is_clean(owner_id) or self.restore_state.is_first_extension_sync:
            # If this is the first time a user with extensions has synced after
            # the extension flag is toggled, pull all the cases so that the
            # extension parameters get set correctly
            return get_case_footprint_info(self.restore_state.domain, owner_id).all_ids
        else:
            if self.is_new_owner(owner_id):
                # for a clean owner's initial sync the base set is just the open ids and their extensions
                all_case_ids = set(self.case_accessor.get_open_case_ids_for_owner(owner_id))
                new_case_ids = set(all_case_ids)
                while new_case_ids:
                    all_case_ids = all_case_ids | new_case_ids
                    extension_case_ids = set(self.case_accessor.get_extension_case_ids(new_case_ids))
                    new_case_ids = extension_case_ids - all_case_ids
                return all_case_ids
            else:
                # for a clean owner's steady state sync, the base set is anything modified since last sync
                modified_non_extension_cases = set(self.case_accessor.get_case_ids_modified_with_owner_since(
                    owner_id, self.restore_state.last_sync_log.date
                ))
                # we also need to fetch unowned extension cases that have been modified
                extension_case_ids = list(self.restore_state.last_sync_log.extension_index_tree.indices.keys())
                modified_extension_cases = set(filter_cases_modified_since(
                    self.case_accessor, extension_case_ids, self.restore_state.last_sync_log.date
                ))
                return modified_non_extension_cases | modified_extension_cases


def _is_live(case, restore_state):
    """
    Given a case and a restore state object, return whether or not the case is "live"
    (direclty owned by this sync and open), or "dependent" (needed by another case)
    """
    return not case.closed and get_owner_id(case) in restore_state.owner_ids


def filter_cases_modified_since(case_accessor, case_ids, reference_date):
    """
    Given a CaseAccessors, case_ids, and a reference date, filter the case ids to only those
    that have been modified since that reference date.
    """
    last_modified_date_dict = case_accessor.get_last_modified_dates(case_ids)
    for case_id in case_ids:
        if last_modified_date_dict.get(case_id, datetime(1900, 1, 1)) > reference_date:
            yield case_id


def case_needs_to_sync(case, last_sync_log):
    # initial sync or new owner IDs always sync down everything
    if not last_sync_log:
        return True

    # if this is a new owner_id and the case wasn't previously on the phone
    # if it's an extension, and it was already on the phone, don't sync it
    owner_id = case.owner_id or case.user_id  # need to fallback to user_id for v1 cases
    if (owner_id not in last_sync_log.owner_ids_on_phone and (
            case.case_id not in last_sync_log.case_ids_on_phone or not _is_extension(case))):
        return True
    elif case.server_modified_on >= last_sync_log.date:
        return case.modified_since_sync(last_sync_log)
    # if the case wasn't touched since last sync, and the phone was aware of this owner_id last time
    # don't worry about it
    return False


@memoized
def _is_extension(case):
    return len([index for index in case.indices
                if index.relationship == CASE_INDEX_EXTENSION]) > 0


def pop_ids(set_, how_many):
    result = []
    for i in range(how_many):
        try:
            result.append(set_.pop())
        except KeyError:
            pass
    return result
