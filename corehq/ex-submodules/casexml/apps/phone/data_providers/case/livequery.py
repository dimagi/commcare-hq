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
import logging
from collections import defaultdict
from functools import partial, wraps
from itertools import chain, islice

from casexml.apps.case.const import CASE_INDEX_EXTENSION as EXTENSION
from casexml.apps.phone.const import ASYNC_RETRY_AFTER
from casexml.apps.phone.tasks import ASYNC_RESTORE_SENT

from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.sql_db.routers import read_from_plproxy_standbys
from corehq.toggles import LIVEQUERY_READ_FROM_STANDBYS, NAMESPACE_USER
from corehq.util.metrics import metrics_counter, metrics_histogram
from corehq.util.metrics.load_counters import case_load_counter
from corehq.util.timer import TimingContext

from .load_testing import get_xml_for_response
from .stock import get_stock_payload
from .utils import get_case_sync_updates


def livequery_read_from_standbys(func):
    @wraps(func)
    def _inner(timing_context, restore_state, response, async_task=None):
        if LIVEQUERY_READ_FROM_STANDBYS.enabled(restore_state.restore_user.user_id, NAMESPACE_USER):
            with read_from_plproxy_standbys():
                return func(timing_context, restore_state, response, async_task)
        else:
            return func(timing_context, restore_state, response, async_task)

    return _inner


@livequery_read_from_standbys
def do_livequery(timing_context, restore_state, response, async_task=None):
    """Get case sync restore response

    This function makes no changes to external state other than updating
    the `restore_state.current_sync_log` and progress of `async_task`.
    Extends `response` with restore elements.
    """

    debug = logging.getLogger(__name__).debug
    domain = restore_state.domain
    owner_ids = list(restore_state.owner_ids)

    debug("sync %s for %r", restore_state.current_sync_log._id, owner_ids)
    with timing_context("livequery"):
        with timing_context("get_case_ids_by_owners"):
            owned_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(
                domain, owner_ids, closed=False)
            debug("owned: %r", owned_ids)

        live_ids, indices = get_live_case_ids_and_indices(domain, owned_ids, timing_context)

        if restore_state.last_sync_log:
            with timing_context("discard_already_synced_cases"):
                debug('last sync: %s', restore_state.last_sync_log._id)
                sync_ids = discard_already_synced_cases(live_ids, restore_state)
        else:
            sync_ids = live_ids

        dependent_ids = live_ids - set(owned_ids)
        debug('updating synclog: live=%r dependent=%r', live_ids, dependent_ids)
        restore_state.current_sync_log.case_ids_on_phone = live_ids
        restore_state.current_sync_log.dependent_case_ids_on_phone = dependent_ids

        total_cases = len(sync_ids)
        with timing_context("compile_response(%s cases)" % total_cases):
            iaccessor = PrefetchIndexCaseAccessor(domain, indices)
            metrics_histogram(
                'commcare.restore.case_load',
                len(sync_ids),
                'cases',
                RESTORE_CASE_LOAD_BUCKETS,
                tags={
                    'domain': domain,
                    'restore_type': 'incremental' if restore_state.last_sync_log else 'fresh'
                }
            )
            metrics_counter('commcare.restore.case_load.count', total_cases, {'domain': domain})
            compile_response(
                timing_context,
                restore_state,
                response,
                batch_cases(iaccessor, sync_ids),
                init_progress(async_task, total_cases),
                total_cases,
            )


def get_case_hierarchy(domain, cases):
    """Get the combined case hierarchy for the input cases"""
    domains = {case.domain for case in cases}
    assert domains == {domain}, "All cases must belong to the same domain"

    case_ids = {case.case_id for case in cases}
    new_cases = get_all_related_live_cases(domain, case_ids)

    return cases + new_cases


def get_all_related_live_cases(domain, case_ids):
    all_case_ids, indices = get_live_case_ids_and_indices(domain, case_ids, TimingContext())
    new_case_ids = list(all_case_ids - case_ids)
    new_cases = PrefetchIndexCaseAccessor(domain, indices).get_cases(new_case_ids)
    return new_cases


