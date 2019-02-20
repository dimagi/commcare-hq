"""Restore logic implementation aiming to minimize database queries

Example case graphs with outcomes:

   a   <--ext-- d(owned) >> a b d
       <--ext-- b

   e(owned)    --ext--> a(closed) >> a b e
               --ext--> b

   b(closed)   <--chi-- a(owned) >> a b c
               <--ext-- c

   a(closed)   <--ext-- d(owned) >> []

   a <--ext-- b <--ext-- c(owned) >> a b c

   a(closed) <--ext-- b <--ext-- c(owned) >> []

   a(closed) <--ext-- b <--ext-- c(owned) <--chi-- d >> []

   a(closed) <--ext-- b <--chi-- c(owned) >> []
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from collections import defaultdict
from itertools import chain, islice

from casexml.apps.case.const import CASE_INDEX_EXTENSION as EXTENSION
from casexml.apps.phone.data_providers.case.load_testing import (
    get_xml_for_response,
)
from casexml.apps.phone.const import ASYNC_RETRY_AFTER
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates
from casexml.apps.phone.tasks import ASYNC_RESTORE_SENT
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.datadog.utils import case_load_counter


def do_livequery(timing_context, restore_state, response, async_task=None):
    """Get case sync restore response

    This function makes no changes to external state other than updating
    the `restore_state.current_sync_log` and progress of `async_task`.
    Extends `response` with restore elements.
    """
    def index_key(index):
        return '{} {}'.format(index.case_id, index.identifier)

    def is_extension(case_id):
        """Determine if case_id is an extension case

        A case that is both a child and an extension is not an extension.
        """
        return case_id in hosts_by_extension and case_id not in parents_by_child

    def has_live_extension(case_id, cache={}):
        """Check if available case_id has a live extension case

        Do not check for live children because an available parent
        cannot cause it's children to become live. This is unlike an
        available host, which can cause its available extension to
        become live through the recursive rules:

        - A case is available if
            - it is open and not an extension case (applies to host).
            - it is open and is the extension of an available case.
        - A case is live if it is owned and available.

        The result is cached to reduce recursion in subsequent calls
        and to prevent infinite recursion.
        """
        try:
            return cache[case_id]
        except KeyError:
            cache[case_id] = False
        cache[case_id] = result = any(
            ext_id in live_ids      # has live extension
            or ext_id in owned_ids  # ext is owned and available, will be live
            or has_live_extension(ext_id)
            for ext_id in extensions_by_host[case_id]
        )
        return result

    def enliven(case_id):
        """Mark the given case, its extensions and their hosts as live

        This closure mutates `live_ids` from the enclosing function.
        """
        if case_id in live_ids:
            # already live
            return
        debug('enliven(%s)', case_id)
        live_ids.add(case_id)
        # case is open and is the extension of a live case
        ext_ids = extensions_by_host.get(case_id, [])
        # case has live extension
        host_ids = hosts_by_extension.get(case_id, [])
        # case has live child
        parent_ids = parents_by_child.get(case_id, [])
        for cid in chain(ext_ids, host_ids, parent_ids):
            enliven(cid)

    def classify(index, prev_ids):
        """Classify index as either live or extension with live status pending

        This closure mutates case graph data structures from the
        enclosing function.

        :returns: Case id for next related index fetch or IGNORE
        if the related case should be ignored.
        """
        sub_id = index.case_id
        ref_id = index.referenced_id  # aka parent/host/super
        relationship = index.relationship
        ix_key = index_key(index)
        if ix_key in seen_ix[sub_id]:
            return IGNORE  # unexpected, don't process duplicate index twice
        seen_ix[sub_id].add(ix_key)
        seen_ix[ref_id].add(ix_key)
        indices[sub_id].append(index)
        debug("%s --%s--> %s", sub_id, relationship, ref_id)
        if sub_id in live_ids:
            # ref has a live child or extension
            enliven(ref_id)
            # It does not matter that sub_id -> ref_id never makes it into
            # hosts_by_extension since both are live and therefore this index
            # will not need to be traversed in other liveness calculations.
        elif relationship == EXTENSION:
            if sub_id in open_ids:
                if ref_id in live_ids:
                    # sub is open and is the extension of a live case
                    enliven(sub_id)
                else:
                    # live status pending:
                    # if ref becomes live -> sub is open extension of live case
                    # if sub becomes live -> ref has a live extension
                    extensions_by_host[ref_id].add(sub_id)
                    hosts_by_extension[sub_id].add(ref_id)
            else:
                return IGNORE  # closed extension
        elif sub_id in owned_ids:
            # sub is owned and available (open and not an extension case)
            enliven(sub_id)
            # ref has a live child
            enliven(ref_id)
        else:
            # live status pending: if sub becomes live -> ref has a live child
            parents_by_child[sub_id].add(ref_id)

        next_id = ref_id if sub_id in prev_ids else sub_id
        if next_id not in all_ids:
            return next_id
        return IGNORE  # circular reference

    def update_open_and_deleted_ids(related):
        """Update open_ids and deleted_ids with related case_ids

        TODO store referenced case (parent) deleted and closed status in
        CommCareCaseIndexSQL to reduce number of related indices fetched
        and avoid this extra query per related query.
        """
        case_ids = {case_id
            for index in related
            for case_id in [index.case_id, index.referenced_id]
            if case_id not in all_ids}
        rows = accessor.get_closed_and_deleted_ids(list(case_ids))
        for case_id, closed, deleted in rows:
            if deleted:
                deleted_ids.add(case_id)
            if closed or deleted:
                case_ids.remove(case_id)
        open_ids.update(case_ids)

    IGNORE = object()
    debug = logging.getLogger(__name__).debug
    accessor = CaseAccessors(restore_state.domain)

    # case graph data structures
    live_ids = set()
    deleted_ids = set()
    extensions_by_host = defaultdict(set)  # host_id -> (open) extension_ids
    hosts_by_extension = defaultdict(set)  # (open) extension_id -> host_ids
    parents_by_child = defaultdict(set)    # child_id -> parent_ids
    indices = defaultdict(list)  # case_id -> list of CommCareCaseIndex-like
    seen_ix = defaultdict(set)   # case_id -> set of '<index.case_id> <index.identifier>'
    owner_ids = list(restore_state.owner_ids)

    debug("sync %s for %r", restore_state.current_sync_log._id, owner_ids)
    with timing_context("livequery"):
        with timing_context("get_case_ids_by_owners"):
            owned_ids = accessor.get_case_ids_by_owners(owner_ids, closed=False)
            debug("owned: %r", owned_ids)

        next_ids = all_ids = set(owned_ids)
        owned_ids = set(owned_ids)  # owned, open case ids (may be extensions)
        open_ids = set(owned_ids)
        while next_ids:
            exclude = set(chain.from_iterable(seen_ix[id] for id in next_ids))
            with timing_context("get_related_indices({} cases, {} seen)".format(
                    len(next_ids), len(exclude))):
                related = accessor.get_related_indices(list(next_ids), exclude)
                if not related:
                    break
                update_open_and_deleted_ids(related)
                next_ids = {classify(index, next_ids)
                    for index in related
                    if index.referenced_id not in deleted_ids
                        and index.case_id not in deleted_ids}
                next_ids.discard(IGNORE)
                all_ids.update(next_ids)
                debug('next: %r', next_ids)

        with timing_context("enliven open roots (%s cases)" % len(open_ids)):
            debug('open: %r', open_ids)
            # owned, open, not an extension -> live
            for case_id in owned_ids:
                if not is_extension(case_id):
                    enliven(case_id)

            # available case with live extension -> live
            for case_id in open_ids:
                if (case_id not in live_ids
                        and not is_extension(case_id)
                        and has_live_extension(case_id)):
                    enliven(case_id)

            debug('live: %r', live_ids)

        if restore_state.last_sync_log:
            with timing_context("discard_already_synced_cases"):
                debug('last sync: %s', restore_state.last_sync_log._id)
                sync_ids = discard_already_synced_cases(
                    live_ids, restore_state, accessor)
        else:
            sync_ids = live_ids
        restore_state.current_sync_log.case_ids_on_phone = live_ids

        with timing_context("compile_response(%s cases)" % len(sync_ids)):
            iaccessor = PrefetchIndexCaseAccessor(accessor, indices)
            compile_response(
                timing_context,
                restore_state,
                response,
                batch_cases(iaccessor, sync_ids),
                init_progress(async_task, len(sync_ids)),
            )


def discard_already_synced_cases(live_ids, restore_state, accessor):
    debug = logging.getLogger(__name__).debug
    sync_log = restore_state.last_sync_log
    phone_ids = sync_log.case_ids_on_phone
    debug("phone_ids: %r", phone_ids)
    if phone_ids:
        sync_ids = live_ids - phone_ids  # sync all live cases not on phone
        # also sync cases on phone that have been modified since last sync
        sync_ids.update(accessor.get_modified_case_ids(list(phone_ids), sync_log))
    else:
        sync_ids = live_ids
    debug('sync_ids: %r', sync_ids)
    return sync_ids


class PrefetchIndexCaseAccessor(object):

    def __init__(self, accessor, indices):
        self.domain = accessor.domain
        self.accessor = accessor
        self.indices = indices

    def get_cases(self, case_ids, **kw):
        assert 'prefetched_indices' not in kw
        kw['prefetched_indices'] = [ix
            for case_id in case_ids
            for ix in self.indices[case_id]]
        return self.accessor.get_cases(case_ids, **kw)


def batch_cases(accessor, case_ids):
    def take(n, iterable):
        # https://docs.python.org/2/library/itertools.html#recipes
        return list(islice(iterable, n))

    track_load = case_load_counter("livequery_restore", accessor.domain)
    ids = iter(case_ids)
    while True:
        next_ids = take(1000, ids)
        if not next_ids:
            break
        track_load(len(next_ids))
        yield accessor.get_cases(next_ids)


def init_progress(async_task, total):
    if not async_task:
        return lambda done: None

    def update_progress(done):
        async_task.update_state(
            state=ASYNC_RESTORE_SENT,
            meta={
                'done': done,
                'total': total,
                'retry-after': ASYNC_RETRY_AFTER
            }
        )

    update_progress(0)
    return update_progress


def compile_response(timing_context, restore_state, response, batches, update_progress):
    done = 0
    for cases in batches:
        with timing_context("get_stock_payload"):
            response.extend(get_stock_payload(
                restore_state.project,
                restore_state.stock_settings,
                cases,
            ))

        with timing_context("get_case_sync_updates (%s cases)" % len(cases)):
            updates = get_case_sync_updates(
                restore_state.domain, cases, restore_state.last_sync_log)

        with timing_context("get_xml_for_response (%s updates)" % len(updates)):
            response.extend(item
                for update in updates
                for item in get_xml_for_response(update, restore_state))

        done += len(cases)
        update_progress(done)
