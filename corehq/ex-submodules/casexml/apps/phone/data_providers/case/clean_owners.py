from collections import defaultdict
from copy import copy
from functools import partial
from datetime import datetime
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.cleanliness import get_case_footprint_info
from casexml.apps.phone.data_providers.case.load_testing import append_update_to_response
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates, CaseStub
from casexml.apps.phone.models import OwnershipCleanlinessFlag, LOG_FORMAT_SIMPLIFIED, IndexTree, SimplifiedSyncLog
from corehq.apps.hqcase.dbaccessors import get_open_case_ids
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
        all_indices = defaultdict(set)
        all_dependencies_syncing = set()
        while case_ids_to_sync:
            ids = pop_ids(case_ids_to_sync, chunk_size)
            # todo: see if we can avoid wrapping - serialization depends on it heavily for now
            case_batch = filter(
                partial(case_needs_to_sync, last_sync_log=self.restore_state.last_sync_log),
                [CommCareCase.wrap(doc) for doc in get_docs(CommCareCase.get_db(), ids)]
            )
            updates = get_case_sync_updates(
                self.restore_state.domain, case_batch, self.restore_state.last_sync_log
            )
            for update in updates:
                case = update.case
                all_synced.add(case._id)
                append_update_to_response(response, update, self.restore_state)

                # update the indices in the new sync log
                if case.indices:
                    all_indices[case._id] = {index.identifier: index.referenced_id for index in case.indices}
                    # and double check footprint for non-live cases
                    for index in case.indices:
                        if index.referenced_id not in all_maybe_syncing:
                            case_ids_to_sync.add(index.referenced_id)

                if not _is_live(case, self.restore_state):
                    all_dependencies_syncing.add(case._id)

            # commtrack ledger sections for this batch
            commtrack_elements = get_stock_payload(
                self.restore_state.project, self.restore_state.stock_settings,
                [CaseStub(update.case._id, update.case.type) for update in updates]
            )
            response.extend(commtrack_elements)

            # add any new values to all_syncing
            all_maybe_syncing = all_maybe_syncing | case_ids_to_sync

        # update sync token - marking it as the new format
        self.restore_state.current_sync_log = SimplifiedSyncLog.wrap(
            self.restore_state.current_sync_log.to_json()
        )
        self.restore_state.current_sync_log.log_format = LOG_FORMAT_SIMPLIFIED
        index_tree = IndexTree(indices=all_indices)
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
        # this is a shortcut to prune closed cases we just sent down before saving the sync log
        self.restore_state.current_sync_log.prune_dependent_cases()
        return response

    def get_case_ids_for_owner(self, owner_id):
        if self.is_clean(owner_id):
            if self.restore_state.is_initial:
                # for a clean owner's initial sync the base set is just the open ids
                return set(get_open_case_ids(self.restore_state.domain, owner_id))
            else:
                # for a clean owner's steady state sync, the base set is anything modified since last sync
                return set(get_case_ids_modified_with_owner_since(
                    self.restore_state.domain, owner_id, self.restore_state.last_sync_log.date
                ))
        else:
            # todo: we may want to be smarter than this
            # right now just return the whole footprint and do any filtering later
            return get_case_footprint_info(self.restore_state.domain, owner_id).all_ids


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
    if not last_sync_log or owner_id not in last_sync_log.owner_ids_on_phone:
        # initial sync or new owner IDs always sync down everything
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