def get_live_case_ids_and_indices(domain, owned_ids, timing_context):
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
        CommCareCaseIndex to reduce number of related indices fetched
        and avoid this extra query per related query.
        """
        case_ids = {case_id
            for index in related
            for case_id in [index.case_id, index.referenced_id]
            if case_id not in all_ids}

        # we know these are open since we filter by closed and deleted when fetching the indexes
        open_cases = {
            index.case_id for index in related
            if index.relationship == 'extension'
        }
        check_cases = list(set(case_ids) - open_cases)
        rows = CommCareCase.objects.get_closed_and_deleted_ids(domain, check_cases)
        for case_id, closed, deleted in rows:
            if deleted:
                deleted_ids.add(case_id)
            if closed or deleted:
                case_ids.remove(case_id)
        open_ids.update(case_ids)

    def populate_indices(related):
        # add all indices to `indices` so that they are included in the
        # restore
        for index in related:
            indices[index.case_id].append(index)

    def filter_deleted_indices(related):
        return [index for index in related if index.referenced_id]

    IGNORE = object()
    debug = logging.getLogger(__name__).debug

    # case graph data structures
    live_ids = set()
    deleted_ids = set()
    extensions_by_host = defaultdict(set)  # host_id -> (open) extension_ids
    hosts_by_extension = defaultdict(set)  # (open) extension_id -> host_ids
    parents_by_child = defaultdict(set)    # child_id -> parent_ids
    indices = defaultdict(list)  # case_id -> list of CommCareCaseIndex-like, used as a cache for later
    seen_ix = defaultdict(set)   # case_id -> set of '<index.case_id> <index.identifier>'

    next_ids = all_ids = set(owned_ids)
    owned_ids = set(owned_ids)  # owned, open case ids (may be extensions)
    open_ids = set(owned_ids)
    get_related_indices = partial(CommCareCaseIndex.objects.get_related_indices, domain)
    while next_ids:
        exclude = set(chain.from_iterable(seen_ix[id] for id in next_ids))
        with timing_context("get_related_indices({} cases, {} seen)".format(len(next_ids), len(exclude))):
            related = get_related_indices(list(next_ids), exclude)
            if not related:
                break

            populate_indices(related)
            related_not_deleted = filter_deleted_indices(related)
            update_open_and_deleted_ids(related_not_deleted)
            next_ids = {classify(index, next_ids)
                        for index in related_not_deleted
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
    return live_ids, indices


def discard_already_synced_cases(live_ids, restore_state):
    debug = logging.getLogger(__name__).debug
    sync_log = restore_state.last_sync_log
    phone_ids = sync_log.case_ids_on_phone
    debug("phone_ids: %r", phone_ids)
    if phone_ids:
        sync_ids = live_ids - phone_ids  # sync all live cases not on phone
        # also sync cases on phone that have been modified since last sync
        sync_ids.update(CommCareCase.objects.get_modified_case_ids(
            restore_state.domain, list(phone_ids), sync_log))
    else:
        sync_ids = live_ids
    debug('sync_ids: %r', sync_ids)
    return sync_ids


class PrefetchIndexCaseAccessor:

    def __init__(self, domain, indices):
        self.domain = domain
        self.indices = indices

    def get_cases(self, case_ids, **kw):
        assert 'prefetched_indices' not in kw
        kw['prefetched_indices'] = [ix
            for case_id in case_ids
            for ix in self.indices[case_id]]
        return CommCareCase.objects.get_cases(case_ids, self.domain, **kw)


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


def compile_response(
    timing_context,
    restore_state,
    response,
    batches,
    update_progress,
    total_cases,
):
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
            response.extend(
                item for update in updates
                for item in get_xml_for_response(
                    update, restore_state, total_cases
                )
            )

        done += len(cases)
        update_progress(done)


RESTORE_CASE_LOAD_BUCKETS = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]
