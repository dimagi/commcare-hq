from collections import defaultdict
from copy import copy
from functools import partial
from datetime import datetime
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import EXTENSION_CASES_SYNC_ENABLED
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.const import CASE_INDEX_EXTENSION, CASE_INDEX_CHILD
from casexml.apps.case.dbaccessors import get_extension_case_ids
from casexml.apps.phone.cleanliness import get_case_footprint_info
from casexml.apps.phone.data_providers.case.load_testing import append_update_to_response
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates, CaseStub
from casexml.apps.phone.models import OwnershipCleanlinessFlag, LOG_FORMAT_SIMPLIFIED, IndexTree, SimplifiedSyncLog
from corehq.apps.hqcase.dbaccessors import get_open_case_ids, get_case_ids_in_domain_by_owner
from corehq.apps.users.cases import get_owner_id
from corehq.dbaccessors.couchapps.cases_by_server_date.by_owner_server_modified_on import \
    get_case_ids_modified_with_owner_since
from corehq.dbaccessors.couchapps.cases_by_server_date.by_server_modified_on import get_last_modified_dates
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.decorators.memoized import memoized


def get_case_payload(restore_state):
    sync_op = CleanOwnerCaseSyncOperation(restore_state)
    return sync_op.get_payload()


# todo: push to state?
chunk_size = 1000


