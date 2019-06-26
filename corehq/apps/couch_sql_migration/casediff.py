from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict

import gevent
from gevent.pool import Pool

from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch

log = logging.getLogger(__name__)


class CaseDiffQueue(object):

    BATCH_SIZE = 100

    def __init__(self, statedb, diff_cases):
        self.statedb = statedb
        self.diff_cases = diff_cases
        self.processed_forms = defaultdict(set)  # case id -> processed form ids
        self.cases_to_diff = {}  # case id -> case doc (JSON)
        self.pool = Pool(5)

    def __enter__(self):
        # TODO load resume state from self.statedb
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        if exc_type is None:
            self._process_remaining_diffs()
        # TODO save resume state to self.statedb

    def update(self, case_ids, form_id):
        """Update the case diff queue with case ids touched by form

        :param case_ids: set of case ids.
        :param form_id: form id touching case ids.
        """
        log.debug("update: cases=%s form=%s", case_ids, form_id)
        processed = self.processed_forms
        for case_id in case_ids:
            processed[case_id].add(form_id)
            if len(processed) >= self.BATCH_SIZE:
                self._lookup_pending_cases()
                processed = self.processed_forms

    def _lookup_pending_cases(self):
        """Lookup cases to be diffed

        Clears `self.processed_forms`
        """
        processed = self.processed_forms
        case_ids = list(processed)
        for case in CaseAccessorCouch.get_cases(case_ids):
            self.enqueue(case.to_json())
        self.processed_forms = defaultdict(set)

    def enqueue(self, case_doc):
        case_id = case_doc["_id"]
        log.debug("enqueue case for diff: %s", case_id)
        cases_to_diff = self.cases_to_diff
        cases_to_diff[case_id] = case_doc
        if len(cases_to_diff) >= self.BATCH_SIZE:
            self.cases_to_diff = {}
            self.pool.spawn(self.diff_cases, cases_to_diff)
            gevent.sleep()  # swap greenlets

    def _process_remaining_diffs(self):
        if self.processed_forms:
            self._lookup_pending_cases()
            assert not self.processed_forms, self.processed_forms
        self.pool, pool = None, self.pool
        if self.cases_to_diff:
            cases_to_diff = self.cases_to_diff
            self.cases_to_diff = None  # prevent enqueue after close
            pool.spawn(self.diff_cases, cases_to_diff)

        while not pool.join(timeout=10):
            log.info('Waiting on {} case diffs'.format(len(pool)))


def get_case_form_ids(couch_case):
    """Get the set of form ids that touched the given couch case object"""
    form_ids = set(couch_case.xform_ids)
    for action in couch_case.actions:
        form_ids.add(action.xform_id)
    return form_ids
