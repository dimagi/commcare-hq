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
from itertools import chain, islice

from casexml.apps.case.const import CASE_INDEX_EXTENSION as EXTENSION
from casexml.apps.phone.data_providers.case.load_testing import (
    get_xml_for_response,
)
from casexml.apps.phone.data_providers.case.stock import get_stock_payload
from casexml.apps.phone.data_providers.case.utils import get_case_sync_updates
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


def get_payload(timing_context, restore_state):
    """Get case sync restore response
    """
    def enliven(case_id):
        """Mark the given case, its extensions and their hosts as live

        This closure mutates `live_ids`, `extensions_by_host`, and
        `hosts_by_extension`, which are data structures local to the
        enclosing function.
        """
        if case_id in live_ids:
            # already live
            return
        debug('enliven(%s)', case_id)
        live_ids.add(case_id)
        ext_ids = extensions_by_host.pop(case_id, None)
        if ext_ids:
            host_ids = set(chain.from_iterable(
                hosts_by_extension.pop(x, []) for x in ext_ids))
            # ext_ids: case is the extension of a live case
            # host_ids: case has live extension
            for next_id in chain(ext_ids, host_ids):
                enliven(next_id)

    def classify(index, prev_ids):
        """Classify index as either live or extension with live status pending

        This closure mutates `indices` from the enclosing function as
        well as the same data structres mutated by `enliven()`.

        :returns: Case id for next related index fetch or CIRCULAR_REF
        if the related case has already been seen.
        """
        indices[index.case_id].append(index)
        sub_id = index.case_id
        ref_id = index.referenced_id  # aka parent/host/super
        relationship = index.relationship
        debug("%s --%s--> %s", sub_id, relationship, ref_id)
        if sub_id in prev_ids:
            # traverse to parent/host
            if (sub_id in live_ids
                    or (relationship == EXTENSION and ref_id in live_ids)
                    or (relationship != EXTENSION and sub_id in open_ids)):
                # one of the following is true
                # - ref has a live child
                # - ref has a live extension
                # - sub is the extension of a live case
                # - sub is open and is not an extension case
                enliven(sub_id)
                enliven(ref_id)
            else:
                # need to know if parent is live before -> live
                extensions_by_host[ref_id].add(sub_id)
                hosts_by_extension[sub_id].add(ref_id)

            if ref_id not in all_ids:
                return ref_id
        else:
            # traverse to open extension
            assert ref_id in prev_ids, (index, prev_ids)
            assert relationship == EXTENSION, index

            if ref_id in live_ids:
                # sub is the extension of a live case
                enliven(sub_id)
            else:
                # need to know if parent is live before -> live
                extensions_by_host[ref_id].add(sub_id)
                hosts_by_extension[sub_id].add(ref_id)

            if sub_id not in all_ids:
                return sub_id
        return CIRCULAR_REF

    CIRCULAR_REF = object()
    debug = logging.getLogger(__name__).debug
    live_ids = set()
    extensions_by_host = defaultdict(set)  # host_id -> extension_ids
    hosts_by_extension = defaultdict(set)  # extension_id -> host_ids
    indices = defaultdict(list)
    accessor = CaseAccessors(restore_state.domain)

    with timing_context("livequery"):
        with timing_context("get_case_ids_by_owners"):
            owner_ids = list(restore_state.owner_ids)
            open_ids = accessor.get_case_ids_by_owners(owner_ids, closed=False)
            debug("open: %r", open_ids)

        next_ids = all_ids = set(open_ids)
        open_ids = set(open_ids)
        level = 0
        while next_ids:
            level += 1
            with timing_context("get_related_indices(level %s)" % level):
                related = accessor.get_related_indices(list(next_ids), all_ids)
                if not related:
                    break
                next_ids = {classify(index, next_ids) for index in related}
                next_ids.discard(CIRCULAR_REF)
                debug('next: %r all: %r', next_ids, all_ids)
                all_ids.update(next_ids)

        with timing_context("enliven open root cases"):
            # owned, open, not an extension -> live
            for case_id in open_ids:
                if case_id not in hosts_by_extension:
                    enliven(case_id)

            # open root nodes and their extensions -> live
            # TODO store referenced_id open/closed status in case index to avoid this query
            root_ids = [r for r in extensions_by_host if r not in hosts_by_extension]
            debug('roots: %r', root_ids)
            for case_id in accessor.filter_open_case_ids(root_ids):
                enliven(case_id)

            debug('live: %r', live_ids)

        with timing_context("compile_response"):
            iaccessor = PrefetchIndexCaseAccessor(accessor, indices)
            batches = batch_cases(iaccessor, live_ids)
            response = compile_response(timing_context, batches, restore_state)

    return response


class PrefetchIndexCaseAccessor(object):

    def __init__(self, accessor, indices):
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

    ids = iter(case_ids)
    while True:
        next_ids = take(1000, ids)
        if not next_ids:
            break
        yield accessor.get_cases(next_ids)


def compile_response(timing_context, batches, restore_state):
    response = restore_state.restore_class()

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
                for update in updates.itervalues()
                for item in get_xml_for_response(update, restore_state))

    return response