class CleanOwnerCaseSyncOperation(object):

    def __init__(self, restore_state):
        self.restore_state = restore_state

    @property
    @memoized
    def cleanliness_flags(self):
        return dict(
            OwnershipCleanlinessFlag.objects.filter(
                domain=self.restore_state.domain,
                owner_id__in=self.restore_state.owner_ids
            ).values_list('owner_id', 'is_clean')
        )

    def is_clean(self, owner_id):
        return self.cleanliness_flags.get(owner_id, False)

    def get_payload(self):
        response = self.restore_state.restore_class()
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
                self.restore_state.domain, list(other_ids_to_check), self.restore_state.last_sync_log.date
            ))

        all_maybe_syncing = copy(case_ids_to_sync)
        all_synced = set()
        child_indices = defaultdict(set)
        extension_indices = defaultdict(set)
        all_dependencies_syncing = set()
        closed_cases = set()
        potential_updates_to_sync = []
        while case_ids_to_sync:
            ids = pop_ids(case_ids_to_sync, chunk_size)
            # todo: see if we can avoid wrapping - serialization depends on it heavily for now
            case_batch = filter(
                partial(case_needs_to_sync, last_sync_log=self.restore_state.last_sync_log),
                [case for case in CaseAccessors(self.restore_state.domain).get_cases(ids)
                 if not case.is_deleted]
            )
            updates = get_case_sync_updates(
                self.restore_state.domain, case_batch, self.restore_state.last_sync_log
            )
            for update in updates:
                case = update.case
                all_synced.add(case.case_id)
                potential_updates_to_sync.append(update)

                # update the indices in the new sync log
                if case.indices:
                    # and double check footprint for non-live cases
                    extension_indices[case.case_id] = {index.identifier: index.referenced_id for index in case.indices
                                                   if index.relationship == CASE_INDEX_EXTENSION}
                    child_indices[case.case_id] = {index.identifier: index.referenced_id for index in case.indices
                                               if index.relationship == CASE_INDEX_CHILD}
                    for index in case.indices:
                        if index.referenced_id not in all_maybe_syncing:
                            case_ids_to_sync.add(index.referenced_id)

                if not _is_live(case, self.restore_state):
                    all_dependencies_syncing.add(case.case_id)
                    if case.closed:
                        closed_cases.add(case.case_id)

            # commtrack ledger sections for this batch
            commtrack_elements = get_stock_payload(
                self.restore_state.project, self.restore_state.stock_settings,
                [CaseStub(update.case.case_id, update.case.type) for update in updates]
            )
            response.extend(commtrack_elements)

            # add any new values to all_syncing
            all_maybe_syncing = all_maybe_syncing | case_ids_to_sync

        # update sync token - marking it as the new format
        self.restore_state.current_sync_log = SimplifiedSyncLog.wrap(
            self.restore_state.current_sync_log.to_json()
        )
        self.restore_state.current_sync_log.log_format = LOG_FORMAT_SIMPLIFIED
        self.restore_state.current_sync_log.extensions_checked = True

        index_tree = IndexTree(indices=child_indices)
        extension_index_tree = IndexTree(indices=extension_indices)
        case_ids_on_phone = all_synced
        primary_cases_syncing = all_synced - all_dependencies_syncing
        if not self.restore_state.is_initial:
            case_ids_on_phone = case_ids_on_phone | self.restore_state.last_sync_log.case_ids_on_phone
            # subtract primary cases from dependencies since they must be newly primary
            all_dependencies_syncing = all_dependencies_syncing | (
                self.restore_state.last_sync_log.dependent_case_ids_on_phone -
                primary_cases_syncing
            )
            index_tree = self.restore_state.last_sync_log.index_tree.apply_updates(index_tree)

        self.restore_state.current_sync_log.case_ids_on_phone = case_ids_on_phone
        self.restore_state.current_sync_log.dependent_case_ids_on_phone = all_dependencies_syncing
        self.restore_state.current_sync_log.index_tree = index_tree
        self.restore_state.current_sync_log.extension_index_tree = extension_index_tree
        self.restore_state.current_sync_log.closed_cases = closed_cases

        _move_no_longer_owned_cases_to_dependent_list_if_necessary(self.restore_state)
        self.restore_state.current_sync_log.purge_dependent_cases()

        purged_cases = case_ids_on_phone - self.restore_state.current_sync_log.case_ids_on_phone

        # don't sync purged cases that were never on the phone
        if self.restore_state.is_initial:
            irrelevant_cases = purged_cases
        else:
            irrelevant_cases = purged_cases - self.restore_state.last_sync_log.case_ids_on_phone

        for update in potential_updates_to_sync:
            if update.case.case_id not in irrelevant_cases:
                append_update_to_response(response, update, self.restore_state)

        return response

    def get_case_ids_for_owner(self, owner_id):
        if EXTENSION_CASES_SYNC_ENABLED.enabled(self.restore_state.domain):
            return self._get_case_ids_for_owners_with_extensions(owner_id)
        else:
            return self._get_case_ids_for_owners_without_extensions(owner_id)

    def _get_case_ids_for_owners_without_extensions(self, owner_id):
        if self.is_clean(owner_id):
            domain = self.restore_state.domain
            if self.restore_state.is_initial:
                # for a clean owner's initial sync the base set is just the open ids
                return set(CaseAccessors(domain).get_open_case_ids(owner_id))
            else:
                # for a clean owner's steady state sync, the base set is anything modified since last sync
                return set(get_case_ids_modified_with_owner_since(
                    self.restore_state.domain, owner_id, self.restore_state.last_sync_log.date
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
            domain = self.restore_state.domain
            case_accessor = CaseAccessors(domain)
            if self.restore_state.is_initial:
                # for a clean owner's initial sync the base set is just the open ids and their extensions
                all_case_ids = set(case_accessor.get_open_case_ids(owner_id))
                new_case_ids = set(all_case_ids)
                while new_case_ids:
                    all_case_ids = all_case_ids | new_case_ids
                    extension_case_ids = set(case_accessor.get_extension_case_ids(new_case_ids))
                    new_case_ids = extension_case_ids - all_case_ids
                return all_case_ids
            else:
                # for a clean owner's steady state sync, the base set is anything modified since last sync
                modified_non_extension_cases = set(get_case_ids_modified_with_owner_since(
                    self.restore_state.domain, owner_id, self.restore_state.last_sync_log.date
                ))
                # we also need to fetch unowned extension cases that have been modified
                extension_case_ids = self.restore_state.last_sync_log.extension_index_tree.indices.keys()
                modified_extension_cases = set(filter_cases_modified_since(
                    domain, extension_case_ids, self.restore_state.last_sync_log.date
                ))
                return modified_non_extension_cases | modified_extension_cases


def _is_live(case, restore_state):
    """
    Given a case and a restore state object, return whether or not the case is "live"
    (direclty owned by this sync and open), or "dependent" (needed by another case)
    """
    return not case.closed and get_owner_id(case) in restore_state.owner_ids


def filter_cases_modified_since(domain, case_ids, reference_date):
    """
    Given a domain, case_ids, and a reference date, filter the case ids to only those
    that have been modified since that reference date.
    """
    last_modified_date_dict = get_last_modified_dates(domain, case_ids)
    for case_id in case_ids:
        if last_modified_date_dict.get(case_id, datetime(1900, 1, 1)) > reference_date:
            yield case_id


def case_needs_to_sync(case, last_sync_log):
    owner_id = case.owner_id or case.user_id  # need to fallback to user_id for v1 cases
    extension_cases = [index for index in case.indices
                       if index.relationship == CASE_INDEX_EXTENSION]
    if (not last_sync_log or
        (owner_id not in last_sync_log.owner_ids_on_phone and
         not (extension_cases and case.case_id in last_sync_log.case_ids_on_phone))):
        # initial sync or new owner IDs always sync down everything
        # extension cases don't get synced again if they haven't changed
        return True
    elif case.server_modified_on >= last_sync_log.date:
        # check all of the actions since last sync for one that had a different sync token
        return any(filter(
            lambda action: action.server_date > last_sync_log.date and action.sync_log_id != last_sync_log._id,
            case.actions,
        ))
    # if the case wasn't touched since last sync, and the phone was aware of this owner_id last time
    # don't worry about it
    return False


def pop_ids(set_, how_many):
    result = []
    for i in range(how_many):
        try:
            result.append(set_.pop())
        except KeyError:
            pass
    return result


def _move_no_longer_owned_cases_to_dependent_list_if_necessary(restore_state):
    if not restore_state.is_initial:
        removed_owners = (
            set(restore_state.last_sync_log.owner_ids_on_phone) - set(restore_state.owner_ids)
        )
        if removed_owners:
            # if we removed any owner ids, then any cases that belonged to those owners need
            # to be moved to the dependent list
            case_ids_to_try_purging = get_case_ids_in_domain_by_owner(
                domain=restore_state.domain,
                owner_id__in=list(removed_owners),
            )
            for to_purge in case_ids_to_try_purging:
                if to_purge in restore_state.current_sync_log.case_ids_on_phone:
                    restore_state.current_sync_log.dependent_case_ids_on_phone.add(to_purge)
